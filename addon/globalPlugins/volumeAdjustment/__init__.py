#-*- coding:utf-8 -*-
# A part of the NVDA Volume Adjustment add-on
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.
# Copyright (C) 2020-2021 Olexandr Gryshchenko <grisov.nvaccess@mailnull.com>

from typing import Callable, List, Union
import addonHandler
from logHandler import log
try:
	addonHandler.initTranslation()
except addonHandler.AddonError:
	log.warning("Unable to initialise translations. This may be because the addon is running from NVDA scratchpad.")
_: Callable[[str], str]

import os
_addonDir = os.path.join(os.path.dirname(__file__), "..", "..")
if isinstance(_addonDir, bytes):
	_addonDir = _addonDir.decode("mbcs")
_curAddon = addonHandler.Addon(_addonDir)
addonName: str = _curAddon.manifest['name']
addonSummary: str = _curAddon.manifest['summary']

import globalPluginHandler
import ui
import gui
import config
import tones
from globalVars import appArgs
from api import getFocusObject
from scriptHandler import script
from nvwave import getOutputDeviceNames
from synthDriverHandler import getSynth, setSynth
from inputCore import InputGesture
from NVDAObjects import NVDAObject
from threading import Thread
from .audiocore import ExtendedAudioUtilities, AudioDevice, AudioSession, cfg, devices
from .settings import VASettingsPanel

UNDEFINED_APP = "UndefinedCurrentApplicationName"


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	"""Implementation global commands of NVDA Volume Adjustment add-on."""
	scriptCategory: str = addonSummary

	def __init__(self, *args, **kwargs) -> None:
		"""Initializing initial configuration values ​​and other fields."""
		super(GlobalPlugin, self).__init__(*args, **kwargs)
		if appArgs.secure or config.isAppX:
			return
		confspec = {
			"step": "integer(default=1,min=1,max=20)",
			"focus": "boolean(default=true)",
			"duplicates": "boolean(default=true)",
			"advanced": "boolean(default=false)",
			"muteCompletely": "boolean(default=false)",
			"mutePercentage": "integer(default=75,min=1,max=99)",
			"unmuteOnExit": "boolean(default=true)",
			"gestures": "boolean(default=true)"
		}
		config.conf.spec[addonName] = confspec
		gui.settingsDialogs.NVDASettingsDialog.categoryClasses.append(VASettingsPanel)
		# Switching between processes
		self._index: int = 0	# index of current audio source
		# Remember the name of the audio session of the previous process
		self._previous: str = ''
		# Name of the current process
		self._process: str = ''
		# Bind default gestures if necessary
		config.conf[addonName]['gestures'] and self.bindGestures(self.__defaultGestures)
		devices.scan(cfg.devices)

	def terminate(self, *args, **kwargs) -> None:
		"""This will be called when NVDA is finished with this global plugin."""
		if config.conf[addonName]["unmuteOnExit"]:
			Thread(target=self.unmuteAllAudioSources).start()
		try:
			gui.settingsDialogs.NVDASettingsDialog.categoryClasses.remove(VASettingsPanel)
		except IndexError:
			log.warning("Can't remove %s Settings panel from NVDA settings dialogs", addonSummary)
		super(GlobalPlugin, self).terminate(*args, **kwargs)

	def event_gainFocus(self, obj: NVDAObject, NextHandler: Callable) -> None:
		"""Track the application in focus if the corresponding option is enabled.
		@param obj: the object to track if focused
		@type obj: NVDAObject
		@param nextHandler: next event handler
		@type nextHandler: Callable
		"""
		if config.conf[addonName]['focus']:
			self._index = -1
			self._previous = UNDEFINED_APP
		NextHandler()

	def selectProcessInFocus(self) -> bool:
		"""Select the name of the process that is in system focus.
		@return: whether the current process is in the list of audio sessions
		@rtype: bool
		"""
		obj = getFocusObject()
		try:
			appName = obj.appModule.appName
		except AttributeError:
			appName = UNDEFINED_APP
		session = AudioSession(appName)
		if not session.name:
			# Translators: The current application does not pay audio
			ui.message(_("{app} is not playing any sound.").format(app=appName))
			return False
		self._process = session.name
		return True

	def announceVolumeLevel(self, volumeLevel: float) -> None:
		"""Announce the current volume level.
		@param volumeLevel: value of volume level
		@type volumeLevel: float, from 0.0 to 1.0
		"""
		# Translators: The message is announced during volume control
		ui.message("%s %d" % (_("Volume"), int(volumeLevel*100)))

	def announceMuted(self) -> None:
		"""Announce that the sound was muted."""
		# Translators: The message is announced during volume control
		ui.message(_("The sound is muted"))

	def getAllSessions(self) -> List[str]:
		"""List of all running processes that available in the list of audio sessions
		excluding hidden sessions and duplicate items if the corresponding option is enabled.
		@return: list of currently running processes
		@rtype: List[str]
		"""
		procs = [s.Process.name() for s in ExtendedAudioUtilities.GetAllSessions() if s.Process and s.Process.name() and s.Process.name() not in cfg.processes]
		return list(set(procs)) if config.conf[addonName]['duplicates'] else procs

	def unmuteAllAudioSources(self) -> None:
		"""Unmute all muted audio devices and audio sessions."""
		for device in devices:
			device.isMuted and device.unmute()
		for sessionName in self.getAllSessions():
			session = AudioSession(sessionName)
			session.isMuted and session.unmute()

	def selectAudioSource(self, sessions: List[str]) -> None:
		"""Select audio source to adjust its volume level.
		This can be a physical audio device or a running process.
		@param sessions: filtered list of all running processes, changes dynamically
		@type sessions: List[str]
		"""
		if 0<=self._index < len(devices):
			title: str = devices[self._index].name
			if devices[self._index].default:
		# Translators: Used as the prefix to default audio device name
				title = "{default}: {title}".format(default=_("Default audio device"), title=title)
		else:
			try:
				self._process = sessions[self._index-len(devices)]
			except IndexError:
				try:
					self._process = sessions[-1]
				except IndexError:
					self._process = UNDEFINED_APP
			self._previous = self._process
			title = AudioSession(self._process).title
		ui.message(title)

	def getAudioSource(self) -> Union[AudioDevice, AudioSession]:
		"""Get the object of selected audio source (device or process),
		this can be instance inherited from the audiocore.AudioSource class.
		Also announces the name of the audio session at the first treatment.
		@return: instance of selected audio source
		@rtype: Union[AudioDevice, AudioSession]
		"""
		if 0<=self._index<len(devices):
			source: Union[AudioDevice, AudioSession] = devices[self._index]
			self._previous = UNDEFINED_APP
		else:
			source = AudioSession(self._process)
			if source.name!=self._previous:
				ui.message(source.title)
				self._previous = source.name
		return source

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Increase the volume"))
	def script_volumeUp(self, gesture: InputGesture) -> None:
		"""Increase the volume of the selected audio source.
		@param gesture: the input gesture in question
		@type gesture: InputGesture
		"""
		if self._index<0 and not self.selectProcessInFocus():
			return
		self.announceVolumeLevel(self.getAudioSource().volumeUp())

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Decrease the volume"))
	def script_volumeDown(self, gesture: InputGesture) -> None:
		"""Decrease the volume of the selected audio source.
		@param gesture: the input gesture in question
		@type gesture: InputGesture
		"""
		if self._index<0 and not self.selectProcessInFocus():
			return
		source = self.getAudioSource()
		volumeLevel = source.volumeDown()
		if volumeLevel>0.0:
			self.announceVolumeLevel(volumeLevel)
			return
		source.mute()
		self.announceMuted()

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Set maximum volume level"))
	def script_volumeMax(self, gesture: InputGesture) -> None:
		"""Set the maximum volume level for the selected audio source.
		@param gesture: the input gesture in question
		@type gesture: InputGesture
		"""
		if self._index<0 and not self.selectProcessInFocus():
			return
		self.announceVolumeLevel(self.getAudioSource().volumeMax())

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Set minimum volume level"))
	def script_volumeMin(self, gesture: InputGesture) -> None:
		"""Set the minimum volume level for the selected audio source.
		@param gesture: the input gesture in question
		@type gesture: InputGesture
		"""
		if self._index<0 and not self.selectProcessInFocus():
			return
		self.announceVolumeLevel(self.getAudioSource().volumeMin())

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Mute selected audio source"))
	def script_mute(self, gesture: InputGesture) -> None:
		"""Mute or unmute the selected audio source.
		@param gesture: gesture assigned to this method
		@type gesture: InputGesture
		"""
		if self._index<0 and not self.selectProcessInFocus():
			return
		source = self.getAudioSource()
		if source.isMuted:
			source.unmute()
			self.announceVolumeLevel(source.volumeLevel)
		else:
			source.mute()
			self.announceMuted()

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Switch to the next audio source"))
	def script_next(self, gesture: InputGesture) -> None:
		"""Switch to the next audio source (audio device or process).
		@param gesture: the input gesture in question
		@type gesture: InputGesture
		"""
		sessions: List[str] = self.getAllSessions()
		if self._index<0:
			try:
				self._index = len(devices) + sessions.index(next(filter(lambda s: self._process in s, sessions), ''))
			except (ValueError, TypeError):
				self._index = len(devices)-1
		self._index = self._index+1 if self._index<(len(devices)+len(sessions)-1) else 0
		self.selectAudioSource(sessions)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Switch to the previous audio source"))
	def script_prev(self, gesture: InputGesture) -> None:
		"""Switch to the previous audio source (audio device or process).
		@param gesture: the input gesture in question
		@type gesture: InputGesture
		"""
		sessions: List[str] = self.getAllSessions()
		if self._index<0:
			try:
				self._index = len(devices) + sessions.index(next(filter(lambda s: self._process in s, sessions), ''))
			except (ValueError, TypeError):
				pass
		self._index = self._index-1 if self._index>0 else len(devices)+len(sessions)-1
		self.selectAudioSource(sessions)

	def setOutputDevice(self, name: str) -> None:
		"""Switche the NVDA output to the audio device with the specified name.
		@param name: name of the audio output device
		@type name: str
		"""
		config.conf['speech']['outputDevice'] = name
		status: bool = setSynth(getSynth().name)
		if status:
			tones.terminate()
			tones.initialize()
		ui.message(name)

	def selectOutputDevice(self, step: int) -> str:
		"""Select an audio device from the list with an offset to the specified step.
		@param step: offset step in the list of available audio devices
		@type step: int (usually 1 or -1)
		@return: the name of the selected audio device
		@rtype: str
		"""
		devices: List[str] = getOutputDeviceNames()
		if devices[0] in ("", "Microsoft Sound Mapper"):
			# Translators: name for default (Microsoft Sound Mapper) audio output device.
			devices[0] = _("Microsoft Sound Mapper")
		try:
			current: int = devices.index(config.conf["speech"]["outputDevice"])
		except ValueError:
			current = 0
		return devices[(current+step)%len(devices)]

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Next audio output device"))
	def script_nextOutputDevice(self, gesture: InputGesture) -> None:
		"""Switch the output to the next available audio device.
		@param gesture: the input gesture in question
		@type gesture: InputGesture
		"""
		device: str = self.selectOutputDevice(step=1)
		self.setOutputDevice(name=device)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Previous audio output device"))
	def script_prevOutputDevice(self, gesture: InputGesture) -> None:
		"""Switch the output to the previous available audio device.
		@param gesture: the input gesture in question
		@type gesture: InputGesture
		"""
		device: str = self.selectOutputDevice(step=-1)
		self.setOutputDevice(name=device)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Switch the output to the selected audio device"))
	def script_switchTo(self, gesture: InputGesture) -> None:
		"""Switch NVDA audio output to the selected sound device.
		@param gesture: gesture assigned to this method
		@type gesture: InputGesture
		"""
		index = int(gesture.displayName.lower()[-2:].replace('f',''))-1
		self.setOutputDevice(name=getOutputDeviceNames()[index])


	__defaultGestures = {
		"kb:NVDA+windows+upArrow": "volumeUp",
		"kb:NVDA+windows+downArrow": "volumeDown",
		"kb:NVDA+windows+home": "volumeMax",
		"kb:NVDA+windows+end": "volumeMin",
		"kb:NVDA+windows+escape": "mute",
		"kb:NVDA+windows+rightArrow": "next",
		"kb:NVDA+windows+leftArrow": "prev",
		"kb:NVDA+windows+pageUp": "nextOutputDevice",
		"kb:NVDA+windows+pageDown": "prevOutputDevice"
	}
	for key in range(1, min(len(getOutputDeviceNames()), 12)+1):
		__defaultGestures["kb:NVDA+windows+f%d" % key] = "switchTo"
