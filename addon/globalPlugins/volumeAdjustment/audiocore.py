#audiocore.py
# The main components for working with system audio devices and audio sessions of running processes
# A part of the NVDA Volume Adjustment add-on
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.
# Copyright (C) 2020-2021 Olexandr Gryshchenko <grisov.nvaccess@mailnull.com>

from __future__ import annotations
from typing import Optional, Callable, List, Dict
import json
from os import path
from threading import Thread
from globalVars import appArgs
import config
from ctypes import cast, POINTER
from comtypes import CoCreateInstance, CLSCTX_ALL, CLSCTX_INPROC_SERVER
from .pycaw import AudioUtilities, IAudioEndpointVolume, CLSID_MMDeviceEnumerator, IMMDeviceEnumerator, EDataFlow, ERole

addonName = path.basename(path.dirname(__file__))


class Configuration(object):
	"""Collection of devices and processes that need to be hidden,
	and list of muted audio sources.
	"""

	def __init__(self) -> None:
		"""File name for saving data and loading previously saved data."""
		self._file = path.join(appArgs.configPath, path.basename(path.dirname(__file__)) + '.json')
		self._data: Dict = {}
		self.load()

	def load(self) -> Configuration:
		"""Load previously saved data.
		@return: updated self object
		@rtype: Configuration
		"""
		try:
			with open(self._file, 'r', encoding='utf-8') as f:
				self._data = json.load(f)
		except Exception:
			pass
		if 'version' not in self._data:
			self._data = {'version': 0}
		return self

	def save(self) -> bool:
		"""Save the data to an external file.
		@return: whether the data has been successfully saved
		@rtype: bool
		"""
		try:
			with open(self._file, 'w', encoding='utf-8') as f:
				f.write(json.dumps(self._data, skipkeys=True, ensure_ascii=False, indent=4))
		except Exception:
			return False
		return True

	@property
	def devices(self) -> Dict[str, str]:
		"""Return a set of audio devices that need to be hidden.
		@return: dict, in which the key is the device ID and value is its name
		@rtype: Dict[str, str]
		"""
		return self._data.get("devices", {})

	@devices.setter
	def devices(self, devices: Dict[str, str]) -> Configuration:
		"""Update a list of devices that needs to hide.
		@param devices: dict with devices in which the key is the ID and the value is the device name
		@type devices: Dict[str, str]
		@return: updated self object
		@rtype: Configuration
		"""
		self._data['devices'] = devices
		return self

	@property
	def processes(self) -> List[str]:
		"""List of processes that need to be hidden.
		@return: list of full names of processes
		@rtype: List[str]
		"""
		return self._data.get("processes", [])

	@processes.setter
	def processes(self, processes: List[str]) -> Configuration:
		"""Update the list of processes to hide.
		@param processes: list of the full names of processes
		@type processes: List[str]
		@return: updated self object
		@rtype: Configuration
		"""
		self._data['processes'] = list(processes)
		return self

	def isChangedDevices(self, devices: Dict[str, str]) -> bool:
		"""Determine if the new list of audio devices differs from the existing one.
		@param devices: dict with devices in which the key is the ID and the value is the device name
		@type devices: Dict[str, str]
		@return: indication of whether the data are different
		@rtype: bool
		"""
		return set(self.devices)^set(devices)

	def isChangedProcesses(self, processes: List[str]) -> bool:
		"""Determine if the new processes list differs from the existing one.
		@param processes: list of the full names of processes
		@type processes: List[str]
		@return: indication of whether the data are different
		@rtype: bool
		"""
		return set(self.processes)^set(processes)

	@property
	def muted(self) -> List[str]:
		"""List of audio sources that have been muted by the methods of this add-on.
		@return: list of names of audio sessions and IDs of audio devices
		@rtype: List[str]
		"""
		return self._data.get("muted", [])

	def addMuted(self, name: Optional[str]) -> Configuration:
		"""Add name of the audio source to the collection of muted.
		@param name: name of the audio session or ID of the audio device
		@type name: Optional[str]
		@return: the current object instance for further reference to its attributes
		@rtype: Configuration
		"""
		if name and name not in self.muted:
			self.muted.append(name)
			self._data["muted"] = self.muted
		return self

	def delMuted(self, name: Optional[str]) -> Configuration:
		"""Remove name of the audio source from the list of muted.
		@param name: the name of the audio session or ID of the audio device
		@type name: Optional[str]
		@return: the current object instance for further reference to its attributes
		@rtype: Configuration
		"""
		try:
			self.muted.remove(name)
		except ValueError:
			pass
		else:
			self._data["muted"] = self.muted
		return self

# Global Configuration instance
cfg = Configuration()


class ExtendedAudioUtilities(AudioUtilities):
	"""Improved Audio Utilities object which gives more opportunities."""

	@staticmethod
	def GetSpeaker(id: Optional[str]=None) -> 'POINTER(POINTER(pycaw.IMMDevice))':
		"""Get speakers by its ID (render + multimedia) device.
		@param id: audio device ID
		@type id: Optional[str]
		@return: pointer to the detected audio device
		@rtype: POINTER(POINTER(pycaw.IMMDevice))
		"""
		device_enumerator = CoCreateInstance(
			CLSID_MMDeviceEnumerator,
			IMMDeviceEnumerator,
			CLSCTX_INPROC_SERVER)
		if id is not None:
			speakers = device_enumerator.GetDevice(id)
		else:
			speakers = device_enumerator.GetDefaultAudioEndpoint(EDataFlow.eRender.value, ERole.eMultimedia.value)
		return speakers


class AudioSource(object):
	"""Represents the basic properties of audio source."""

	def __init__(self,
		id: Optional[str]='',
		name: Optional[str]='',
		volume: Optional['comtypes.POINTER(ISimpleAudioVolume)']=None) -> None:
		"""The main properties of an audio source.
		@param id: audio source ID (audio device ID or audio session name)
		@type id: Optional[str]
		@param name: name of audio source
		@type name: Optional[str]
		@param volume: pointer on the interface to adjust the volume of the audio source
		@type volume: Optional[comtypes.POINTER(ISimpleAudioVolume)]
		"""
		self._id: Optional[str] = id
		self._name: Optional[str] = name
		self._volume: Optional['comtypes.POINTER(ISimpleAudioVolume)'] = volume

	# Accessors: getter-methods for obtaining class field values
	id = lambda self: self._id
	name = lambda self: self._name
	volume = lambda self: self._volume

	# The main properties of the audio device
	id = property(id)
	name = property(name)
	volume = property(volume)

	def volumeControl(self, volumeControlFunction: str) -> Callable:
		"""Link to the audio source volume level setting function.
		Used due to the difference between the appropriate methods in audio devices and audio sessions.
		@param volumeControlFunction: name of the volume control function
		@type volumeControlFunction: str
		@return: link to the volume control function
		@rtype: Callable
		"""
		try:
			return getattr(self.volume, volumeControlFunction)
		except AttributeError:
			return None

	@property
	def volumeLevel(self) -> float:
		"""Get the volume level of the sound source.
		The method must be overridden for each type of sound source.
		@return: current volume level
		@rtype: float
		"""
		return NotImplementedError

	@volumeLevel.setter
	def volumeLevel(self, level: float) -> None:
		"""Set the volume level of the sound source.
		The method must be overridden for each type of sound source.
		@param level: target volume level
		@type level: float
		"""
		return NotImplementedError

	def volumeUp(self) -> float:
		"""Increase the volume level by the specified step.
		@return: current volume level
		@rtype: float
		"""
		self.isMuted and self.unmute()
		level = self.volumeLevel = min(1.0, float(round(self.volumeLevel*100) + config.conf[addonName]["step"])/100.0)
		return level

	def volumeDown(self) -> float:
		"""Decrease the volume level by the specified step.
		@return: current volume level
		@rtype: float
		"""
		self.isMuted and self.unmute()
		level = self.volumeLevel = max(0.0, float(round(self.volumeLevel*100) - config.conf[addonName]["step"])/100.0)
		return level

	def volumeMax(self) -> float:
		"""Set the maximum volume level of the audio source.
		@return: current volume level
		@rtype: float
		"""
		self.isMuted and self.unmute()
		self.volumeLevel = 1.0
		return self.volumeLevel

	def volumeMin(self) -> float:
		"""Set the minimum volume level of the audio source.
		@return: current volume level
		@rtype: float
		"""
		self.isMuted and self.unmute()
		self.volumeLevel = 0.0
		return self.volumeLevel

	@property
	def isMuted(self) -> bool:
		"""Check whether the current audio source is muted.
		@return: a state of the audio source (muted or no)
		@rtype: bool
		"""
		try:
			state = self.volume.GetMute()
		except AttributeError:
			state = False
		if not config.conf[addonName]['muteCompletely']:
			return (self.id in cfg.muted) or state
		return state

	def mute(self) -> bool:
		"""Mute the current audio source.
		@return: a state of the audio source (muted or no)
		@rtype: bool
		"""
		try:
			if config.conf[addonName]['muteCompletely']:
				self.volume.SetMute(True, None)
			elif not self.isMuted:
				self.volumeLevel = (self.volumeLevel*(100-config.conf[addonName]['mutePercentage']))/100.0
		except AttributeError:
			return False
		else:
			cfg.addMuted(self.id).save()
			return True

	def unmute(self) -> bool:
		"""Unmute the current audio source.
		@return: a state of the audio source (muted or no)
		@rtype: bool
		"""
		try:
			if config.conf[addonName]['muteCompletely']:
				self.volume.SetMute(False, None)
			elif self.isMuted:
				self.volumeLevel = min(1.0, round(self.volumeLevel*100.0)/(100.0-config.conf[addonName]['mutePercentage']))
		except AttributeError:
			return False
		else:
			cfg.delMuted(self.id).save()
			return True


class AudioDevice(AudioSource):
	"""Presentation of one audio device."""

	def __init__(self,
		id: Optional[str]='',
		name: str='',
		volume: Optional['comtypes.POINTER(ISimpleAudioVolume)']=None) -> None:
		"""The main properties of an audio device.
		@param id: audio device ID
		@type id: Optional[str]
		@param name: human friendly name of audio device
		@type name: str
		@param volume: pointer on the interface to adjust the volume of the audio device
		@type volume: Optional[comtypes.POINTER(ISimpleAudioVolume)]
		"""
		super(AudioDevice, self).__init__(id, name, volume)
		self._default: bool = False

	@property
	def default(self) -> bool:
		"""Check if the current audio device is the default output device.
		@return: default output audio device or not
		@rtype: bool
		"""
		return self._default

	@property
	def volumeLevel(self) -> float:
		"""Get the volume level of the audio device.
		@return: current volume level
		@rtype: float [-1.0, 0.0...1.0]
		"""
		try:
			return super(AudioDevice, self).volumeControl("GetMasterVolumeLevelScalar")()
		except (AttributeError, TypeError,):
			return -1.0

	@volumeLevel.setter
	def volumeLevel(self, level: float) -> None:
		"""Set the volume level of the audio device.
		@param level: target volume level
		@type level: float [0.0...1.0]
		"""
		try:
			super(AudioDevice, self).volumeControl("SetMasterVolumeLevelScalar")(level, None)
		except (AttributeError, TypeError,):
			pass


class AudioDevices(object):
	"""Detection and presentation of all system audio devices."""

	def __init__(self) -> None:
		"""Initial values of default audio device and a list of all detected devices."""
		self._defaultDevice: AudioDevice = AudioDevice()
		self._devices: List[AudioDevice] = []

	def initialize(self, hide: List[str]=[]) -> None:
		"""Detect audio devices and save them in the list.
		Should running in a separate thread to avoid blocking NVDA.
		@param hide: a list of devices IDs that needs to hide
		@type hide: List[str]
		"""
		self._defaultDevice: 'POINTER(POINTER(pycaw.IMMDevice))' = AudioUtilities.GetSpeakers()
		self._devices: List[AudioDevice] = []
		if config.conf[addonName]['advanced']:
			try:
				mixers: List = ExtendedAudioUtilities.GetAllDevices()
			except Exception:
				mixers: List = []
			for mixer in mixers:
				device: 'POINTER(POINTER(pycaw.IMMDevice))' = ExtendedAudioUtilities.GetSpeaker(mixer.id)
				try:
					interface = device.Activate(
						IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
				except Exception:
					continue
				device: AudioDevice = AudioDevice(
					id = mixer.id,
					name = mixer.FriendlyName or mixer.id,
					volume = cast(interface, POINTER(IAudioEndpointVolume))
				)
				if device.id and device.name and device.id not in hide:
					if device.id==self._defaultDevice.GetId():
						device._default = True
						self._devices.insert(0, device)
					else:
						self._devices.append(device)
		# Insert to the list the default audio output device if it is not listed
		# for some reason on some systems it is not determined in the standard way
		if not next(filter(lambda d: d.default, self._devices), None):
			device = AudioDevice(
				id = self._defaultDevice.GetId(),
				name = self.getDeviceNameByID(self._defaultDevice.GetId()),
				volume = cast(self._defaultDevice.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None), POINTER(IAudioEndpointVolume))
			)
			device._default = True
			self._devices.insert(0, device)

	def getDeviceNameByID(self, id: Optional[str]) -> str:
		"""Get the name of the audio device by its ID.
		@param id: audio device ID
		@type id: Optional[str]
		@return: human friendly name of audio device or empty string
		@rtype: str
		"""
		try:
			mixers = AudioUtilities.GetAllDevices()
		except Exception:
			mixers = []
		mixer = next(filter(lambda m: m.id==id, mixers), None)
		return mixer.FriendlyName if mixer else ' '

	def scan(self, hide: List[str]=[]) -> None:
		"""Search for available audio devices in the system and save them in the current object.
		@param hide: a list of device IDs that needs to hide
		@type hide: List[str]
		"""
		scan = Thread(target=self.initialize, args=[hide])
		scan.start()

	def __len__(self) -> int:
		"""The number of audio devices detected in the system.
		@return: number of audio devices
		@rtype: int
		"""
		return len(self._devices)

	def __getitem__(self, index: int) -> AudioDevice:
		"""Return the audio device by its sequence number in the list.
		@param index: the index of the device in the sequence of detected audio devices
		@type index: int
		@return: audio device from the list
		@rtype: AudioDevice
		"""
		return self._devices[index]


class AudioSession(AudioSource):
	"""Object for working with the audio session of a separate running process."""

	def __init__(self, name: str) -> None:
		"""Initialize an audio session.
		@param name: the name of the running process
		@type name: str
		"""
		self._sessions: List = [session for session in AudioUtilities.GetAllSessions() if session.Process and session.Process.name()]
		self._current: 'pycaw.AudioSession' = self.selectAudioSession(name)
		super(AudioSession, self).__init__(id=name, name=None, volume=None)

	def selectAudioSession(self, name: str) -> Optional['pycaw.AudioSession']:
		"""Find and return an audio session by its specified name.
		@param name: full name or part of the process name
		@type name: str
		@return: an audio session related to a given process
		@rtype: Optional[pycaw.AudioSession]
		"""
		return next(filter(lambda s: name.lower() in s.Process.name().lower(), self._sessions), None)

	@property
	def name(self) -> Optional[str]:
		"""Getter method - returns the full name of the current process.
		@return: name of the current running process
		@rtype: Optional[str]
		"""
		if not self._name:
			try:
				self._name = self._current.Process.name()
			except AttributeError:
				self._name = None
		return self._name

	@property
	def title(self) -> str:
		"""Getter method - returns human friendly name of the current process.
		@return: human friendly name of the current running process
		@rtype: str
		"""
		try:
			name = self._current.DisplayName
		except AttributeError:
			name = None
		return name or self.name.replace('.exe', '')

	@property
	def volume(self) -> Optional['comtypes.POINTER(ISimpleAudioVolume)']:
		"""Pointer used to control the volume level of the current running process.
		@return: pointer to control the volume of the selected running process
		@rtype: Optional[comtypes.POINTER(ISimpleAudioVolume)]
		"""
		if not self._volume:
			self._volume = self._current.SimpleAudioVolume
		return self._volume

	@property
	def volumeLevel(self) -> float:
		"""Get the volume level of the audio session.
		@return: current volume level
		@rtype: float [-1.0, 0.0...1.0]
		"""
		try:
			return super(AudioSession, self).volumeControl("GetMasterVolume")()
		except (AttributeError, TypeError,):
			return -1.0

	@volumeLevel.setter
	def volumeLevel(self, level: float) -> None:
		"""Set the volume level of the audio session.
		@param level: target volume level
		@type level: float [0.0...1.0]
		"""
		try:
			super(AudioSession, self).volumeControl("SetMasterVolume")(level, None)
		except (AttributeError, TypeError,):
			pass


# global instance to avoid multiple scans of all audio devices
devices = AudioDevices()
