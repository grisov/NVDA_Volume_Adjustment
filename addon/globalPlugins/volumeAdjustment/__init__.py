# A part of the NVDA Volume Adjustment add-on
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.
# Copyright (C) 2020-2026 Oleksandr Gryshchenko <grisov.nvaccess@mailgw.com>

from __future__ import annotations
import os.path
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
from utils.mmdevice import AudioOutputDevice, getOutputDevices
from .audiocore import cfg
from .sources import AppSource, AudioSource, PlaybackAppSource, SourceKey, SourceKind, getSourceKey, registry

try:
	addonHandler.initTranslation()
except addonHandler.AddonError:
	log.warning("Unable to init translations. This may be because the addon is running from NVDA scratchpad.")
_: Callable[[str], str]
GlobalPluginType = TypeVar("GlobalPluginType", bound=globalPluginHandler.GlobalPlugin)

_addonDir = os.path.join(os.path.dirname(__file__), "..", "..")
if isinstance(_addonDir, bytes):
	_addonDir = _addonDir.decode("mbcs")
_curAddon = addonHandler.Addon(_addonDir)
addonName: str = _curAddon.manifest["name"]
addonSummary: str = _curAddon.manifest["summary"]

from .settings import NvdaVolumeWarningDialog, VASettingsPanel  # noqa E402

UNDEFINED_APP: str = "UndefinedCurrentApplicationName"


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
		# Creating individual switching methods for each output audio device detected in the system
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
		visible: str = config.conf[addonName]["categories"]
		sources: List[AudioSource] = []
		for kind in SourceKind:
			if kind.value not in visible:
				continue
			if kind == SourceKind.PLAYBACK_APP:
				sources.extend(registry.getApps(cfg.processes))
			elif kind == SourceKind.RECORDING_APP:
				sources.extend(registry.getRecordingApps(cfg.processes))
			else:
				sources.extend(device for device in registry.devices if device.kind == kind)
		return sources

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

	def getCategoryName(self, kind: SourceKind) -> str:
		"""Get the name of the category of audio sources to announce.
		@param kind: the category of audio sources
		@type kind: SourceKind
		@return: the translated name of the category
		@rtype: str
		"""
		if kind == SourceKind.OUTPUT_DEVICE:
			# Translators: The name of the category of audio sources announced while switching between them
			return _("Output devices")
		if kind == SourceKind.INPUT_DEVICE:
			# Translators: The name of the category of audio sources announced while switching between them
			return _("Input devices")
		if kind == SourceKind.PLAYBACK_APP:
			# Translators: The name of the category of audio sources announced while switching between them
			return _("Playback apps")
		# Translators: The name of the category of audio sources announced while switching between them
		return _("Recording apps")

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
		if self._selected is None and config.conf[addonName]["focus"]:
			focused = registry.findApp(*self.getFocusedProcess())
			current = getSourceKey(focused) if focused is not None else None
		elif self._selected is None:
			# Without focus tracking the first source is adjusted until another one is selected
			current = keys[0]
		else:
			current = self._selected
		if current in keys:
			position = keys.index(current)
		elif step > 0:
			# Unknown position: the next source is the first application, the previous one is the last source
			position = len([source for source in sources if not isinstance(source, AppSource)]) - 1
		else:
			position = 0
		source = sources[(position + step) % len(sources)]
		self._selected = self._previous = getSourceKey(source)
		if isinstance(source, AppSource):
			self._session = source
		title = self.getSourceTitle(source)
		# The category is announced when it changes, or when the previous source is not known
		if config.conf[addonName]["announceCategories"] and (current is None or current[0] != source.kind):
			title = f"{self.getCategoryName(source.kind)}, {title}"
		ui.message(title)
		if config.conf[addonName]["status"]:
			self.announceMuted(source) if source.isMuted else self.announceVolumeLevel(source.volumeLevel)

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

	def setOutputDevice(self, device: AudioOutputDevice) -> None:
		"""Switche the NVDA output to the specified audio device.
		@param device: audio output device
		@type device: AudioOutputDevice
		"""
		config.conf["audio"]["outputDevice"] = device.id
		status: bool = setSynth(getSynth().name)
		if status:
			tones.terminate()
			tones.initialize()
		ui.message(device.friendlyName)

	def selectOutputDevice(self, step: int) -> AudioOutputDevice:
		"""Select an audio device from the list with an offset to the specified step.
		@param step: offset step in the list of available audio devices
		@type step: int (usually 1 or -1)
		@return: selected audio device
		@rtype: AudioOutputDevice
		"""
		devices: List[AudioOutputDevice] = [device for device in getOutputDevices(includeDefault=True)]
		if devices[0].id == "":
			devices[0].id = "default"
		try:
			current: int = [dev.id for dev in devices].index(config.conf["audio"]["outputDevice"])
		except ValueError:
			current = 0
		return devices[(current + step) % len(devices)]

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Next audio output device"))
	def script_nextOutputDevice(self, gesture: InputGesture) -> None:
		"""Switch the output to the next available audio device.
		@param gesture: the input gesture in question
		@type gesture: InputGesture
		"""
		device: AudioOutputDevice = self.selectOutputDevice(step=1)
		self.setOutputDevice(device)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Previous audio output device"))
	def script_prevOutputDevice(self, gesture: InputGesture) -> None:
		"""Switch the output to the previous available audio device.
		@param gesture: the input gesture in question
		@type gesture: InputGesture
		"""
		device: AudioOutputDevice = self.selectOutputDevice(step=-1)
		self.setOutputDevice(device)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Switch the output to the selected audio device"))
	def script_switchTo(self, gesture: InputGesture) -> None:
		"""Switch NVDA audio output to the selected sound device.
		@param gesture: gesture assigned to this method
		@type gesture: InputGesture
		"""
		index = int(gesture.displayName.lower()[-2:].replace("f", "")) - 1
		self.setOutputDevice(device=[dev for dev in getOutputDevices(includeDefault=True)][index])

	def switchingMethodsFactory(
		self,
		index: int,
		device: AudioOutputDevice,
	) -> Callable[[GlobalPlugin, InputGesture], None]:
		"""Create a separate switching method for each output audio device detected in the system.
		@param index: sequence number of the detected audio device
		@type index: int, index>=0
		@param device: output audio device in the system
		@type device: AudioOutputDevice
		@return: the instance of the method to switch to the specified audio device
		@rtype: Callable[[GlobalPlugin, InputGesture], None]
		"""

		def script_switchingMethod(self, gesture: InputGesture) -> None:
			"""Switch NVDA audio output to the specified sound device.
			@param gesture: gesture assigned to this method
			@type gesture: InputGesture
			"""
			self.setOutputDevice(device)

		# Translators: The name of the method that displayed in the NVDA input gestures dialog
		script_switchingMethod.__doc__ = _("Switch the output to the device {number} ({name})").format(
			number=index,
			name=device.friendlyName,
		)  # noqa E501
		return script_switchingMethod

	def bindSwitchingMethods(self) -> None:
		"""Bind all created switching methods to the current global plugin class instance,
		should be called in the class constructor.
		"""
		outputDevices: List[AudioOutputDevice] = [device for device in getOutputDevices(includeDefault=True)]
		for i in range(len(outputDevices)):
			name = f"script_switchToDevice{i}"
			setattr(self.__class__, name, self.switchingMethodsFactory(i, outputDevices[i]))
			if config.conf[addonName]["gestures"] and i < 12:
				self.bindGesture("kb:NVDA+windows+f%d" % (i + 1), name.split("_", 1)[1])

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
		# Output audio devices
		"kb:NVDA+windows+pageUp": "nextOutputDevice",
		"kb:NVDA+windows+pageDown": "prevOutputDevice",
		# Customize channels volume
		"kb:NVDA+shift+windows+rightArrow": "nextChannel",
		"kb:NVDA+shift+windows+leftArrow": "prevChannel",
		"kb:NVDA+shift+windows+upArrow": "channelVolumeUp",
		"kb:NVDA+shift+windows+downArrow": "channelVolumeDown",
		"kb:NVDA+shift+windows+home": "channelVolumeMax",
		"kb:NVDA+shift+windows+end": "channelVolumeMin",
		"kb:NVDA+shift+windows+escape": "channelVolumeAverage",
	}
