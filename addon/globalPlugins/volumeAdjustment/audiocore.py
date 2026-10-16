# audiocore.py
# The main components for working with system audio devices and audio sessions of running processes
# A part of the NVDA Volume Adjustment add-on
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.
# Copyright (C) 2020-2026 Oleksandr Gryshchenko <grisov.nvaccess@mailgw.com>

from __future__ import annotations
import json
from abc import ABCMeta, abstractmethod
from ctypes import POINTER, cast
from os import path
from typing import Dict, Iterator, List, Optional, Union
import config
from comtypes import CLSCTX_ALL, GUID, COMError, pointer
from globalVars import appArgs
from logHandler import log
from pycaw.api.audiopolicy import IAudioSessionControl2, IAudioSessionManager2
from pycaw.api.mmdeviceapi import IMMDevice
from pycaw.api.mmdeviceapi.depend.structures import PROPERTYKEY
from pycaw.constants import DEVICE_STATE, STGM, AudioSessionState
from pycaw.utils import (
	AudioSession,
	AudioUtilities,
	EDataFlow,
	ERole,
	IAudioEndpointVolume,
	ISimpleAudioVolume,
)

addonName = path.basename(path.dirname(__file__))


class Configuration(object):
	"""Collection of devices and processes that need to be hidden,
	and list of muted audio sources.
	"""

	def __init__(self) -> None:
		"""File name for saving data and loading previously saved data."""
		self._file = path.join(appArgs.configPath, path.basename(path.dirname(__file__)) + ".json")
		self._data: Dict = {}
		self.load()

	def load(self) -> Configuration:
		"""Load previously saved data.
		@return: updated self object
		@rtype: Configuration
		"""
		try:
			with open(self._file, "r", encoding="utf-8") as f:
				self._data = json.load(f)
		except Exception:
			pass
		if "version" not in self._data:
			self._data = {"version": 0}
		return self

	def save(self) -> bool:
		"""Save the data to an external file.
		@return: whether the data has been successfully saved
		@rtype: bool
		"""
		try:
			with open(self._file, "w", encoding="utf-8") as f:
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
		self._data["devices"] = devices
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
		self._data["processes"] = list(processes)
		return self

	def isChangedDevices(self, devices: Dict[str, str]) -> bool:
		"""Determine if the new list of audio devices differs from the existing one.
		@param devices: dict with devices in which the key is the ID and the value is the device name
		@type devices: Dict[str, str]
		@return: indication of whether the data are different
		@rtype: bool
		"""
		return bool(set(self.devices) ^ set(devices))

	def isChangedProcesses(self, processes: List[str]) -> bool:
		"""Determine if the new processes list differs from the existing one.
		@param processes: list of the full names of processes
		@type processes: List[str]
		@return: indication of whether the data are different
		@rtype: bool
		"""
		return bool(set(self.processes) ^ set(processes))

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
			# The list must be stored first: without the "muted" key the property returns a new empty list
			self._data.setdefault("muted", []).append(name)
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


def getDefaultOutputSessions() -> List[AudioSession]:
	"""Get all audio sessions of the default output device.
	Unlike AudioUtilities.GetAllSessions() from pycaw 20251023+, this does not wrap the device
	with AudioUtilities.CreateDevice(), which reads the whole property store of the device
	and makes every call several times slower.
	@return: audio sessions of the default output device, empty if there is no such device
	@rtype: List[pycaw.AudioSession]
	"""
	try:
		device = AudioUtilities.GetDeviceEnumerator().GetDefaultAudioEndpoint(
			EDataFlow.eRender.value,
			ERole.eMultimedia.value,
		)
		manager = device.Activate(IAudioSessionManager2._iid_, CLSCTX_ALL, None).QueryInterface(
			IAudioSessionManager2,
		)
		sessionEnumerator = manager.GetSessionEnumerator()
	except COMError:
		log.debugWarning("Unable to get audio sessions of the default output device", exc_info=True)
		return []
	sessions: List[AudioSession] = []
	for i in range(sessionEnumerator.GetCount()):
		control = sessionEnumerator.GetSession(i)
		if control is None:
			continue
		sessions.append(AudioSession(control.QueryInterface(IAudioSessionControl2)))
	return sessions


# Format ID of the device property keys PKEY_Device_FriendlyName (14) and PKEY_Device_DeviceDesc (2)
DEVICE_PROPERTIES_FMTID = GUID("{a45c254e-df1c-4efd-8020-67d146a850e0}")


def getDeviceName(immDevice: IMMDevice) -> str:
	"""Get the human friendly name of the audio device.
	Only the name is read, unlike AudioUtilities.CreateDevice() which reads the whole property store.
	@param immDevice: audio device
	@type immDevice: pycaw.IMMDevice
	@return: friendly name of the device, its description if there is no friendly name, or empty string
	@rtype: str
	"""
	try:
		store = immDevice.OpenPropertyStore(STGM.STGM_READ.value)
	except COMError:
		return ""
	for pid in (14, 2):
		key = PROPERTYKEY()
		key.fmtid = DEVICE_PROPERTIES_FMTID
		key.pid = pid
		try:
			value = store.GetValue(key)
		except COMError:
			continue
		name = value.GetValue()
		value.clear()
		if isinstance(name, str) and name:
			return name
	return ""


class AudioSource(metaclass=ABCMeta):
	"""Represents the basic properties of audio source."""

	def __init__(
		self,
		id: str,
		name: str,
		volume: Union[ISimpleAudioVolume, pointer[IAudioEndpointVolume], None] = None,
	) -> None:
		"""The main properties of an audio source.
		@param id: audio source ID (audio device ID or audio session name)
		@type id: str
		@param name: name of audio source
		@type name: str
		@param volume: pointer on the interface to adjust the volume of the audio source
		@type volume: Union[pycaw.ISimpleAudioVolume, pointer[pycaw.IAudioEndpointVolume], None]
		"""
		self._id = id
		self._name = name
		self._volume = volume
		self._channel: int = 0
		self._default: bool = False

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
	def volume(self) -> Union[ISimpleAudioVolume, IAudioEndpointVolume, None]:
		"""An object that gives access to control the volume of the sound source.
		@return: volume control object
		@rtype: Union[pycaw.ISimpleAudioVolume, pycaw.IAudioEndpointVolume, None]
		"""
		return self._volume

	@property
	def channel(self) -> int:
		"""Get selected channel of the audio source.
		@return: the number of the audio channel
		@rtype: int
		"""
		return self._channel

	@channel.setter
	def channel(self, number: int) -> None:
		"""Select the channel of the audio source.
		@param number: the number of the audio channel
		@type number: int
		"""
		try:
			number %= self.channelCount
		except ZeroDivisionError:
			number = 0
		self._channel = number

	@property
	def default(self) -> bool:
		"""Check if the current audio source is the default output device.
		@return: default output audio device or not
		@rtype: bool
		"""
		return self._default

	# MyPy 0.812 is not supported type hints for abstract property getters and setters
	# https://github.com/python/mypy/issues/4165
	@property  # type: ignore
	@abstractmethod
	def volumeLevel(self) -> float:
		"""Get the volume level of the sound source.
		The method must be overridden for each type of sound sources.
		@return: current volume level
		@rtype: float [0.0..1.0]
		"""
		raise NotImplementedError("This property must be overridden in the child class!")

	# Decorated property is not supported by MyPy 0.812
	# https://github.com/python/mypy/issues/1362
	@volumeLevel.setter  # type: ignore
	@abstractmethod
	def volumeLevel(self, level: float) -> None:
		"""Set the volume level of the sound source.
		The method must be overridden for each type of sound sources.
		@param level: target volume level
		@type level: float [0.0..1.0]
		"""
		raise NotImplementedError("This property must be overridden in the child class!")

	def volumeUp(self) -> float:
		"""Increase the volume level by the specified step.
		@return: current volume level
		@rtype: float
		"""
		self.isMuted and self.unmute()
		# Ignore MyPy type hint because setter volumeLevel is not read-only
		level = self.volumeLevel = min(  # type: ignore
			1.0,
			float(round(self.volumeLevel * 100.0) + config.conf[addonName]["step"]) / 100.0,
		)
		return level

	def volumeDown(self) -> float:
		"""Decrease the volume level by the specified step.
		@return: current volume level
		@rtype: float
		"""
		if self.isMuted:
			if self.volumeLevel <= 0.0:
				# Already silent: unmuting just to mute again would only rewrite the configuration file
				return 0.0
			self.unmute()
		# Ignore MyPy type hint because setter volumeLevel is not read-only
		level = self.volumeLevel = max(  # type: ignore
			0.0,
			float(round(self.volumeLevel * 100.0) - config.conf[addonName]["step"]) / 100.0,
		)
		return level

	def volumeMax(self) -> float:
		"""Set the maximum volume level of the audio source.
		@return: current volume level
		@rtype: float
		"""
		self.isMuted and self.unmute()
		# Ignore MyPy type hint because setter volumeLevel is not read-only
		self.volumeLevel = 1.0  # type: ignore
		return self.volumeLevel

	def volumeMin(self) -> float:
		"""Set the minimum volume level of the audio source.
		@return: current volume level
		@rtype: float
		"""
		self.isMuted and self.unmute()
		# Ignore MyPy type hint because setter volumeLevel is not read-only
		self.volumeLevel = 0.0  # type: ignore
		return self.volumeLevel

	@property
	def isMuted(self) -> bool:
		"""Check whether the current audio source is muted.
		@return: a state of the audio source (muted or no)
		@rtype: bool
		"""
		state = False if self.volume is None else self.volume.GetMute()
		if not config.conf[addonName]["muteCompletely"]:
			return (self.id in cfg.muted) or state
		return state

	def mute(self) -> bool:
		"""Mute the current audio source.
		@return: a state of the audio source (muted or no)
		@rtype: bool
		"""
		try:
			if config.conf[addonName]["muteCompletely"]:
				self.volume.SetMute(True, None)  # type: ignore
			elif not self.isMuted:
				# Incorrect handling of AttributeError by MyPy 0.812: https://github.com/python/mypy/issues/8056
				self.volumeLevel *= (100 - config.conf[addonName]["mutePercentage"]) / 100.0  # type: ignore
		except AttributeError:
			return False
		else:
			# The file is written only when the list of muted audio sources changes
			if self.id not in cfg.muted:
				cfg.addMuted(self.id).save()
			return True

	def unmute(self) -> bool:
		"""Unmute the current audio source.
		@return: a state of the audio source (muted or no)
		@rtype: bool
		"""
		try:
			# The getattr() function is used for correct processing by the MyPy analyzer
			getattr(self.volume, "SetMute")(False, None)
			if self.isMuted:
				# Setter volumeLevel is not read-only, MyPy issue
				self.volumeLevel = min(  # type: ignore
					1.0,
					round(self.volumeLevel * 100.0) / (100.0 - config.conf[addonName]["mutePercentage"]),
				)
		except AttributeError:
			return False
		else:
			# The file is written only when the list of muted audio sources changes
			if self.id in cfg.muted:
				cfg.delMuted(self.id).save()
			return True

	@property
	@abstractmethod
	def channelCount(self) -> int:
		"""Get the number of channels available in the current audio source.
		The method must be overridden for each type of sound sources.
		@return: the number of channels
		@rtype: int
		"""
		raise NotImplementedError("This property must be overridden in the child class!")

	@abstractmethod
	def getChannelVolumeLevel(self, channel: int) -> float:
		"""Get the volume level of the specified audio source channel.
		The method must be overridden for each type of sound sources.
		@param channel: the number of the specified audio channel
		@type channel: int
		@return: the volume level
		@rtype: float
		"""
		raise NotImplementedError("This property must be overridden in the child class!")

	@abstractmethod
	def setChannelVolumeLevel(self, level: float, channel: int = -1) -> None:
		"""Set the volume level of the specified audio source channel.
		The method must be overridden for each type of sound sources.
		@param channel: the number of the specified audio channels
		@type channel: int
		@param level: target volume level
		@type level: float [0.0..1.0]
		"""
		raise NotImplementedError("This property must be overridden in the child class!")

	def channelVolumeUp(self, channel: int = -1) -> float:
		"""Increase the volume level for selected channel by the specified step.
		@param channel: the number of the specified audio channel
		@type channel: int
		@return: current volume level
		@rtype: float [-1.0, 0.0..1.0]
		"""
		self.isMuted and self.unmute()
		if channel < 0:
			channel = self.channel
		level: float = self.getChannelVolumeLevel(channel)
		if level < 0:
			return level
		level = min(1.0, float(round(level * 100.0) + config.conf[addonName]["step"]) / 100.0)
		self.setChannelVolumeLevel(level, channel)
		return level

	def channelVolumeDown(self, channel: int = -1) -> float:
		"""Decrease the volume level for selected channel by the specified step.
		@param channel: the number of the specified audio channel
		@type channel: int
		@return: current volume level
		@rtype: float [-1.0, 0.0..1.0]
		"""
		self.isMuted and self.unmute()
		if channel < 0:
			channel = self.channel
		level: float = self.getChannelVolumeLevel(channel)
		if level < 0:
			return level
		level = max(0.0, float(round(level * 100.0) - config.conf[addonName]["step"]) / 100.0)
		self.setChannelVolumeLevel(level, channel)
		return level

	def channelVolumeMax(self, channel: int = -1) -> float:
		"""Set the maximum volume level of the selected channel.
		@param channel: the number of the specified audio channel
		@type channel: int
		@return: current volume level
		@rtype: float [-1.0, 1.0]
		"""
		self.isMuted and self.unmute()
		if channel < 0:
			channel = self.channel
		self.setChannelVolumeLevel(1.0, channel)
		return self.getChannelVolumeLevel(channel)

	def channelVolumeMin(self, channel: int = -1) -> float:
		"""Set the minimum volume level of the selected channel.
		@param channel: the number of the specified audio channel
		@type channel: int
		@return: current volume level
		@rtype: float [-1.0, 0.0]
		"""
		self.isMuted and self.unmute()
		if channel < 0:
			channel = self.channel
		self.setChannelVolumeLevel(0.0, channel)
		return self.getChannelVolumeLevel(channel)

	def channelVolumeAverage(self) -> float:
		"""Set the average volume level for all audio channels.
		@return: average volume level
		@rtype: float [-1.0, 0.0..1.0]
		"""
		if self.channelCount <= 0:
			return -1.0
		level: float = (
			sum((self.getChannelVolumeLevel(channel) for channel in range(self.channelCount)))
			/ self.channelCount
		)
		for channel in range(self.channelCount):
			self.setChannelVolumeLevel(level, channel)
		return level


class VAAudioDevice(AudioSource):
	"""Presentation of one audio device."""

	@property
	def volumeLevel(self) -> float:
		"""Get the volume level of the audio device.
		@return: current volume level
		@rtype: float [-1.0, 0.0..1.0]
		"""
		try:
			# Incorrect handling of AttributeError by MyPy 0.812: https://github.com/python/mypy/issues/8056
			return self.volume.GetMasterVolumeLevelScalar()  # type: ignore
		except (AttributeError, TypeError):
			return -1.0

	@volumeLevel.setter
	def volumeLevel(self, level: float) -> None:
		"""Set the volume level of the audio device.
		@param level: target volume level
		@type level: float [0.0..1.0]
		"""
		try:
			# Incorrect handling of AttributeError by MyPy
			self.volume.SetMasterVolumeLevelScalar(level, None)  # type: ignore
		except (AttributeError, TypeError):
			pass

	@property
	def channelCount(self) -> int:
		"""Get the number of channels available in the current audio device.
		@return: the number of channels
		@rtype: int
		"""
		try:
			# Incorrect handling of AttributeError by MyPy
			return self.volume.GetChannelCount()  # type: ignore
		except (AttributeError, TypeError):
			return 0

	def getChannelVolumeLevel(self, channel: int = -1) -> float:
		"""Get the volume level of the specified audio source channel.
		@param channel: the number of the specified audio channel
		@type channel: int
		@return: the volume level
		@rtype: float
		"""
		if channel < 0:
			channel = self.channel
		try:
			# Incorrect handling of AttributeError by MyPy 0.812: https://github.com/python/mypy/issues/8056
			return self.volume.GetChannelVolumeLevelScalar(channel)  # type: ignore
		except (AttributeError, TypeError):
			return -1.0

	def setChannelVolumeLevel(self, level: float, channel: int = -1) -> None:
		"""Set the volume level of the specified audio source channel.
		@param channel: the number of the specified audio channel
		@type channel: int
		@param level: target volume level
		@type level: float [0.0..1.0]
		"""
		if channel < 0:
			channel = self.channel
		try:
			# Incorrect handling of AttributeError by MyPy
			self.volume.SetChannelVolumeLevelScalar(channel, level, None)  # type: ignore
		except (AttributeError, TypeError):
			pass


class VAAudioDevices(object):
	"""Detection and presentation of all system audio devices."""

	def __init__(self) -> None:
		"""Initial values of default audio device and a list of all detected devices."""
		self._devices: List[VAAudioDevice] = []

	def initialize(self, hide: Dict[str, str] = {}) -> VAAudioDevices:
		"""Detect audio devices and save them in the list.
		Only active devices are listed: disabled, unplugged and not present devices are skipped.
		The default output device is always the first one in the list.
		@param hide: a collection of devices that needs to hide
		@type hide: Dict[str, str]
		@return: collection of the detected audio devices
		@rtype: VAAudioDevices
		"""
		self._devices = []
		try:
			enumerator = AudioUtilities.GetDeviceEnumerator()
			defaultDevice = enumerator.GetDefaultAudioEndpoint(
				EDataFlow.eRender.value,
				ERole.eMultimedia.value,
			)
			defaultId: str = defaultDevice.GetId()
		except COMError:
			log.debugWarning("Unable to get the default output audio device", exc_info=True)
			return self
		if config.conf[addonName]["advanced"]:
			# All active output and input devices
			collection = enumerator.EnumAudioEndpoints(EDataFlow.eAll.value, DEVICE_STATE.ACTIVE.value)
			for i in range(collection.GetCount()):
				immDevice = collection.Item(i)
				try:
					if immDevice.GetId() in (defaultId, *hide):
						continue
					device = self.createDevice(immDevice)
				except COMError:
					continue
				if device.name:
					self._devices.append(device)
		# The default output device is listed even if it is hidden
		try:
			device = self.createDevice(defaultDevice)
		except COMError:
			log.debugWarning("Unable to activate the default output audio device", exc_info=True)
			return self
		device._default = True
		self._devices.insert(0, device)
		return self

	@staticmethod
	def createDevice(immDevice: IMMDevice) -> VAAudioDevice:
		"""Create the presentation of the specified audio device.
		@param immDevice: audio device
		@type immDevice: pycaw.IMMDevice
		@return: audio device with the interface to adjust its volume
		@rtype: VAAudioDevice
		"""
		id: str = immDevice.GetId() or "default"
		return VAAudioDevice(
			id=id,
			name=getDeviceName(immDevice) or id,
			volume=cast(
				immDevice.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None),
				POINTER(IAudioEndpointVolume),
			),
		)

	def scan(self, hide: Dict[str, str] = {}) -> None:
		"""Search for available audio devices in the system and save them in the current object.
		It takes a few milliseconds, so it runs in the calling thread, which also uses the created COM objects.
		@param hide: a collection of audio devices that needs to hide
		@type hide: Dict[str, str]
		"""
		self.initialize(hide)

	def __len__(self) -> int:
		"""The number of audio devices detected in the system.
		@return: number of audio devices
		@rtype: int
		"""
		return len(self._devices)

	def __getitem__(self, index: int) -> VAAudioDevice:
		"""Return the audio device by its sequence number in the list.
		@param index: the index of the device in the sequence of detected audio devices
		@type index: int
		@return: audio device from the list
		@rtype: VAAudioDevice
		"""
		return self._devices[index]

	def __iter__(self) -> Iterator[VAAudioDevice]:
		"""Iteration through all detected audio devices.
		@return: iterator of all detected audio devices
		@rtype: Iterator[VAAudioDevice]
		"""
		for device in self._devices:
			yield device


class VAAudioSession(AudioSource):
	"""Object for working with the audio session of a separate running process."""

	def __init__(self, name: str, pid: int = 0) -> None:
		"""Initialize an audio session.
		@param name: the name of the running process
		@type name: str
		@param pid: ID of the process whose audio session is preferred, 0 to search by name only
		@type pid: int
		"""
		self._sessions: List[AudioSession] = [
			session for session in getDefaultOutputSessions() if session.Process and session.Process.name()
		]
		self._current: AudioSession = self.selectAudioSession(name, pid)
		super(VAAudioSession, self).__init__(id=name, name="", volume=None)
		# Muted audio sources are stored by ID, so it is the full name of the selected process,
		# e.g. "firefox.exe" when the session was looked up by the application name "firefox"
		self._id = self.name or name

	def selectAudioSession(self, name: str = "nvda.exe", pid: int = 0) -> AudioSession:
		"""Find and return an audio session by its process ID or specified name.
		The process ID is not enough on its own: e.g. in web browsers the sound is usually played
		by a child process, not by the process of the focused window.
		@param name: full name or part of the process name
		@type name: str
		@param pid: ID of the process whose audio session is preferred, 0 to search by name only
		@type pid: int
		@return: an audio session related to a given process
		@rtype: pycaw.AudioSession
		"""
		if pid:
			session = next((s for s in self._sessions if s.ProcessId == pid), None)
			if session is not None:
				return session
		return next(
			filter(lambda s: name.lower() in s.Process.name().lower(), self._sessions),  # noqa ET113
			next(
				filter(lambda s: "nvda.exe" in s.Process.name().lower(), self._sessions),  # noqa E128
				self._sessions[0],
			),
		)  # noqa E128

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
				self._name = ""
		return self._name

	@property
	def title(self) -> str:
		"""Getter method - returns human friendly name of the current process.
		@return: human friendly name of the current running process
		@rtype: str
		"""
		try:
			name: str = self._current.DisplayName
		except AttributeError:
			name = ""
		name = {
			r"@%SystemRoot%\System32\AudioSrv.Dll,-202": "System Sound",
		}.get(name, name)
		return name or self.name.replace(".exe", "")

	@property
	def isExpired(self) -> bool:
		"""Check whether the audio session can no longer be used.
		A session expires when its process exits or closes all its audio streams.
		Volume calls on an expired session do not fail, they just have no effect.
		@return: whether the audio session has expired or is not available anymore
		@rtype: bool
		"""
		try:
			return self._current.State == AudioSessionState.Expired
		except (AttributeError, COMError):
			return True

	@property
	def volume(self) -> Union[ISimpleAudioVolume, IAudioEndpointVolume, None]:
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
		@rtype: float [-1.0, 0.0..1.0]
		"""
		try:
			# Incorrect handling of AttributeError by MyPy
			return self.volume.GetMasterVolume()  # type: ignore
		except (AttributeError, TypeError):
			return -1.0

	@volumeLevel.setter
	def volumeLevel(self, level: float) -> None:
		"""Set the volume level of the audio session.
		@param level: target volume level
		@type level: float [0.0..1.0]
		"""
		try:
			# Incorrect handling of AttributeError by MyPy
			self.volume.SetMasterVolume(level, None)  # type: ignore
		except (AttributeError, TypeError):
			pass

	@property
	def channelCount(self) -> int:
		"""Get the number of channels available in the current audio device.
		@return: the number of channels
		@rtype: int
		"""
		return -1

	def getChannelVolumeLevel(self, channel: int = -1) -> float:
		"""Get the volume level of the specified audio source channel.
		@param channel: the number of the specified audio channel
		@type channel: int
		@return: the volume level
		@rtype: float
		"""
		return -1.0

	def setChannelVolumeLevel(self, level: float, channel: int = -1) -> None:
		"""Set the volume level of the specified audio source channel.
		@param channel: the number of the specified audio channel
		@type channel: int
		@param level: target volume level
		@type level: float [0.0..1.0]
		"""
		pass


# global instance to avoid multiple scans of all audio devices
devices = VAAudioDevices()
