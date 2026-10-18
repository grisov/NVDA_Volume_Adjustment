# A part of the NVDA Volume Adjustment add-on
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.
# Copyright (C) 2020-2026 Oleksandr Gryshchenko <grisov.nvaccess@mailgw.com>

from __future__ import annotations
import os.path
from typing import Callable, List, Optional, TypeVar
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
from .sources import AudioSource, PlaybackAppSource, registry

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
		# Switching between processes
		self._index: int = 0  # index of current audio source
		# Remember the name of the audio session of the previous process
		self._previous: str = ""
		# Name of the current process
		self._process: str = ""
		# Application of the current process, reused between keypresses
		self._session: Optional[PlaybackAppSource] = None
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
			self._index = -1
			self._previous = UNDEFINED_APP
			# The application in focus may have changed, so its audio session is looked up again
			self._session = None
		NextHandler()

	def selectProcessInFocus(self) -> bool:
		"""Select the name of the process that is in system focus.
		The application found after the last focus change is reused by subsequent keypresses
		until it becomes outdated (see AudioSourceRegistry.isOutdated()).
		@return: whether the current process is in the list of audio sessions
		@rtype: bool
		"""
		if self._session is None or registry.isOutdated(self._session):
			obj = getFocusObject()
			try:
				appName = obj.appModule.appName
			except AttributeError:
				appName = UNDEFINED_APP
			# The session of the focused process itself is preferred, then the one found by the app name
			session = registry.findApp(appName, getattr(obj, "processID", 0))
			if session is None:
				self.announceNotPlaying(appName)
				return False
			self._session = session
		self._process = self._session.name
		return True

	def getSession(self, name: str) -> Optional[PlaybackAppSource]:
		"""Get the application of the specified process.
		The previously found application is reused while the same process stays selected,
		so repeated keypresses do not enumerate all audio sessions again.
		An outdated application (e.g. the process was restarted or the default device changed) is looked up again.
		@param name: the name of the running process
		@type name: str
		@return: the application of the specified process, None if it does not play any sound
		@rtype: Optional[PlaybackAppSource]
		"""
		if self._session is None or self._session.name != name or registry.isOutdated(self._session):
			self._session = registry.findApp(name)
		return self._session

	def announceVolumeLevel(self, volumeLevel: float) -> None:
		"""Announce the current volume level.
		@param volumeLevel: value of volume level
		@type volumeLevel: float, from 0.0 to 1.0
		"""
		# Translators: The message is announced during volume control
		ui.message("%s %d" % (_("Volume"), int(volumeLevel * 100.0)))

	def announceMuted(self) -> None:
		"""Announce that the sound was muted."""
		# Translators: The message is announced during volume control
		ui.message(_("The sound is muted"))

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

	def getAllSessions(self) -> List[str]:
		"""List of all running processes that play sound, excluding the hidden processes.
		Each process name is listed once: all audio sessions of the process are adjusted together.
		@return: list of currently running processes
		@rtype: List[str]
		"""
		return [app.name for app in registry.getApps(cfg.processes)]

	def unmuteAllAudioSources(self) -> None:
		"""Unmute all muted audio devices and audio sessions."""
		for device in registry.devices:
			device.isMuted and device.unmute()
		# Hidden processes are unmuted too: they may have been muted before they were hidden
		for app in registry.getApps():
			app.isMuted and app.unmute()

	def selectAudioSource(self, sessions: List[str]) -> None:
		"""Select audio source to adjust its volume level.
		This can be a physical audio device or a running process.
		@param sessions: filtered list of all running processes, changes dynamically
		@type sessions: List[str]
		"""
		if 0 <= self._index < len(registry.devices):
			source: AudioSource = registry.devices[self._index]
			title: str = source.name
			if source.default:
				# Translators: Used as the prefix to default audio device name
				title = "{default}: {title}".format(default=_("Default audio device"), title=source.name)
		else:
			try:
				self._process = sessions[self._index - len(registry.devices)]
			except IndexError:
				try:
					self._process = sessions[-1]
				except IndexError:
					self._process = UNDEFINED_APP
			self._previous = self._process
			# Switching between audio sources always takes a fresh session
			app = self._session = registry.findApp(self._process)
			if app is None:
				self.announceNotPlaying(self._process.replace(".exe", ""))
				return
			source = app
			title = app.title
		ui.message(title)
		if config.conf[addonName]["status"]:
			self.announceMuted() if source.isMuted else self.announceVolumeLevel(source.volumeLevel)

	def getAudioSource(self) -> Optional[AudioSource]:
		"""Get the object of selected audio source (device or process),
		this can be instance inherited from the sources.AudioSource class.
		Also announces the name of the application at the first treatment.
		@return: instance of selected audio source, None if the selected application does not play any sound
		@rtype: Optional[AudioSource]
		"""
		if 0 <= self._index < len(registry.devices):
			self._previous = UNDEFINED_APP
			return registry.devices[self._index]
		app = self.getSession(self._process)
		if app is None:
			self.announceNotPlaying(self._process.replace(".exe", ""))
			return None
		if app.name != self._previous:
			ui.message(app.title)
			self._previous = app.name
		return app

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
		if self._index < 0 and not self.selectProcessInFocus():
			return None
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
			self.announceMuted()

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
			self.announceMuted()

		self.runWithNvdaWarning(source, mute)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Switch to the next audio source"))
	def script_next(self, gesture: InputGesture) -> None:
		"""Switch to the next audio source (audio device or process).
		@param gesture: the input gesture in question
		@type gesture: InputGesture
		"""
		sessions: List[str] = self.getAllSessions()
		if self._index < 0:
			try:
				self._index = len(registry.devices) + sessions.index(
					next(filter(lambda s: self._process in s, sessions), ""),
				)
			except (ValueError, TypeError):
				self._index = len(registry.devices) - 1
		self._index = self._index + 1 if self._index < (len(registry.devices) + len(sessions) - 1) else 0
		self.selectAudioSource(sessions)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Switch to the previous audio source"))
	def script_prev(self, gesture: InputGesture) -> None:
		"""Switch to the previous audio source (audio device or process).
		@param gesture: the input gesture in question
		@type gesture: InputGesture
		"""
		sessions: List[str] = self.getAllSessions()
		if self._index < 0:
			try:
				self._index = len(registry.devices) + sessions.index(
					next(filter(lambda s: self._process in s, sessions), ""),
				)
			except (ValueError, TypeError):
				pass
		self._index = self._index - 1 if self._index > 0 else len(registry.devices) + len(sessions) - 1
		self.selectAudioSource(sessions)

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
			self.announceMuted() if source.isMuted else self.announceVolumeLevel(
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
			self.announceMuted() if source.isMuted else self.announceVolumeLevel(
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
