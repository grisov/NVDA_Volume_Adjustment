#audiocore.py
# The main components for working with system audio devices and audio sessions of running processes
# A part of the NVDA Volume Adjustment add-on
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.
# Copyright (C) 2020-2021 Olexandr Gryshchenko <grisov.nvaccess@mailnull.com>

from __future__ import annotations
from typing import Optional, Callable, List, Dict, Union, Generator
import json
from os import path
from threading import Thread
from globalVars import appArgs
import config
from ctypes import cast, POINTER
from comtypes import CoCreateInstance, CLSCTX_ALL, CLSCTX_INPROC_SERVER, pointer
from . import pycaw

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
		@return: collection of audio devices IDs
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
		return bool(set(self.devices)^set(devices))

	def isChangedProcesses(self, processes: List[str]) -> bool:
		"""Determine if the new processes list differs from the existing one.
		@param processes: list of the full names of processes
		@type processes: List[str]
		@return: indication of whether the data are different
		@rtype: bool
		"""
		return bool(set(self.processes)^set(processes))

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

	def delMuted(self, name: str) -> Configuration:
		"""Remove name of the audio source from the list of muted.
		@param name: the name of the audio session or ID of the audio device
		@type name: str
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


class ExtendedAudioUtilities(pycaw.AudioUtilities):
	"""Improved Audio Utilities object which gives more opportunities."""

	@staticmethod
	def GetSpeaker(id: Optional[str]=None) -> pycaw.IMMDevice:
		"""Get speakers by its ID (render + multimedia) device.
		@param id: audio device ID
		@type id: str
		@return: pointer to the detected audio device
		@rtype: pycaw.IMMDevice
		"""
		device_enumerator = CoCreateInstance(
			pycaw.CLSID_MMDeviceEnumerator,
			pycaw.IMMDeviceEnumerator,
			CLSCTX_INPROC_SERVER)
		if id is not None:
			speakers = device_enumerator.GetDevice(id)
		else:
			speakers = device_enumerator.GetDefaultAudioEndpoint(pycaw.EDataFlow.eRender.value, pycaw.ERole.eMultimedia.value)
		return speakers


class AudioSource(object):
	"""Represents the basic properties of audio source."""

	def __init__(self,
		id: str,
		name: str,
		volume: Union[pycaw.ISimpleAudioVolume, pycaw.IAudioEndpointVolume, None] = None) -> None:
		"""The main properties of an audio source.
		@param id: audio source ID (audio device ID or audio session name)
		@type id: str
		@param name: name of audio source
		@type name: str
		@param volume: pointer on the interface to adjust the volume of the audio source
		@type volume: Union[pycaw.ISimpleAudioVolume, pycaw.IAudioEndpointVolume, None]
		"""
		self._id = id
		self._name = name
		self._volume = volume

	@property
	def id(self) -> str:
		"""ID of the current audio source.
		@return: device ID or audio session name
		@rtype: str
		"""
		return self._id

	@property
	def name(self) -> str:
		"""Name of the current audio source.
		@return: audio source name
		@rtype: str
		"""
		return self._name

	@property
	def volume(self) -> Union[pycaw.ISimpleAudioVolume, pycaw.IAudioEndpointVolume, None]:
		"""An object that gives access to control the volume of the sound source.
		@return: volume control object
		@rtype: Union[pycaw.ISimpleAudioVolume, pycaw.IAudioEndpointVolume, None]
		"""
		return self._volume

	def volumeControl(self, volumeControlFunction: str) -> Callable:
		"""Link to the audio source volume level setting function.
		Used due to the difference between the appropriate methods in audio devices and audio sessions.
		@param volumeControlFunction: name of the volume control function
		@type volumeControlFunction: str
		@return: link to the volume control function
		@rtype: Callable
		"""
		return getattr(self.volume, volumeControlFunction, lambda: None)

	@property
	def volumeLevel(self) -> float:
		"""Get the volume level of the sound source.
		The method must be overridden for each type of sound source.
		@return: current volume level
		@rtype: float
		"""
		raise NotImplementedError("This property must be overridden in the child class!")

	@volumeLevel.setter
	def volumeLevel(self, level: float) -> None:
		"""Set the volume level of the sound source.
		The method must be overridden for each type of sound source.
		@param level: target volume level
		@type level: float
		"""
		raise NotImplementedError("This property must be overridden in the child class!")

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
		state = False if self.volume is None else self.volume.GetMute() 
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
				# The getattr() function is used for correct processing by the MyPy analyzer
				getattr(self.volume, 'SetMute')(True, None)
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
			# The getattr() function is used for correct processing by the MyPy analyzer
			getattr(self.volume, 'SetMute')(False, None)
			if self.isMuted:
				self.volumeLevel = min(1.0, round(self.volumeLevel*100.0)/(100.0-config.conf[addonName]['mutePercentage']))
		except AttributeError:
			return False
		else:
			cfg.delMuted(self.id).save()
			return True


class AudioDevice(AudioSource):
	"""Presentation of one audio device."""

	def __init__(self,
		id: str = '',
		name: str = '',
		volume: pointer[pycaw.IAudioEndpointVolume] = None) -> None:
		"""The main properties of an audio device.
		@param id: audio device ID
		@type id: str
		@param name: human friendly name of audio device
		@type name: str
		@param volume: pointer on the interface to adjust the volume of the audio device
		@type volume: pointer[pycaw.IAudioEndpointVolume]
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
		self._devices: List[AudioDevice] = []

	def initialize(self, hide: Dict[str, str]={}) -> AudioDevices:
		"""Detect audio devices and save them in the list.
		Should running in a separate thread to avoid blocking NVDA.
		@param hide: a collection of devices that needs to hide
		@type hide: Dict[str, str]
		@return: collection of the detected audio devices
		@rtype: AudioDevices
		"""
		defaultDevice: pycaw.IMMDevice = pycaw.AudioUtilities.GetSpeakers()
		self._devices = []
		if config.conf[addonName]['advanced']:
			try:
				mixers: List[pycaw.AudioDevice] = [mx for mx in ExtendedAudioUtilities.GetAllDevices() if mx]
			except Exception:
				mixers = []
			for mixer in mixers:
				immDevice: pycaw.IMMDevice = ExtendedAudioUtilities.GetSpeaker(mixer.id)
				try:
					interface = immDevice.Activate(
						pycaw.IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
				except Exception:
					continue
				device = AudioDevice(
					id = mixer.id or '',
					name = mixer.FriendlyName or mixer.id or '',
					volume = cast(interface, POINTER(pycaw.IAudioEndpointVolume))
				)
				if device.id and device.name and device.id not in hide:
					if device.id==defaultDevice.GetId():
						device._default = True
						self._devices.insert(0, device)
					else:
						self._devices.append(device)
		# Insert to the list the default audio output device if it is not listed
		# for some reason on some systems it is not determined in the standard way
		if not next(filter(lambda d: d.default, self._devices), None):
			device = AudioDevice(
				id = defaultDevice.GetId() or '',
				name = self.getDeviceNameByID(defaultDevice.GetId()) or '',
				volume = cast(defaultDevice.Activate(pycaw.IAudioEndpointVolume._iid_, CLSCTX_ALL, None), POINTER(pycaw.IAudioEndpointVolume))
			)
			device._default = True
			self._devices.insert(0, device)
		return self

	def getDeviceNameByID(self, id: Optional[str]) -> str:
		"""Get the name of the audio device by its ID.
		@param id: audio device ID
		@type id: Optional[str]
		@return: human friendly name of audio device or empty string
		@rtype: str
		"""
		try:
			mixers: List[pycaw.AudioDevice] = [mx for mx in ExtendedAudioUtilities.GetAllDevices() if mx]
		except Exception:
			mixers = []
		mixer = next(filter(lambda m: m.id==id, mixers), None)
		return mixer.FriendlyName if mixer else ' '

	def scan(self, hide: Dict[str, str]={}) -> None:
		"""Search for available audio devices in the system and save them in the current object.
		@param hide: a collection of audio devices that needs to hide
		@type hide: Dict[str, str]
		"""
		Thread(target=self.initialize, args=[hide]).start()

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

	def __iter__(self) -> Generator[AudioDevice, None, None]:
		"""Iteration through all detected audio devices.
		@return: generator of all detected audio devices
		@rtype: Generator[AudioDevice, None, None]
		"""
		for device in self._devices:
			yield device


class AudioSession(AudioSource):
	"""Object for working with the audio session of a separate running process."""

	def __init__(self, name: str) -> None:
		"""Initialize an audio session.
		@param name: the name of the running process
		@type name: str
		"""
		self._sessions: List[pycaw.AudioSession] = [session for session in pycaw.AudioUtilities.GetAllSessions() if session.Process and session.Process.name()]
		self._current: pycaw.AudioSession = self.selectAudioSession(name)
		super(AudioSession, self).__init__(id=name, name='', volume=None)

	def selectAudioSession(self, name: str = 'nvda.exe') -> pycaw.AudioSession:
		"""Find and return an audio session by its specified name.
		@param name: full name or part of the process name
		@type name: str
		@return: an audio session related to a given process
		@rtype: pycaw.AudioSession
		"""
		return next(filter(lambda s: name.lower() in s.Process.name().lower(), self._sessions),
			next(filter(lambda s: 'nvda.exe' in s.Process.name().lower(), self._sessions),
				self._sessions[0]))

	@property
	def name(self) -> str:
		"""Getter method - returns the full name of the current process.
		@return: name of the current running process
		@rtype: str
		"""
		if not self._name:
			try:
				self._name = self._current.Process.name()
			except AttributeError:
				self._name = ''
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
	def volume(self) -> Union[pycaw.ISimpleAudioVolume, pycaw.IAudioEndpointVolume, None]:
		"""Pointer used to control the volume level of the current running process.
		@return: pointer to control the volume of the selected running process
		@rtype: Union[pycaw.ISimpleAudioVolume, pycaw.IAudioEndpointVolume, None]
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
