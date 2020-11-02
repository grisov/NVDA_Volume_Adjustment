#-*- coding:utf-8 -*-
# A part of NonVisual Desktop Access (NVDA)
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.
# Copyright (C) 2020 Olexandr Gryshchenko <grisov.nvaccess@mailnull.com>

import addonHandler
from logHandler import log
try:
	addonHandler.initTranslation()
except addonHandler.AddonError:
	log.warning("Unable to initialise translations. This may be because the addon is running from NVDA scratchpad.")

import os
_addonDir = os.path.join(os.path.dirname(__file__), "..", "..")
if isinstance(_addonDir, bytes):
	_addonDir = _addonDir.decode("mbcs")
_curAddon = addonHandler.Addon(_addonDir)
addonName = _curAddon.manifest['name']
addonSummary = _curAddon.manifest['summary']

import globalPluginHandler
import ui
import gui
import config
from scriptHandler import script
from threading import Thread
from .core import devices, AudioSession
from .pycaw import AudioUtilities
from .settings import VASettingsPanel


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	"""Implementation global commands of NVDA add-on"""
	scriptCategory = addonSummary

	def __init__(self, *args, **kwargs):
		"""Initializing initial configuration values ​​and other fields"""
		confspec = {
			"step": "integer(default=1,min=1,max=20)"
		}
		config.conf.spec[addonName] = confspec
		super(GlobalPlugin, self).__init__(*args, **kwargs)
		gui.settingsDialogs.NVDASettingsDialog.categoryClasses.append(VASettingsPanel)
		# Variables initialization for using Core Audio Windows API
		self._devices = devices
		# Switch between processes
		self._index = 0
		self._selectedProcess = ''
		Thread(target=self._devices.initialize).start()

	def terminate(self, *args, **kwargs):
		"""This will be called when NVDA is finished with this global plugin"""
		super().terminate(*args, **kwargs)
		try:
			gui.settingsDialogs.NVDASettingsDialog.categoryClasses.remove(VASettingsPanel)
		except IndexError:
			log.warning("Can't remove %s Settings panel from NVDA settings dialogs", _addonSummary)

	@property
	def step(self) -> float:
		"""***
		"""
		return float(config.conf[addonName]['step'])/100.

	def announceVolumeLevel(self, volumeLevel: float) -> None:
		"""Announce the current volume level.
		@param volumeLevel: value of volume level
		@type volumeLevel: float, from 0.0 to 1.0
		"""
		# Translators: The message is announced during volume control
		ui.message("%s %d" % (_("Volume"), int(volumeLevel*100)))

	def announceIsMuted(self) -> None:
		"""Announce that the sound was muted."""
		# Translators: The message is announced during volume control
		ui.message(_("The sound is muted"))

	def increaseSession(self, name:str) -> float:
		"""Increase the volume level for a running process with a given name.
		@param name: the full name of the running process
		@type name: str
		@return: current volume level
		@rtype: float
		"""
		session = AudioSession(name)
		volumeLevel = session.volume.GetMasterVolume()
		if volumeLevel<=self.step and session.volume.GetMute():
			session.volume.SetMute(False, None)
		volumeLevel = min(1.0, volumeLevel + self.step)
		session.volume.SetMasterVolume(volumeLevel, None)
		return volumeLevel

	def decreaseSession(self, name:str) -> float:
		"""Decrease the volume level for a running process with a given name.
		@param name: the full name of the running process
		@type name: str
		@return: current volume level
		@rtype: float
		"""
		session = AudioSession(name)
		volumeLevel = session.volume.GetMasterVolume()
		volumeLevel = max(0.0, volumeLevel - self.step)
		if volumeLevel > 0.0:
			session.volume.SetMasterVolume(volumeLevel, None)
			self.announceVolumeLevel(volumeLevel)
		else:
			session.volume.SetMute(True, None)
			self.announceIsMuted()
		return volumeLevel

	def increaseDevice(self) -> float:
		"""Increase the volume level for selected audio device.
		@return: current volume level
		@rtype: float
		"""
		device = self._devices[self._index]
		volumeLevel = device.volume.GetMasterVolumeLevelScalar()
		if volumeLevel<=self.step and device.volume.GetMute():
			device.volume.SetMute(False, None)
		volumeLevel = min(1.0, volumeLevel + self.step)
		device.volume.SetMasterVolumeLevelScalar(volumeLevel, None)
		return volumeLevel

	def decreaseDevice(self) -> float:
		"""Decrease the volume level for selected audio device.
		@return: current volume level
		@rtype: float
		"""
		device = self._devices[self._index]
		volumeLevel = device.volume.GetMasterVolumeLevelScalar()
		volumeLevel = max(0.0, volumeLevel - self.step)
		if volumeLevel > 0.0:
			device.volume.SetMasterVolumeLevelScalar(volumeLevel, None)
			self.announceVolumeLevel(volumeLevel)
		else:
			device.volume.SetMute(True, None)
			self.announceIsMuted()
		return volumeLevel

	def selectAudioSource(self, sessions:list) -> None:
		"""Select audio source to adjust its volume level.
		This can be a physical audio device or a running process.
		@param sessions: list of all running processes, changes dynamically
		@type sessions: list
		"""
		if self._index < len(self._devices):
			title = self._devices[self._index].name
			if self._devices[self._index].default:
		# Translators: Used as the prefix to default audio device name
				title = "{default}: {title}".format(default=_("Default audio device"), title=title)
		else:
			try:
				self._selectedProcess = sessions[self._index-len(self._devices)].Process.name()
			except IndexError:
				pass
			title = AudioSession(self._selectedProcess).title
		ui.message(title)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Increase the volume"))
	def script_volumeUp(self, gesture) -> None:
		"""Increase the volume of the selected audio source.
		@param gesture: the input gesture in question
		@type gesture: L{inputCore.InputGesture}
		"""
		if self._index<len(self._devices):
			volumeLevel = self.increaseDevice()
		else:
			volumeLevel = self.increaseSession(self._selectedProcess)
		self.announceVolumeLevel(volumeLevel)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Decrease the volume"))
	def script_volumeDown(self, gesture) -> None:
		"""Decrease the volume of the selected audio source.
		@param gesture: the input gesture in question
		@type gesture: L{inputCore.InputGesture}
		"""
		if self._index<len(self._devices):
			self.decreaseDevice()
		else:
			self.decreaseSession(self._selectedProcess)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Set maximum volume level"))
	def script_volumeMax(self, gesture) -> None:
		"""Set the maximum volume level for the selected audio source.
		@param gesture: the input gesture in question
		@type gesture: L{inputCore.InputGesture}
		"""
		if self._index<len(self._devices):
			if self._devices[self._index].volume.GetMute():
				self._devices[self._index].volume.SetMute(False, None)
			self._devices[self._index].volume.SetMasterVolumeLevelScalar(1.0, None)
			volumeLevel = self._devices[self._index].volume.GetMasterVolumeLevelScalar()
		else:
			session = AudioSession(self._selectedProcess)
			if session.volume.GetMute():
				session.volume.SetMute(False, None)
			session.volume.SetMasterVolume(1.0, None)
			volumeLevel = session.volume.GetMasterVolume()
		self.announceVolumeLevel(volumeLevel)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Set minimum volume level"))
	def script_volumeMin(self, gesture) -> None:
		"""Set the minimum volume level for the selected audio source.
		@param gesture: the input gesture in question
		@type gesture: L{inputCore.InputGesture}
		"""
		if self._index<len(self._devices):
			self._devices[self._index].volume.SetMasterVolumeLevelScalar(0.0, None)
			volumeLevel = self._devices[self._index].volume.GetMasterVolumeLevelScalar()
		else:
			session = AudioSession(self._selectedProcess)
			session.volume.SetMasterVolume(0.0, None)
			volumeLevel = session.volume.GetMasterVolume()
		self.announceVolumeLevel(volumeLevel)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Switch to the next audio source"))
	def script_nextProcess(self, gesture) -> None:
		"""Switch to the next audio source (audio device or process).
		@param gesture: the input gesture in question
		@type gesture: L{inputCore.InputGesture}
		"""
		sessions = [s for s in AudioUtilities.GetAllSessions() if s.Process and s.Process.name]
		self._index = self._index+1 if self._index<(len(self._devices)+len(sessions)-1) else 0
		self.selectAudioSource(sessions)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Switch to the previous audio source"))
	def script_prevProcess(self, gesture) -> None:
		"""Switch to the previous audio source (audio device or process).
		@param gesture: the input gesture in question
		@type gesture: L{inputCore.InputGesture}
		"""
		sessions = [s for s in AudioUtilities.GetAllSessions() if s.Process and s.Process.name]
		self._index = self._index-1 if self._index>0 else len(self._devices)+len(sessions)-1
		self.selectAudioSource(sessions)

	__gestures = {
		"kb:NVDA+windows+upArrow": "volumeUp",
		"kb:NVDA+windows+downArrow": "volumeDown",
		"kb:NVDA+windows+home": "volumeMax",
		"kb:NVDA+windows+end": "volumeMin",
		"kb:NVDA+windows+rightArrow": "nextProcess",
		"kb:NVDA+windows+leftArrow": "prevProcess"
	}
