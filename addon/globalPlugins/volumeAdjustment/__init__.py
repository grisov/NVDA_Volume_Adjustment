# A part of the NVDA Volume Adjustment add-on
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.
# Copyright (C) 2020-2026 Oleksandr Gryshchenko <grisov.nvaccess@mailgw.com>

from __future__ import annotations
import os.path
import subprocess
from typing import Callable, List, Optional, Tuple, TypeVar
import addonHandler
import config
import globalPluginHandler
import tones
import ui
import wx
from api import getFocusObject
from globalVars import appArgs
import gui
from gui import settingsDialogs
from gui.message import ReturnCode
from inputCore import InputGesture
from logHandler import log
from NVDAObjects import NVDAObject
from scriptHandler import script
from synthDriverHandler import getSynth, setSynth
from enum import Enum
from pycaw.utils import ERole
from utils.mmdevice import getOutputDevices
from .audiocore import cfg
from .sources import AppSource, AudioSource, PlaybackAppSource, SourceKey, SourceKind, getSourceKey, registry

try:
	addonHandler.initTranslation()
except addonHandler.AddonError:
	log.warning("Unable to init translations. This may be because the addon is running from NVDA scratchpad.")
_: Callable[[str], str]
ngettext: Callable[[str, str, int], str]
GlobalPluginType = TypeVar("GlobalPluginType", bound=globalPluginHandler.GlobalPlugin)

_addonDir = os.path.join(os.path.dirname(__file__), "..", "..")
if isinstance(_addonDir, bytes):
	_addonDir = _addonDir.decode("mbcs")
_curAddon = addonHandler.Addon(_addonDir)
addonName: str = _curAddon.manifest["name"]
addonSummary: str = _curAddon.manifest["summary"]

from .settings import (  # noqa E402
	NvdaVolumeWarningDialog,
	VASettingsPanel,
	getCategoryName,
	getOnlyVisibleCategoryMessage,
	getVisibleCategories,
	setVisibleCategories,
)

UNDEFINED_APP: str = "UndefinedCurrentApplicationName"
# Number of the function keys F1..F12 bound to the output devices
FUNCTION_KEYS = 12
# Prefixes of the names of the scripts created for each output device, see bindSwitchingMethods()
OUTPUT_DEVICE_SCRIPTS = ("switchNvdaOutputToDevice", "setDefaultOutputDevice", "setCommunicationDevice")


class OutputTarget(Enum):
	"""What the switching between output devices changes."""

	# The output device of NVDA speech and sounds
	NVDA = "nvda"
	# The default output device of Windows (console and multimedia roles)
	DEFAULT = "default"
	# The default communication device of Windows
	COMMUNICATION = "communication"


def disableInSecureMode(decoratedCls: GlobalPluginType) -> GlobalPluginType:
	if appArgs.secure:
		return globalPluginHandler.GlobalPlugin
	return decoratedCls


@disableInSecureMode
class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	"""Implementation global commands of NVDA Volume Adjustment add-on."""

	scriptCategory: str = addonSummary

	def __init__(self, *args, **kwargs) -> None:
		"""Initializing initial configuration values and other fields."""
		super(GlobalPlugin, self).__init__(*args, **kwargs)
		confspec = {
			"status": "boolean(default=true)",
			"step": "integer(default=1,min=1,max=20)",
			"focus": "boolean(default=true)",
			"duplicates": "boolean(default=true)",
			"advanced": "boolean(default=false)",
			# Letters of the visible categories of audio sources, see sources.SourceKind
			"categories": 'string(default="OIPR")',
			"announceCategories": "boolean(default=true)",
			"muteCompletely": "boolean(default=false)",
			"mutePercentage": "integer(default=75,min=1,max=99)",
			"unmuteOnExit": "boolean(default=true)",
			"warnNvdaVolume": "boolean(default=true)",
			"gestures": "boolean(default=true)",
		}
		config.conf.spec[addonName] = confspec
		settingsDialogs.NVDASettingsDialog.categoryClasses.append(VASettingsPanel)
		# Remember the default output audio device
		self._defaultOutputDevice: str = config.conf["audio"]["outputDevice"]
		# Audio source selected with arrows: its category and ID, None to adjust the application in focus
		self._selected: Optional[SourceKey] = None
		# The audio source whose name was announced last, so it is not repeated on every keypress
		self._previous: Optional[SourceKey] = None
		# Application of the selected or focused process, reused between keypresses
		self._session: Optional[AppSource] = None
		# Whether the warning about lowering the volume of NVDA itself is currently shown
		self._isWarningShown: bool = False
		# Bind default gestures if necessary
		config.conf[addonName]["gestures"] and self.bindGestures(self.__defaultGestures)
		# Creating the switching methods for the output devices 1-12
		self.bindSwitchingMethods()
		registry.start(cfg.devices)

	def terminate(self, *args, **kwargs) -> None:
		"""This will be called when NVDA is finished with this global plugin."""
		if config.conf[addonName]["unmuteOnExit"]:
			# It takes a few milliseconds and uses the COM objects of audio devices created in this thread
			try:
				self.unmuteAllAudioSources()
			except Exception:
				log.exception("Unable to unmute audio sources on exit")
		registry.stop()
		try:
			settingsDialogs.NVDASettingsDialog.categoryClasses.remove(VASettingsPanel)
		except ValueError:
			log.warning("Can't remove %s Settings panel from NVDA settings dialogs", addonSummary)
		super(GlobalPlugin, self).terminate(*args, **kwargs)

	def event_gainFocus(self, obj: NVDAObject, NextHandler: Callable) -> None:
		"""Track the application in focus if the corresponding option is enabled.
		@param obj: the object to track if focused
		@type obj: NVDAObject
		@param nextHandler: next event handler
		@type nextHandler: Callable
		"""
		if config.conf[addonName]["focus"]:
			self._selected = None
			# The name of the application in focus is announced on the next keypress
			self._previous = None
			# The application in focus may have changed, so its audio session is looked up again
			self._session = None
		NextHandler()

	def getFocusedProcess(self) -> Tuple[str, int]:
		"""Get the application name and the process ID of the object in system focus.
		@return: the application name and the process ID, 0 if it is unknown
		@rtype: Tuple[str, int]
		"""
		obj = getFocusObject()
		try:
			appName = obj.appModule.appName
		except AttributeError:
			appName = UNDEFINED_APP
		return appName, getattr(obj, "processID", 0)

	def selectProcessInFocus(self) -> bool:
		"""Select the application that is in system focus.
		The application found after the last focus change is reused by subsequent keypresses
		until it becomes outdated (see AudioSourceRegistry.isOutdated()).
		@return: whether the application in focus plays any sound
		@rtype: bool
		"""
		if self._session is None or registry.isOutdated(self._session):
			appName, processId = self.getFocusedProcess()
			# The session of the focused process itself is preferred, then the one found by the app name
			session = registry.findApp(appName, processId)
			if session is None:
				self.announceNotPlaying(appName)
				return False
			self._session = session
		return True

	def getSession(self, kind: SourceKind, name: str) -> Optional[AppSource]:
		"""Get the application of the specified process in the specified category.
		The previously found application is reused while the same process stays selected,
		so repeated keypresses do not enumerate all audio sessions again.
		An outdated application (e.g. the process was restarted or the devices changed) is looked up again.
		@param kind: playback or recording applications
		@type kind: SourceKind
		@param name: the name of the running process
		@type name: str
		@return: the application of the specified process, None if it has no audio session
		@rtype: Optional[AppSource]
		"""
		if (
			self._session is None
			or getSourceKey(self._session) != (kind, name)
			or registry.isOutdated(self._session)
		):
			self._session = registry.findApp(name, kind=kind)
		return self._session

	def formatVolumeLevel(self, volumeLevel: float) -> str:
		"""Get the text of the volume level announcement, e.g. "Volume 29".
		@param volumeLevel: value of volume level
		@type volumeLevel: float, from 0.0 to 1.0
		@return: the text to announce
		@rtype: str
		"""
		# Rounded: Windows stores volume levels as 32-bit floats, 29 % is read back as 28.999999 %
		level = round(volumeLevel * 100.0)
		# Translators: The message is announced during volume control
		return "%s %d" % (_("Volume"), level)

	def announceVolumeLevel(self, volumeLevel: float) -> None:
		"""Announce the current volume level.
		@param volumeLevel: value of volume level
		@type volumeLevel: float, from 0.0 to 1.0
		"""
		ui.message(self.formatVolumeLevel(volumeLevel))

	def announceMuted(self, source: AudioSource) -> None:
		"""Announce that the sound was muted.
		In the "Volume Down" mute mode the remaining volume level is announced as well,
		using the already translated messages, e.g. "The sound is muted, Volume 5".
		@param source: the muted audio source
		@type source: AudioSource
		"""
		# Translators: The message is announced during volume control
		message: str = _("The sound is muted")
		volume = source.volume
		# The level is announced only when the add-on decreased it: a source muted by Windows or another program is silent
		if (
			not config.conf[addonName]["muteCompletely"]
			and source.mutedKey in cfg.muted
			and not (volume is not None and volume.GetMute())
		):
			message = f"{message}, {self.formatVolumeLevel(source.volumeLevel)}"
		ui.message(message)

	def announceChannel(self, number: int) -> None:
		"""Announce the number of the selected audio channel.
		@param number: the number of audio channel
		@type number: int
		"""
		# Translators: Message about the number of the selected audio channel
		ui.message(_("Channel %d") % number)

	def announceNotPlaying(self, app: str) -> None:
		"""Announce that the application does not play any sound, so its volume cannot be adjusted.
		@param app: the name of the application
		@type app: str
		"""
		# Translators: The message when the selected application does not play any sound
		ui.message(_("{app} is not playing any sound.").format(app=app))

	def announceNotSupported(self) -> None:
		"""Announce that the feature currently is not supported."""
		# Translators: The message when feature currently is not supported
		ui.message(_("Not supported"))

	def getAllSources(self) -> List[AudioSource]:
		"""List of all audio sources available for switching, in the order of the categories:
		output devices, input devices, playback applications, recording applications.
		Hidden categories, devices and processes are skipped.
		Each process name is listed once per category: all its audio sessions are adjusted together.
		@return: the audio sources, the list changes dynamically
		@rtype: List[AudioSource]
		"""
		sources: List[AudioSource] = []
		for kind in getVisibleCategories():
			sources.extend(self.getSources(kind))
		return sources

	def getSources(self, kind: SourceKind) -> List[AudioSource]:
		"""List of the audio sources of one category, hidden devices and processes are skipped.
		@param kind: the category of audio sources
		@type kind: SourceKind
		@return: the audio sources of the category
		@rtype: List[AudioSource]
		"""
		if kind == SourceKind.PLAYBACK_APP:
			return [*registry.getApps(cfg.processes)]
		if kind == SourceKind.RECORDING_APP:
			return [*registry.getRecordingApps(cfg.processes)]
		return [device for device in registry.devices if device.kind == kind]

	def toggleCategory(self, kind: SourceKind) -> None:
		"""Show or hide the category of audio sources and announce the result.
		The last visible category cannot be hidden.
		@param kind: the category of audio sources
		@type kind: SourceKind
		"""
		visible = getVisibleCategories()
		category = getCategoryName(kind)
		if kind not in visible:
			setVisibleCategories([*visible, kind])
			count = len(self.getSources(kind))
			# Translators: The message when a category of audio sources is shown,
			# {category} is its name, e.g. "Recording apps", {count} is the number of its audio sources now
			message = ngettext("{category} shown, {count} source", "{category} shown, {count} sources", count)
			ui.message(message.format(category=category, count=count))
		elif visible == [kind]:
			ui.message(getOnlyVisibleCategoryMessage(category, hiding=True))
		else:
			setVisibleCategories([visibleKind for visibleKind in visible if visibleKind != kind])
			# Translators: The message when a category of audio sources is hidden,
			# {category} is its name, e.g. "Recording apps"
			ui.message(_("{category} hidden").format(category=category))

	def showOnlyCategory(self, kind: SourceKind) -> None:
		"""Show only the specified category of audio sources and announce the result.
		@param kind: the category of audio sources
		@type kind: SourceKind
		"""
		category = getCategoryName(kind)
		if getVisibleCategories() == [kind]:
			ui.message(getOnlyVisibleCategoryMessage(category))
			return
		setVisibleCategories([kind])
		count = len(self.getSources(kind))
		# Translators: The message when only one category of audio sources is shown,
		# {category} is its name, e.g. "Recording apps", {count} is the number of its audio sources now
		message = ngettext("{category} only, {count} source", "{category} only, {count} sources", count)
		ui.message(message.format(category=category, count=count))

	def unmuteAllAudioSources(self) -> None:
		"""Unmute all muted audio devices and audio sessions."""
		for device in registry.devices:
			device.isMuted and device.unmute()
		# Hidden processes are unmuted too: they may have been muted before they were hidden
		for app in [*registry.getApps(), *registry.getRecordingApps()]:
			app.isMuted and app.unmute()

	def getSourceTitle(self, source: AudioSource) -> str:
		"""Get the name of the audio source to announce.
		@param source: the audio source
		@type source: AudioSource
		@return: human friendly name of the audio source
		@rtype: str
		"""
		if isinstance(source, AppSource):
			return source.title
		if source.default:
			# Translators: Used as the prefix to default audio device name
			return "{default}: {title}".format(default=_("Default audio device"), title=source.name)
		return source.name

	def getCurrentSourceKey(self, sources: List[AudioSource]) -> Optional[SourceKey]:
		"""Get the key of the audio source that switching starts from.
		@param sources: the audio sources available for switching, not empty
		@type sources: List[AudioSource]
		@return: the selected source, the application in focus or the first source,
			None if the application in focus does not play any sound
		@rtype: Optional[SourceKey]
		"""
		if self._selected is not None:
			return self._selected
		if config.conf[addonName]["focus"]:
			focused = registry.findApp(*self.getFocusedProcess())
			return getSourceKey(focused) if focused is not None else None
		# Without focus tracking the first source is adjusted until another one is selected
		return getSourceKey(sources[0])

	def selectSource(self, source: AudioSource, announceCategory: bool) -> None:
		"""Select the audio source for the volume commands and announce it.
		@param source: the audio source to select
		@type source: AudioSource
		@param announceCategory: whether the name of its category is announced before its name
		@type announceCategory: bool
		"""
		self._selected = self._previous = getSourceKey(source)
		if isinstance(source, AppSource):
			self._session = source
		title = self.getSourceTitle(source)
		if announceCategory:
			title = f"{getCategoryName(source.kind)}, {title}"
		ui.message(title)
		if config.conf[addonName]["status"]:
			self.announceMuted(source) if source.isMuted else self.announceVolumeLevel(source.volumeLevel)

	def switchAudioSource(self, step: int) -> None:
		"""Select the next or previous audio source in the list and announce it.
		Starting from the application in focus, the neighbouring source is selected.
		@param step: offset in the list of audio sources
		@type step: int (usually 1 or -1)
		"""
		sources = self.getAllSources()
		if not sources:
			return
		keys = [getSourceKey(source) for source in sources]
		current = self.getCurrentSourceKey(sources)
		if current in keys:
			position = keys.index(current)
		elif step > 0:
			# Unknown position: the next source is the first application, the previous one is the last source
			position = len([source for source in sources if not isinstance(source, AppSource)]) - 1
		else:
			position = 0
		source = sources[(position + step) % len(sources)]
		# The category is announced when it changes, or when the previous source is not known
		self.selectSource(
			source,
			announceCategory=config.conf[addonName]["announceCategories"]
			and (current is None or current[0] != source.kind),
		)

	def switchCategory(self, step: int) -> None:
		"""Select the first audio source of the next or previous visible category and announce it
		with the name of the category. Categories without audio sources are skipped.
		With only one such category, its first source is selected.
		@param step: direction in the list of categories
		@type step: int (1 or -1)
		"""
		sources = self.getAllSources()
		if not sources:
			return
		current = self.getCurrentSourceKey(sources)
		order = list(SourceKind)
		# The position of the current category, or just before the first/after the last one if it is unknown
		position = order.index(current[0]) if current is not None else (-1 if step > 0 else len(order))
		for offset in range(1, len(order) + 1):
			kind = order[(position + step * offset) % len(order)]
			source = next((source for source in sources if source.kind == kind), None)
			if source is not None:
				# The name of the category is always announced: it is the purpose of the command
				self.selectSource(source, announceCategory=True)
				return

	def announceTitleOnce(self, source: AudioSource) -> AudioSource:
		"""Announce the name of the application when a volume command uses it for the first time.
		@param source: the audio source to adjust
		@type source: AudioSource
		@return: the same audio source
		@rtype: AudioSource
		"""
		key = getSourceKey(source)
		if key != self._previous:
			ui.message(self.getSourceTitle(source))
			self._previous = key
		return source

	def getAudioSource(self) -> Optional[AudioSource]:
		"""Get the object of the audio source selected with arrows (device or application),
		this can be instance inherited from the sources.AudioSource class.
		Also announces the name of the application at the first treatment.
		@return: instance of selected audio source, None if the selected application has no audio session
		@rtype: Optional[AudioSource]
		"""
		if self._selected is None:
			return None
		kind, id = self._selected
		if kind in (SourceKind.OUTPUT_DEVICE, SourceKind.INPUT_DEVICE):
			devices = registry.devices
			device = next((device for device in devices if device.id == id), None)
			if device is None:
				# The selected device has been removed or hidden: the default output device is adjusted instead
				if not devices:
					return None
				device = devices[0]
				self._selected = getSourceKey(device)
				ui.message(self.getSourceTitle(device))
			# The name of the application is announced again when it is selected after a device
			self._previous = self._selected
			return device
		app = self.getSession(kind, id)
		if app is None:
			self.announceNotPlaying(id.replace(".exe", ""))
			return None
		return self.announceTitleOnce(app)

	def isNvdaSession(self, source: AudioSource) -> bool:
		"""Check whether the audio source is the audio session of NVDA itself, which plays NVDA speech.
		@param source: audio source to check
		@type source: AudioSource
		@return: whether the audio source belongs to the running NVDA process
		@rtype: bool
		"""
		return isinstance(source, PlaybackAppSource) and os.getpid() in source.processIds

	def runWithNvdaWarning(self, source: AudioSource, action: Callable[[], None]) -> None:
		"""Run the action that lowers or mutes the volume of the audio source.
		For the audio session of NVDA itself, the action runs only after the user confirms the warning,
		unless the warning has been disabled with its checkbox or in the add-on settings.
		@param source: the audio source whose volume is changed
		@type source: AudioSource
		@param action: the change of the volume and its announcement
		@type action: Callable[[], None]
		"""
		if not config.conf[addonName]["warnNvdaVolume"] or not self.isNvdaSession(source):
			action()
			return
		if self._isWarningShown:
			return

		def showWarning() -> None:
			self._isWarningShown = True
			try:
				with NvdaVolumeWarningDialog(gui.mainFrame) as dialog:
					confirmed = dialog.ShowModal() == ReturnCode.OK
					if confirmed and dialog.dontShowAgainChk.GetValue():
						config.conf[addonName]["warnNvdaVolume"] = False
			finally:
				self._isWarningShown = False
			if confirmed:
				action()

		wx.CallAfter(showWarning)

	def getSelectedAudioSource(self) -> Optional[AudioSource]:
		"""Get the audio source to adjust: the application in focus or the source selected in the list.
		Announces if the selected application does not play any sound.
		@return: the selected audio source, None if there is nothing to adjust
		@rtype: Optional[AudioSource]
		"""
		if self._selected is not None and self._selected[0] not in getVisibleCategories():
			# The category of the selected source has been hidden with a gesture or in the add-on settings:
			# the application in focus or the first source is adjusted instead
			self._selected = self._previous = None
			self._session = None
		if self._selected is None:
			if config.conf[addonName]["focus"]:
				if not self.selectProcessInFocus():
					return None
				# Incorrect narrowing of the attribute by MyPy
				return self.announceTitleOnce(self._session)  # type: ignore
			# Without focus tracking the first source in the list is adjusted until another one is selected
			sources = self.getAllSources()
			if not sources:
				return None
			self._selected = getSourceKey(sources[0])
		return self.getAudioSource()

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Increase the volume"))
	def script_volumeUp(self, gesture: InputGesture) -> None:
		"""Increase the volume of the selected audio source.
		@param gesture: the input gesture in question
		@type gesture: InputGesture
		"""
		source = self.getSelectedAudioSource()
		if source is None:
			return
		self.announceVolumeLevel(source.volumeUp())

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Decrease the volume"))
	def script_volumeDown(self, gesture: InputGesture) -> None:
		"""Decrease the volume of the selected audio source.
		@param gesture: the input gesture in question
		@type gesture: InputGesture
		"""
		source = self.getSelectedAudioSource()
		if source is None:
			return

		def volumeDown() -> None:
			volumeLevel = source.volumeDown()
			if volumeLevel > 0.0:
				self.announceVolumeLevel(volumeLevel)
				return
			source.mute()
			self.announceMuted(source)

		self.runWithNvdaWarning(source, volumeDown)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Set the maximum volume level"))
	def script_volumeMax(self, gesture: InputGesture) -> None:
		"""Set the maximum volume level for the selected audio source.
		@param gesture: the input gesture in question
		@type gesture: InputGesture
		"""
		source = self.getSelectedAudioSource()
		if source is None:
			return
		self.announceVolumeLevel(source.volumeMax())

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Set the minimum volume level"))
	def script_volumeMin(self, gesture: InputGesture) -> None:
		"""Set the minimum volume level for the selected audio source.
		@param gesture: the input gesture in question
		@type gesture: InputGesture
		"""
		source = self.getSelectedAudioSource()
		if source is None:
			return
		self.runWithNvdaWarning(source, lambda: self.announceVolumeLevel(source.volumeMin()))

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Mute selected audio source"))
	def script_mute(self, gesture: InputGesture) -> None:
		"""Mute or unmute the selected audio source.
		@param gesture: gesture assigned to this method
		@type gesture: InputGesture
		"""
		source = self.getSelectedAudioSource()
		if source is None:
			return
		if source.isMuted:
			source.unmute()
			self.announceVolumeLevel(source.volumeLevel)
			return

		def mute() -> None:
			source.mute()
			self.announceMuted(source)

		self.runWithNvdaWarning(source, mute)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Switch to the next audio source"))
	def script_next(self, gesture: InputGesture) -> None:
		"""Switch to the next audio source (audio device or process).
		@param gesture: the input gesture in question
		@type gesture: InputGesture
		"""
		self.switchAudioSource(step=1)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Switch to the previous audio source"))
	def script_prev(self, gesture: InputGesture) -> None:
		"""Switch to the previous audio source (audio device or process).
		@param gesture: the input gesture in question
		@type gesture: InputGesture
		"""
		self.switchAudioSource(step=-1)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Switch to the first audio source of the next category"))
	def script_nextCategory(self, gesture: InputGesture) -> None:
		"""Switch to the first audio source of the next visible category.
		@param gesture: the input gesture in question
		@type gesture: InputGesture
		"""
		self.switchCategory(step=1)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Switch to the first audio source of the previous category"))
	def script_prevCategory(self, gesture: InputGesture) -> None:
		"""Switch to the first audio source of the previous visible category.
		@param gesture: the input gesture in question
		@type gesture: InputGesture
		"""
		self.switchCategory(step=-1)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Show or hide output devices"))
	def script_toggleOutputDevices(self, gesture: InputGesture) -> None:
		"""Show or hide the output devices in the list of audio sources.
		@param gesture: the input gesture in question
		@type gesture: InputGesture
		"""
		self.toggleCategory(SourceKind.OUTPUT_DEVICE)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Show or hide input devices"))
	def script_toggleInputDevices(self, gesture: InputGesture) -> None:
		"""Show or hide the input devices in the list of audio sources.
		@param gesture: the input gesture in question
		@type gesture: InputGesture
		"""
		self.toggleCategory(SourceKind.INPUT_DEVICE)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Show or hide applications playing sound"))
	def script_togglePlaybackApps(self, gesture: InputGesture) -> None:
		"""Show or hide the applications playing sound in the list of audio sources.
		@param gesture: the input gesture in question
		@type gesture: InputGesture
		"""
		self.toggleCategory(SourceKind.PLAYBACK_APP)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Show or hide applications recording sound"))
	def script_toggleRecordingApps(self, gesture: InputGesture) -> None:
		"""Show or hide the applications recording sound in the list of audio sources.
		@param gesture: the input gesture in question
		@type gesture: InputGesture
		"""
		self.toggleCategory(SourceKind.RECORDING_APP)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Show only output devices"))
	def script_showOnlyOutputDevices(self, gesture: InputGesture) -> None:
		"""Show only the output devices in the list of audio sources.
		@param gesture: the input gesture in question
		@type gesture: InputGesture
		"""
		self.showOnlyCategory(SourceKind.OUTPUT_DEVICE)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Show only input devices"))
	def script_showOnlyInputDevices(self, gesture: InputGesture) -> None:
		"""Show only the input devices in the list of audio sources.
		@param gesture: the input gesture in question
		@type gesture: InputGesture
		"""
		self.showOnlyCategory(SourceKind.INPUT_DEVICE)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Show only applications playing sound"))
	def script_showOnlyPlaybackApps(self, gesture: InputGesture) -> None:
		"""Show only the applications playing sound in the list of audio sources.
		@param gesture: the input gesture in question
		@type gesture: InputGesture
		"""
		self.showOnlyCategory(SourceKind.PLAYBACK_APP)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Show only applications recording sound"))
	def script_showOnlyRecordingApps(self, gesture: InputGesture) -> None:
		"""Show only the applications recording sound in the list of audio sources.
		@param gesture: the input gesture in question
		@type gesture: InputGesture
		"""
		self.showOnlyCategory(SourceKind.RECORDING_APP)

	def getCurrentOutputId(self, target: OutputTarget) -> str:
		"""Get the ID of the output device currently used for the target.
		@param target: NVDA output or a default device of Windows
		@type target: OutputTarget
		@return: the device ID, "default" or empty if NVDA or Windows uses no specific device
		@rtype: str
		"""
		if target == OutputTarget.NVDA:
			return config.conf["audio"]["outputDevice"]
		if target == OutputTarget.DEFAULT:
			return registry.getDefaultOutputId(ERole.eMultimedia)
		return registry.getDefaultOutputId(ERole.eCommunications)

	def setOutputDevice(self, target: OutputTarget, id: str, name: str) -> None:
		"""Switch the output of NVDA or a default device of Windows to the specified device and announce its name.
		@param target: NVDA output or a default device of Windows
		@type target: OutputTarget
		@param id: the device ID, the configuration default of NVDA for its "default" output
		@type id: str
		@param name: the name of the device to announce
		@type name: str
		"""
		if target == OutputTarget.NVDA:
			config.conf["audio"]["outputDevice"] = id
			if setSynth(getSynth().name):
				tones.terminate()
				tones.initialize()
		else:
			roles = (
				[ERole.eConsole, ERole.eMultimedia]
				if target == OutputTarget.DEFAULT
				else [ERole.eCommunications]
			)
			if not registry.setDefaultOutput(id, roles):
				# Translators: The message when Windows does not allow to change its default audio device
				ui.message(_("Unable to set the default device"))
				return
		ui.message(name)

	def selectOutputDeviceById(self, target: OutputTarget, id: str, name: str) -> None:
		"""Switch to the output device found when NVDA was started, if it is still available.
		@param target: NVDA output or a default device of Windows
		@type target: OutputTarget
		@param id: the device ID
		@type id: str
		@param name: the name of the device
		@type name: str
		"""
		if id not in [deviceId for deviceId, deviceName in registry.getOutputDevices()]:
			# Translators: The message when the output device has been disconnected or disabled since NVDA was started,
			# {name} is the name of the device
			ui.message(_("{name} is not available").format(name=name))
			return
		self.setOutputDevice(target, id, name)

	def selectOutputDeviceByStep(self, target: OutputTarget, step: int) -> None:
		"""Switch to the next or previous output device in the order of Windows.
		If no specific device is used (e.g. NVDA follows the default device), the first or last one is selected.
		@param target: NVDA output or a default device of Windows
		@type target: OutputTarget
		@param step: offset in the list of output devices
		@type step: int (usually 1 or -1)
		"""
		devices = registry.getOutputDevices()
		if not devices:
			return
		ids = [id for id, name in devices]
		current = self.getCurrentOutputId(target)
		if current in ids:
			index = (ids.index(current) + step) % len(devices)
		else:
			index = 0 if step > 0 else -1
		self.setOutputDevice(target, *devices[index])

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Switch NVDA output to the next device"))
	def script_nextOutputDevice(self, gesture: InputGesture) -> None:
		"""Switch NVDA output to the next active output device.
		@param gesture: the input gesture in question
		@type gesture: InputGesture
		"""
		self.selectOutputDeviceByStep(OutputTarget.NVDA, step=1)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Switch NVDA output to the previous device"))
	def script_prevOutputDevice(self, gesture: InputGesture) -> None:
		"""Switch NVDA output to the previous active output device.
		@param gesture: the input gesture in question
		@type gesture: InputGesture
		"""
		self.selectOutputDeviceByStep(OutputTarget.NVDA, step=-1)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Switch NVDA output to the default device"))
	def script_switchNvdaOutputToDefault(self, gesture: InputGesture) -> None:
		"""Switch NVDA output to the default output device of Windows, so NVDA follows its changes.
		@param gesture: the input gesture in question
		@type gesture: InputGesture
		"""
		# The first item is the "default" output with its name translated by NVDA; the devices are not read
		default = next(getOutputDevices(includeDefault=True))
		self.setOutputDevice(OutputTarget.NVDA, default.id, default.friendlyName)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Set the next device as the default output device"))
	def script_nextDefaultOutputDevice(self, gesture: InputGesture) -> None:
		"""Make the next active output device the default output device of Windows.
		@param gesture: the input gesture in question
		@type gesture: InputGesture
		"""
		self.selectOutputDeviceByStep(OutputTarget.DEFAULT, step=1)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Set the previous device as the default output device"))
	def script_prevDefaultOutputDevice(self, gesture: InputGesture) -> None:
		"""Make the previous active output device the default output device of Windows.
		@param gesture: the input gesture in question
		@type gesture: InputGesture
		"""
		self.selectOutputDeviceByStep(OutputTarget.DEFAULT, step=-1)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Set the next device as the default communication device"))
	def script_nextCommunicationDevice(self, gesture: InputGesture) -> None:
		"""Make the next active output device the default communication device of Windows.
		@param gesture: the input gesture in question
		@type gesture: InputGesture
		"""
		self.selectOutputDeviceByStep(OutputTarget.COMMUNICATION, step=1)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Set the previous device as the default communication device"))
	def script_prevCommunicationDevice(self, gesture: InputGesture) -> None:
		"""Make the previous active output device the default communication device of Windows.
		@param gesture: the input gesture in question
		@type gesture: InputGesture
		"""
		self.selectOutputDeviceByStep(OutputTarget.COMMUNICATION, step=-1)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Open the Sound dialog of Windows"))
	def script_openSoundDialog(self, gesture: InputGesture) -> None:
		"""Open the classic Sound dialog of the Windows Control Panel (mmsys.cpl),
		which lists all playback and recording devices with their properties.
		If it is missing (e.g. removed in a future or customized Windows), the Sound page of the Windows Settings is opened.
		@param gesture: the input gesture in question
		@type gesture: InputGesture
		"""
		system32 = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32")
		if os.path.isfile(os.path.join(system32, "mmsys.cpl")):
			try:
				subprocess.Popen([os.path.join(system32, "control.exe"), "mmsys.cpl"])
				return
			except OSError:
				log.error("Unable to open the Sound dialog of Windows", exc_info=True)
		try:
			os.startfile("ms-settings:sound")
		except OSError:
			log.error("Unable to open the Sound settings of Windows", exc_info=True)

	def outputDeviceScriptFactory(
		self,
		target: OutputTarget,
		id: str,
		name: str,
		description: str,
	) -> Callable[[GlobalPlugin, InputGesture], None]:
		"""Create the script that switches to the specified output device.
		@param target: NVDA output or a default device of Windows
		@type target: OutputTarget
		@param id: the device ID
		@type id: str
		@param name: the name of the device
		@type name: str
		@param description: the name of the script in the NVDA input gestures dialog
		@type description: str
		@return: the script
		@rtype: Callable[[GlobalPlugin, InputGesture], None]
		"""

		def script_selectOutputDevice(self, gesture: InputGesture) -> None:
			"""Switch to the output device of the script.
			@param gesture: gesture assigned to this method
			@type gesture: InputGesture
			"""
			self.selectOutputDeviceById(target, id, name)

		return script(description=description)(script_selectOutputDevice)

	def bindSwitchingMethods(self) -> None:
		"""Create the scripts that switch NVDA output and the default devices of Windows to each output device
		found when NVDA is started, and bind the first 12 of them to F1-F12 with the modifiers of each target
		if the default gestures are enabled. Devices connected later are available after NVDA is restarted.
		Should be called in the class constructor.
		"""
		# The scripts of the devices found the previous time the plugin was created, e.g. before the add-ons were reloaded
		for scriptName in [name for name in vars(self.__class__) if name.startswith("script_")]:
			if scriptName[len("script_") :].rstrip("0123456789") in OUTPUT_DEVICE_SCRIPTS:
				delattr(self.__class__, scriptName)
		# Translators: The name of the method that displayed in the NVDA input gestures dialog,
		# {number} is the number of the output device in the order of Windows, e.g. 1 for F1, {name} is its name
		nvdaDescription = _("Switch NVDA output to the device {number} ({name})")
		# Translators: The name of the method that displayed in the NVDA input gestures dialog,
		# {number} is the number of the output device in the order of Windows, e.g. 1 for F1, {name} is its name
		defaultDescription = _("Set the device {number} ({name}) as the default output device")
		# Translators: The name of the method that displayed in the NVDA input gestures dialog,
		# {number} is the number of the output device in the order of Windows, e.g. 1 for F1, {name} is its name
		communicationDescription = _("Set the device {number} ({name}) as the default communication device")
		targets = (
			(OutputTarget.NVDA, "", nvdaDescription),
			(OutputTarget.DEFAULT, "shift+", defaultDescription),
			(OutputTarget.COMMUNICATION, "control+", communicationDescription),
		)
		devices = registry.getOutputDevices()
		for scriptPrefix, (target, modifiers, description) in zip(OUTPUT_DEVICE_SCRIPTS, targets):
			for number, (id, name) in enumerate(devices, 1):
				scriptName = f"{scriptPrefix}{number}"
				setattr(
					self.__class__,
					f"script_{scriptName}",
					self.outputDeviceScriptFactory(
						target, id, name, description.format(number=number, name=name)
					),
				)
				if config.conf[addonName]["gestures"] and number <= FUNCTION_KEYS:
					self.bindGesture(f"kb:NVDA+{modifiers}windows+f{number}", scriptName)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Select next channel"))
	def script_nextChannel(self, gesture: InputGesture) -> None:
		"""Select the next channel of the current audio source.
		@param gesture: the input gesture in question
		@type gesture: InputGesture
		"""
		source = self.getSelectedAudioSource()
		if source is None:
			return
		if source.channelCount <= 0:
			self.announceNotSupported()
			return
		source.channel += 1
		self.announceChannel(source.channel)
		if config.conf[addonName]["status"]:
			self.announceMuted(source) if source.isMuted else self.announceVolumeLevel(
				source.getChannelVolumeLevel(),
			)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Select previous channel"))
	def script_prevChannel(self, gesture: InputGesture) -> None:
		"""Select the previous channel of the current audio source.
		@param gesture: the input gesture in question
		@type gesture: InputGesture
		"""
		source = self.getSelectedAudioSource()
		if source is None:
			return
		if source.channelCount <= 0:
			self.announceNotSupported()
			return
		source.channel -= 1
		self.announceChannel(source.channel)
		if config.conf[addonName]["status"]:
			self.announceMuted(source) if source.isMuted else self.announceVolumeLevel(
				source.getChannelVolumeLevel(),
			)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Increase the volume of the selected channel"))
	def script_channelVolumeUp(self, gesture: InputGesture) -> None:
		"""Increase the volume level of the selected audio channel.
		@param gesture: the input gesture in question
		@type gesture: InputGesture
		"""
		source = self.getSelectedAudioSource()
		if source is None:
			return
		level: float = source.channelVolumeUp()
		if level < 0:
			self.announceNotSupported()
			return
		self.announceVolumeLevel(level)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Decrease the volume of the selected channel"))
	def script_channelVolumeDown(self, gesture: InputGesture) -> None:
		"""Decrease the volume level of the selected audio channel.
		@param gesture: the input gesture in question
		@type gesture: InputGesture
		"""
		source = self.getSelectedAudioSource()
		if source is None:
			return
		level: float = source.channelVolumeDown()
		if level < 0:
			self.announceNotSupported()
			return
		self.announceVolumeLevel(level)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Set the maximum volume level for the selected channel"))
	def script_channelVolumeMax(self, gesture: InputGesture) -> None:
		"""Set the maximum volume level for the selected audio channel.
		@param gesture: the input gesture in question
		@type gesture: InputGesture
		"""
		source = self.getSelectedAudioSource()
		if source is None:
			return
		level: float = source.channelVolumeMax()
		if level < 0:
			self.announceNotSupported()
			return
		self.announceVolumeLevel(level)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Set the minimum volume level for the selected channel"))
	def script_channelVolumeMin(self, gesture: InputGesture) -> None:
		"""Set the minimum volume level for the selected audio channel.
		@param gesture: the input gesture in question
		@type gesture: InputGesture
		"""
		source = self.getSelectedAudioSource()
		if source is None:
			return
		level: float = source.channelVolumeMin()
		if level < 0:
			self.announceNotSupported()
			return
		self.announceVolumeLevel(level)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Set the average volume level for all channels"))
	def script_channelVolumeAverage(self, gesture: InputGesture) -> None:
		"""Set the average volume level for all audio channels.
		@param gesture: the input gesture in question
		@type gesture: InputGesture
		"""
		source = self.getSelectedAudioSource()
		if source is None:
			return
		level: float = source.channelVolumeAverage()
		if level < 0:
			self.announceNotSupported()
			return
		self.announceVolumeLevel(level)

	__defaultGestures = {
		# Volume level
		"kb:NVDA+windows+upArrow": "volumeUp",
		"kb:NVDA+windows+downArrow": "volumeDown",
		"kb:NVDA+windows+home": "volumeMax",
		"kb:NVDA+windows+end": "volumeMin",
		"kb:NVDA+windows+escape": "mute",
		"kb:NVDA+windows+rightArrow": "next",
		"kb:NVDA+windows+leftArrow": "prev",
		"kb:NVDA+control+windows+rightArrow": "nextCategory",
		"kb:NVDA+control+windows+leftArrow": "prevCategory",
		# Categories of audio sources
		"kb:NVDA+windows+o": "toggleOutputDevices",
		"kb:NVDA+windows+i": "toggleInputDevices",
		"kb:NVDA+windows+p": "togglePlaybackApps",
		"kb:NVDA+windows+r": "toggleRecordingApps",
		"kb:NVDA+shift+windows+o": "showOnlyOutputDevices",
		"kb:NVDA+shift+windows+i": "showOnlyInputDevices",
		"kb:NVDA+shift+windows+p": "showOnlyPlaybackApps",
		"kb:NVDA+shift+windows+r": "showOnlyRecordingApps",
		# Output audio devices
		"kb:NVDA+windows+pageUp": "nextOutputDevice",
		"kb:NVDA+windows+pageDown": "prevOutputDevice",
		"kb:NVDA+windows+d": "switchNvdaOutputToDefault",
		"kb:NVDA+windows+s": "openSoundDialog",
		"kb:NVDA+shift+windows+pageUp": "nextDefaultOutputDevice",
		"kb:NVDA+shift+windows+pageDown": "prevDefaultOutputDevice",
		"kb:NVDA+control+windows+pageUp": "nextCommunicationDevice",
		"kb:NVDA+control+windows+pageDown": "prevCommunicationDevice",
		# Customize channels volume
		"kb:NVDA+shift+windows+rightArrow": "nextChannel",
		"kb:NVDA+shift+windows+leftArrow": "prevChannel",
		"kb:NVDA+shift+windows+upArrow": "channelVolumeUp",
		"kb:NVDA+shift+windows+downArrow": "channelVolumeDown",
		"kb:NVDA+shift+windows+home": "channelVolumeMax",
		"kb:NVDA+shift+windows+end": "channelVolumeMin",
		"kb:NVDA+shift+windows+escape": "channelVolumeAverage",
	}
