# sources.py
# Audio sources whose volume can be adjusted: audio devices and applications playing sound
# A part of the NVDA Volume Adjustment add-on
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.
# Copyright (C) 2020-2026 Oleksandr Gryshchenko <grisov.nvaccess@mailgw.com>

from __future__ import annotations
from abc import ABCMeta, abstractmethod
from enum import Enum
from typing import Dict, Iterable, List, Optional, Type, Union
import config
from comtypes import CLSCTX_ALL, COMError, pointer
from logHandler import log
from pycaw.api.mmdeviceapi import IMMDevice
from pycaw.constants import DEVICE_STATE, AudioSessionState
from pycaw.utils import (
	AudioSession,
	AudioUtilities,
	EDataFlow,
	ERole,
	IAudioEndpointVolume,
	ISimpleAudioVolume,
)
from .audiocore import addonName, cfg, getDefaultOutputSessions, getDeviceName


class SourceKind(Enum):
	"""Categories of audio sources whose volume can be adjusted."""

	OUTPUT_DEVICE = "O"
	INPUT_DEVICE = "I"
	PLAYBACK_APP = "P"
	RECORDING_APP = "R"


class SessionGroupVolume(object):
	"""Volume control of all audio sessions of one application, used like a single ISimpleAudioVolume:
	the volume level and the mute state are read from the first session and set for all of them.
	"""

	def __init__(self, volumes: List[ISimpleAudioVolume]) -> None:
		"""Volume control of the specified audio sessions.
		@param volumes: volume interfaces of the audio sessions, at least one
		@type volumes: List[pycaw.ISimpleAudioVolume]
		"""
		self._volumes = volumes

	def GetMasterVolume(self) -> float:
		"""Get the volume level of the first audio session.
		@return: volume level
		@rtype: float [0.0..1.0]
		"""
		return self._volumes[0].GetMasterVolume()

	def SetMasterVolume(self, level: float, context: Optional[object]) -> None:
		"""Set the volume level of all audio sessions.
		@param level: target volume level
		@type level: float [0.0..1.0]
		@param context: event context passed to the audio sessions
		@type context: Optional[object]
		"""
		for volume in self._volumes:
			volume.SetMasterVolume(level, context)

	def GetMute(self) -> bool:
		"""Get the mute state of the first audio session.
		@return: whether the audio session is muted
		@rtype: bool
		"""
		return self._volumes[0].GetMute()

	def SetMute(self, mute: bool, context: Optional[object]) -> None:
		"""Mute or unmute all audio sessions.
		@param mute: whether to mute the audio sessions
		@type mute: bool
		@param context: event context passed to the audio sessions
		@type context: Optional[object]
		"""
		for volume in self._volumes:
			volume.SetMute(mute, context)


class AudioSource(metaclass=ABCMeta):
	"""Represents the basic properties of audio source."""

	def __init__(
		self,
		id: str,
		name: str,
		volume: Union[ISimpleAudioVolume, SessionGroupVolume, pointer[IAudioEndpointVolume], None] = None,
	) -> None:
		"""The main properties of an audio source.
		@param id: audio source ID (audio device ID or audio session name)
		@type id: str
		@param name: name of audio source
		@type name: str
		@param volume: pointer on the interface to adjust the volume of the audio source
		@type volume: Union[pycaw.ISimpleAudioVolume, SessionGroupVolume, pointer[pycaw.IAudioEndpointVolume], None]
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


class DeviceSource(AudioSource):
	"""Presentation of one audio device."""

	kind: SourceKind

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


class OutputDeviceSource(DeviceSource):
	"""Audio output device, e.g. speakers or headphones."""

	kind = SourceKind.OUTPUT_DEVICE


class InputDeviceSource(DeviceSource):
	"""Audio input device, e.g. a microphone."""

	kind = SourceKind.INPUT_DEVICE


def createDevice(immDevice: IMMDevice, deviceClass: Type[DeviceSource]) -> DeviceSource:
	"""Create the presentation of the specified audio device.
	@param immDevice: audio device
	@type immDevice: pycaw.IMMDevice
	@param deviceClass: class of the audio source according to the data flow of the device
	@type deviceClass: Type[DeviceSource]
	@return: audio device with the interface to adjust its volume
	@rtype: DeviceSource
	"""
	id: str = immDevice.GetId() or "default"
	# QueryInterface() adds a COM reference for the new pointer object. ctypes.cast() must not be used here:
	# it creates a second pointer object without a reference, so the interface was released twice
	# when the device objects were discarded, which crashed NVDA after the devices were rescanned.
	return deviceClass(
		id=id,
		name=getDeviceName(immDevice) or id,
		volume=immDevice.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None).QueryInterface(
			IAudioEndpointVolume,
		),
	)


class AppSource(AudioSource):
	"""All audio sessions of one running application (process name), adjusted together."""

	kind: SourceKind

	def __init__(self, name: str, sessions: List[AudioSession]) -> None:
		"""Initialize the application with its audio sessions.
		@param name: the full name of the process, also used as the ID of the muted audio source
		@type name: str
		@param sessions: audio sessions of the application, at least one
		@type sessions: List[pycaw.AudioSession]
		"""
		super(AppSource, self).__init__(
			id=name,
			name=name,
			volume=SessionGroupVolume([session.SimpleAudioVolume for session in sessions]),
		)
		self._sessions = sessions

	@property
	def processIds(self) -> List[int]:
		"""IDs of the processes playing the audio sessions of the application.
		@return: process IDs
		@rtype: List[int]
		"""
		return [session.ProcessId for session in self._sessions]

	@property
	def title(self) -> str:
		"""Getter method - returns human friendly name of the application.
		@return: human friendly name of the application
		@rtype: str
		"""
		try:
			name: str = self._sessions[0].DisplayName
		except (AttributeError, COMError):
			name = ""
		name = {
			r"@%SystemRoot%\System32\AudioSrv.Dll,-202": "System Sound",
		}.get(name, name)
		return name or self.name.replace(".exe", "")

	@property
	def isExpired(self) -> bool:
		"""Check whether the application must be looked up again.
		A session expires when its process exits or closes all its audio streams.
		Volume calls on an expired session do not fail, they just have no effect.
		@return: whether any of the audio sessions has expired or is not available anymore
		@rtype: bool
		"""
		try:
			return any(session.State == AudioSessionState.Expired for session in self._sessions)
		except (AttributeError, COMError):
			return True

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


class PlaybackAppSource(AppSource):
	"""Application playing sound."""

	kind = SourceKind.PLAYBACK_APP


class AudioSourceRegistry(object):
	"""All audio sources whose volume can be adjusted.
	The list of audio devices is kept until it is rescanned, while applications are looked up on demand:
	their audio sessions appear and disappear all the time, and looking them up takes a few milliseconds.
	"""

	def __init__(self) -> None:
		"""Initially no audio devices are known, they are detected by scanDevices()."""
		self._devices: List[DeviceSource] = []

	@property
	def devices(self) -> List[DeviceSource]:
		"""Audio devices found by the last scan, the default output device is the first one.
		@return: audio devices whose volume can be adjusted
		@rtype: List[DeviceSource]
		"""
		return self._devices

	def scanDevices(self, hide: Iterable[str] = ()) -> None:
		"""Detect the audio devices whose volume can be adjusted and keep them until the next scan.
		It takes a few milliseconds, so it runs in the calling thread, which also uses the created COM objects.
		@param hide: IDs of the audio devices hidden in the add-on settings
		@type hide: Iterable[str]
		"""
		self._devices = self.getAllDevices(hide)

	def getAllDevices(self, hide: Iterable[str] = ()) -> List[DeviceSource]:
		"""Detect the active audio devices without changing the list of devices kept by the registry.
		The default output device is always the first one, even if it is hidden.
		If all available audio devices are controlled, the other output devices and then the input devices follow.
		Disabled, unplugged and not present devices are skipped.
		@param hide: IDs of the audio devices to skip
		@type hide: Iterable[str]
		@return: detected audio devices
		@rtype: List[DeviceSource]
		"""
		try:
			enumerator = AudioUtilities.GetDeviceEnumerator()
			defaultDevice = enumerator.GetDefaultAudioEndpoint(
				EDataFlow.eRender.value,
				ERole.eMultimedia.value,
			)
			default = createDevice(defaultDevice, OutputDeviceSource)
		except COMError:
			log.debugWarning("Unable to get the default output audio device", exc_info=True)
			return []
		default._default = True
		devices: List[DeviceSource] = [default]
		if not config.conf[addonName]["advanced"]:
			return devices
		skip = {default.id, *hide}
		for flow, deviceClass in (
			(EDataFlow.eRender, OutputDeviceSource),
			(EDataFlow.eCapture, InputDeviceSource),
		):
			collection = enumerator.EnumAudioEndpoints(flow.value, DEVICE_STATE.ACTIVE.value)
			for i in range(collection.GetCount()):
				immDevice = collection.Item(i)
				try:
					if immDevice.GetId() in skip:
						continue
					device = createDevice(immDevice, deviceClass)
				except COMError:
					continue
				if device.name:
					devices.append(device)
		return devices

	def getApps(self, hide: Iterable[str] = ()) -> List[PlaybackAppSource]:
		"""Get the applications playing sound on the default output device.
		There is one audio source per process name, in the order of the audio sessions,
		and all audio sessions of the application are adjusted together.
		@param hide: names of the processes hidden in the add-on settings
		@type hide: Iterable[str]
		@return: applications playing sound
		@rtype: List[PlaybackAppSource]
		"""
		hidden = set(hide)
		groups: Dict[str, List[AudioSession]] = {}
		for session in getDefaultOutputSessions():
			name = session.Process.name() if session.Process else ""
			if name and name not in hidden:
				groups.setdefault(name, []).append(session)
		return [PlaybackAppSource(name, sessions) for name, sessions in groups.items()]

	def findApp(self, name: str, pid: int = 0) -> Optional[PlaybackAppSource]:
		"""Find the application playing sound by its process ID or name.
		The process ID is not enough on its own: e.g. in web browsers the sound is usually played
		by a child process, not by the process of the focused window.
		There is no fallback to another application: adjusting the volume of NVDA or of an unrelated program
		instead of the requested one would be confusing.
		@param name: full name or part of the process name
		@type name: str
		@param pid: ID of the process whose application is preferred, 0 to search by name only
		@type pid: int
		@return: the application, None if it does not play any sound
		@rtype: Optional[PlaybackAppSource]
		"""
		apps = self.getApps()
		if pid:
			app = next((app for app in apps if pid in app.processIds), None)
			if app is not None:
				return app
		return next((app for app in apps if name.lower() in app.name.lower()), None)


# Global instance shared by the global plugin and the settings panel
registry = AudioSourceRegistry()
