#core.py
# The main components for working with system audio devices and audio sessions of running processes
# A part of NonVisual Desktop Access (NVDA)
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.
# Copyright (C) 2020 Olexandr Gryshchenko <grisov.nvaccess@mailnull.com>

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

	def initialize(self) -> None:
		"""Detect audio devices and save them in the list.
		Should running in a separate thread to avoid blocking NVDA.
		"""
		self._defaultDevice = AudioUtilities.GetSpeakers()
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
				name = mixer.FriendlyName,
				volume = cast(interface, POINTER(IAudioEndpointVolume))
			)
			if device.id==self._defaultDevice.GetId():
				device._default = True
				self._devices.insert(0, device)
			else:
				self._devices.append(device)

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
		self._name = name
		self._volume = None

	@property
	def name(self) -> str:
		"""Getter method - returns the full name of the current process.
		@return: name of the current running process
		@rtype: str
		"""
		return self._name

	@property
	def title(self) -> str:
		"""Getter method - returns human friendly name of the current process.
		@return: human friendly name of the current running process
		@rtype: str
		"""
		return ' '.join(self.name.split('.')[:-1])

	@property
	def volume(self):
		"""An object used to control the volume level of the current running process.
		@return: pointer to control the volume of the selected running process
		@rtype: ISimpleAudioVolume
		"""
		if not self._volume:
			for session in AudioUtilities.GetAllSessions():
				if session.Process and session.Process.name()==self.name:
					self._volume = session.SimpleAudioVolume
		return self._volume
