#audiocore.py
# The main components for working with system audio devices and audio sessions of running processes
# A part of the NVDA Volume Adjustment add-on
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.
# Copyright (C) 2020 Olexandr Gryshchenko <grisov.nvaccess@mailnull.com>

import json
from os import path
from threading import Thread
from globalVars import appArgs
from ctypes import cast, POINTER
from comtypes import CoCreateInstance, CLSCTX_ALL, CLSCTX_INPROC_SERVER
from .pycaw import AudioUtilities, IAudioEndpointVolume, CLSID_MMDeviceEnumerator, IMMDeviceEnumerator, EDataFlow, ERole


class ExtendedAudioUtilities(AudioUtilities):
	"""Improved Audio Utilities object which gives more opportunities."""

	@staticmethod
	def GetSpeaker(id:str=None):
		"""Get speakers by its ID (render + multimedia) device.
		@param id: audio device ID
		@type id: str or None
		@return: pointer to the detected audio device
		@rtype: POINTER(POINTER(IMMDevice))
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


class AudioDevice(object):
	"""Presentation of one audio device."""

	def __init__(self, id:str='', name:str='', volume=None):
		"""The main properties of an audio device.
		@param id: audio device ID
		@type id: str or None
		@param name: human friendly name of audio device
		@type name: str
		@param volume: pointer on the interface to adjust the volume of the audio device
		@type volume: POINTER(IAudioEndpointVolume)
		"""
		self._id = id
		self._name = name
		self._volume = volume
		self._default = False

	# Accessors: getter-methods for obtaining class field values
	id = lambda self: self._id
	name = lambda self: self._name
	volume = lambda self: self._volume
	default = lambda self: self._default

	# The main properties of the audio device
	id = property(id)
	name = property(name)
	volume = property(volume)
	default = property(default)


class AudioDevices(object):
	"""Detection and presentation of all system audio devices."""

	def __init__(self):
		"""Initial values of default audio device and a list of all detected devices."""
		self._defaultDevice = AudioDevice()
		self._devices = []

	def initialize(self, hide:list=[]) -> None:
		"""Detect audio devices and save them in the list.
		Should running in a separate thread to avoid blocking NVDA.
		@param hide: a list of device IDs that needs to hide
		@type hide: list
		"""
		self._defaultDevice = AudioUtilities.GetSpeakers()
		self._devices = []
		try:
			mixers = ExtendedAudioUtilities.GetAllDevices()
		except Exception:
			mixers = []
		for mixer in mixers:
			device = ExtendedAudioUtilities.GetSpeaker(mixer.id)
			try:
				interface = device.Activate(
					IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
			except Exception:
				continue
			device = AudioDevice(
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
			default = AudioUtilities.GetSpeakers()
			device = AudioDevice(
				id = default.GetId(),
				name = ' ',
				volume = cast(default.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None), POINTER(IAudioEndpointVolume))
			)
			device._default = True
			self._devices.insert(0, device)

	def scan(self, hide:list=[]) -> None:
		"""Search for available audio devices in the system and save them in the current object.
		@param hide: a list of device IDs that needs to hide
		@type hide: list
		"""
		scan = Thread(target=self.initialize, args=[hide])
		scan.start()

	def __len__(self) -> int:
		"""The number of audio devices detected in the system.
		@return: number of audio devices
		@rtype: int
		"""
		return len(self._devices)

	def __getitem__(self, index:int) -> AudioDevice:
		"""Return the audio device by its sequence number in the list.
		@param index: the index of the device in the sequence of detected audio devices
		@type index: int
		@return: audio device from the list
		@rtype: AudioDevice
		"""
		return self._devices[index]


class AudioSession(object):
	"""Object for working with the audio session of a separate running process."""

	def __init__(self, name:str):
		"""Initialize an audio session.
		@param name: the name of the running process
		@type name: str
		"""
		self._sessions = [session for session in AudioUtilities.GetAllSessions() if session.Process and session.Process.name()]
		self._current = self.selectAudioSession(name)
		self._name = ''
		self._volume = None

	def selectAudioSession(self, name:str):
		"""Find and return an audio session by its specified name.
		@param name: full name or part of the process name
		@type name: str
		@return: an audio session related to a given process
		@rtype: pycaw.AudioSession
		"""
		return next(filter(lambda s: name.lower() in s.Process.name().lower(), self._sessions), None)

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
	def volume(self):
		"""An object used to control the volume level of the current running process.
		@return: pointer to control the volume of the selected running process
		@rtype: ISimpleAudioVolume
		"""
		if not self._volume:
			self._volume = self._current.SimpleAudioVolume
		return self._volume


class HiddenSources(object):
	"""Lists of devices and processes that need to be hidden."""

	def __init__(self):
		"""File name for saving data and loading previously saved data."""
		self._file = path.join(appArgs.configPath, path.basename(path.dirname(__file__)) + '.json')
		self._data = {}
		self.load()

	def load(self):
		"""Load previously saved data.
		@return: updated self object
		@rtype: core.HiddenSources
		"""
		try:
			with open(self._file, 'r', encoding='utf-8') as f:
				self._data = json.load(f)
		except Exception:
			pass
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
	def devices(self) -> dict:
		"""Return a set of audio devices that need to be hidden.
		@return: dict, in which the key is the device ID and value is its name
		@rtype: dict
		"""
		return self._data.get("devices", {})

	@devices.setter
	def devices(self, devices:dict):
		"""Update a list of devices that needs to hide.
		@param devices: dict with devices in which the key is the ID and the value is the device name
		@type devices: dict
		@return: updated self object
		@rtype: core.HiddenSources
		"""
		self._data['devices'] = devices
		return self

	@property
	def processes(self) -> list:
		"""List of processes that need to be hidden.
		@return: list of full names of processes
		@rtype: list
		"""
		return self._data.get("processes", [])

	@processes.setter
	def processes(self, processes:list):
		"""Update the list of processes to hide.
		@param processes: list of the full names of processes
		@type processes: list
		@return: updated self object
		@rtype: core.HiddenSources
		"""
		self._data['processes'] = list(processes)
		return self

	def isChangedDevices(self, devices:dict) -> bool:
		"""Determine if the new list of audio devices differs from the existing one.
		@param devices: dict with devices in which the key is the ID and the value is the device name
		@type devices: dict
		@return: indication of whether the data are different
		@rtype: bool
		"""
		return set(self.devices)^set(devices)

	def isChangedProcesses(self, processes:list) -> bool:
		"""Determine if the new processes list differs from the existing one.
		@param processes: list of the full names of processes
		@type processes: list
		@return: indication of whether the data are different
		@rtype: bool
		"""
		return set(self.processes)^set(processes)


# global instances to avoid multiple scans of all audio devices
devices = AudioDevices()
hidden = HiddenSources()
