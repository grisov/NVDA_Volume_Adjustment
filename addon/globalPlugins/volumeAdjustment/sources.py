# sources.py
# Audio sources whose volume can be adjusted: audio devices and applications playing or recording sound
# A part of the NVDA Volume Adjustment add-on
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.
# Copyright (C) 2020-2026 Oleksandr Gryshchenko <grisov.nvaccess@mailgw.com>

from __future__ import annotations
import math
from abc import ABCMeta, abstractmethod
from enum import Enum, IntEnum
from typing import Dict, Iterable, List, NamedTuple, Optional, Tuple, Type, TypeVar, Union
import config
from comtypes import CLSCTX_ALL, COMError, pointer
from logHandler import log
from pycaw.api.audiopolicy import IAudioSessionManager2
from pycaw.api.mmdeviceapi import IMMDevice
from pycaw.callbacks import AudioSessionNotification, MMNotificationClient
from pycaw.constants import DEVICE_STATE, AudioSessionState
from pycaw.utils import (
	AudioSession,
	AudioUtilities,
	EDataFlow,
	ERole,
	IAudioEndpointVolume,
	ISimpleAudioVolume,
)
from .audiocore import (
	PKEY_AudioEndpoint_FormFactor,
	PKEY_Device_DeviceDesc,
	PKEY_Device_EnumeratorName,
	PKEY_Device_FriendlyName,
	PKEY_DeviceInterface_FriendlyName,
	addonName,
	cfg,
	getDeviceProperties,
	getSessionManager,
	listSessions,
)


# Windows stores volume levels as 32-bit floats: 29 % is read back as 28.999999 %.
# A level closer than this to a whole percent (in percent) is treated as that whole percent.
LEVEL_TOLERANCE = 0.01


def stepLevel(level: float, step: int) -> float:
	"""Change the volume level by the step in percent, stopping at whole percents.
	A level at a whole percent changes exactly by the step. A level set by another program between
	whole percents first moves to the next whole percent in the direction of the step,
	so every keypress changes the announced level by the step.
	@param level: current volume level
	@type level: float [0.0..1.0]
	@param step: change in percent, negative to decrease the level
	@type step: int
	@return: new volume level
	@rtype: float [0.0..1.0]
	"""
	target = level * 100.0 + step
	percent = math.floor(target + LEVEL_TOLERANCE) if step > 0 else math.ceil(target - LEVEL_TOLERANCE)
	return min(100, max(0, percent)) / 100.0


class SourceKind(Enum):
	"""Categories of audio sources whose volume can be adjusted."""

	OUTPUT_DEVICE = "O"
	INPUT_DEVICE = "I"
	PLAYBACK_APP = "P"
	RECORDING_APP = "R"


# Identifies an audio source between keypresses: its category and ID (device ID or process name).
# The same process can be both a playback and a recording application.
SourceKey = Tuple[SourceKind, str]


class FormFactor(IntEnum):
	"""Physical type of an audio device (EndpointFormFactor in Windows)."""

	REMOTE_NETWORK_DEVICE = 0
	SPEAKERS = 1
	LINE_LEVEL = 2
	HEADPHONES = 3
	MICROPHONE = 4
	HEADSET = 5
	HANDSET = 6
	UNKNOWN_DIGITAL_PASSTHROUGH = 7
	SPDIF = 8
	DIGITAL_AUDIO_DISPLAY_DEVICE = 9
	"""HDMI or DisplayPort, e.g. the speakers of a monitor or TV"""
	UNKNOWN = 10


class Connection(Enum):
	"""How an audio device is connected, guessed from the name of its device enumerator."""

	INTERNAL = "internal"
	"""Sound card of the computer or HDMI/DisplayPort of the graphics card (HDAUDIO, INTELAUDIO)"""
	USB = "usb"
	BLUETOOTH = "bluetooth"
	"""Including the hands-free profile, which Windows shows as a separate device (BTHENUM, BTHHFENUM)"""
	VIRTUAL = "virtual"
	"""Software device, e.g. a virtual audio cable (ROOT, SWD); a heuristic, not an official attribute"""
	OTHER = "other"

	@classmethod
	def fromEnumeratorName(cls, name: Optional[str]) -> Connection:
		"""Guess the connection from the name of the device enumerator.
		@param name: value of the PKEY_Device_EnumeratorName property
		@type name: Optional[str]
		@return: the connection of the device
		@rtype: Connection
		"""
		name = (name or "").upper()
		if name in ("HDAUDIO", "INTELAUDIO"):
			return cls.INTERNAL
		if name == "USB":
			return cls.USB
		if name.startswith("BTH"):
			return cls.BLUETOOTH
		if name in ("ROOT", "SWD"):
			return cls.VIRTUAL
		return cls.OTHER


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

	kind: SourceKind

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
	def mutedKey(self) -> str:
		"""Key of the audio source in the list of muted audio sources saved in the add-on configuration.
		@return: device ID or audio session name
		@rtype: str
		"""
		return self.id

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
		level = self.volumeLevel = stepLevel(self.volumeLevel, config.conf[addonName]["step"])  # type: ignore
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
		level = self.volumeLevel = stepLevel(self.volumeLevel, -config.conf[addonName]["step"])  # type: ignore
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
			return (self.mutedKey in cfg.muted) or state
		return state

	def mute(self) -> bool:
		"""Mute the current audio source.
		@return: a state of the audio source (muted or no)
		@rtype: bool
		"""
		# Exact volume level before muting, restored when the audio source is unmuted
		level: Optional[float] = None
		try:
			if config.conf[addonName]["muteCompletely"]:
				self.volume.SetMute(True, None)  # type: ignore
			elif not self.isMuted:
				level = self.volumeLevel
				# Incorrect handling of AttributeError by MyPy 0.812: https://github.com/python/mypy/issues/8056
				self.volumeLevel = level * (100 - config.conf[addonName]["mutePercentage"]) / 100.0  # type: ignore
		except AttributeError:
			return False
		else:
			# The file is written only when the list of muted audio sources changes
			if self.mutedKey not in cfg.muted:
				cfg.addMuted(self.mutedKey, level).save()
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
				level = cfg.getMutedLevel(self.mutedKey)
				if level is None:
					# Muted by a previous version of the add-on, which did not save the exact level
					percentage = config.conf[addonName]["mutePercentage"]
					level = min(1.0, self.volumeLevel * 100.0 / (100.0 - percentage))
				# Setter volumeLevel is not read-only, MyPy issue
				self.volumeLevel = level  # type: ignore
		except AttributeError:
			return False
		else:
			# The file is written only when the list of muted audio sources changes
			if self.mutedKey in cfg.muted:
				cfg.delMuted(self.mutedKey).save()
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
		level = stepLevel(level, config.conf[addonName]["step"])
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
		level = stepLevel(level, -config.conf[addonName]["step"])
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
	# Attributes read when the device is detected, see createDevice()
	formFactor: FormFactor = FormFactor.UNKNOWN
	connection: Connection = Connection.OTHER
	adapterName: str = ""
	"""Name of the sound card, useful when several devices have the same name such as Speakers"""
	isDefaultDevice: bool = False
	"""The default device of its data flow (output or input) for multimedia"""
	isDefaultCommunicationDevice: bool = False
	"""The default device of its data flow for communications"""

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


def createDevice(
	immDevice: IMMDevice,
	deviceClass: Type[DeviceSource],
	defaultIds: Iterable[str] = (),
	communicationIds: Iterable[str] = (),
) -> DeviceSource:
	"""Create the presentation of the specified audio device with its attributes.
	@param immDevice: audio device
	@type immDevice: pycaw.IMMDevice
	@param deviceClass: class of the audio source according to the data flow of the device
	@type deviceClass: Type[DeviceSource]
	@param defaultIds: IDs of the default devices for multimedia
	@type defaultIds: Iterable[str]
	@param communicationIds: IDs of the default devices for communications
	@type communicationIds: Iterable[str]
	@return: audio device with the interface to adjust its volume
	@rtype: DeviceSource
	"""
	id: str = immDevice.GetId() or "default"
	friendlyName, description, enumeratorName, formFactor, adapterName = getDeviceProperties(
		immDevice,
		(
			PKEY_Device_FriendlyName,
			PKEY_Device_DeviceDesc,
			PKEY_Device_EnumeratorName,
			PKEY_AudioEndpoint_FormFactor,
			PKEY_DeviceInterface_FriendlyName,
		),
	)
	name = next((value for value in (friendlyName, description) if isinstance(value, str) and value), id)
	# QueryInterface() adds a COM reference for the new pointer object. ctypes.cast() must not be used here:
	# it creates a second pointer object without a reference, so the interface was released twice
	# when the device objects were discarded, which crashed NVDA after the devices were rescanned.
	device = deviceClass(
		id=id,
		name=name,
		volume=immDevice.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None).QueryInterface(
			IAudioEndpointVolume,
		),
	)
	try:
		device.formFactor = FormFactor(formFactor)
	except ValueError:
		device.formFactor = FormFactor.UNKNOWN
	device.connection = Connection.fromEnumeratorName(enumeratorName)
	device.adapterName = adapterName if isinstance(adapterName, str) else ""
	device.isDefaultDevice = id in defaultIds
	device.isDefaultCommunicationDevice = id in communicationIds
	return device


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
		# Version of the registry state when the application was looked up, see AudioSourceRegistry.isOutdated()
		self.generation: int = 0

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


class RecordingAppSource(AppSource):
	"""Application recording sound."""

	kind = SourceKind.RECORDING_APP

	@property
	def mutedKey(self) -> str:
		"""Key of the application in the list of muted audio sources, distinct from the same playback application.
		A colon cannot be a part of a file name, so it cannot clash with a process name.
		@return: the process name with a prefix
		@rtype: str
		"""
		return f"recording:{self.name}"


AppT = TypeVar("AppT", bound=AppSource)


def getSourceKey(source: AudioSource) -> SourceKey:
	"""Get the key that identifies the audio source between keypresses.
	@param source: the audio source
	@type source: AudioSource
	@return: the category and the ID of the audio source
	@rtype: SourceKey
	"""
	return source.kind, source.id


class DeviceNotifications(MMNotificationClient):
	"""Marks the registry outdated when audio devices are added, removed, enabled, disabled
	or the default device is changed.
	Windows calls these methods in its own threads, so they only set flags:
	the lists are rebuilt in the main thread of NVDA when they are used next time.
	"""

	def __init__(self, registry: AudioSourceRegistry) -> None:
		"""Notification handler of the specified registry.
		@param registry: the registry to mark outdated
		@type registry: AudioSourceRegistry
		"""
		super(DeviceNotifications, self).__init__()
		self._registry = registry

	def on_default_device_changed(
		self,
		flow: str,
		flow_id: int,
		role: str,
		role_id: int,
		default_device_id: str,
	) -> None:
		"""The default device for a role has changed."""
		self._registry.markDevicesChanged()

	def on_device_added(self, added_device_id: str) -> None:
		"""A new audio device has been added."""
		self._registry.markDevicesChanged()

	def on_device_removed(self, removed_device_id: str) -> None:
		"""An audio device has been removed."""
		self._registry.markDevicesChanged()

	def on_device_state_changed(self, device_id: str, new_state: str, new_state_id: int) -> None:
		"""An audio device has been enabled, disabled, plugged in or unplugged."""
		self._registry.markDevicesChanged()


class SessionNotifications(AudioSessionNotification):
	"""Marks the applications outdated when a new audio session is created on an audio device.
	Windows calls this method in its own thread, so it only sets a flag.
	"""

	def __init__(self, registry: AudioSourceRegistry) -> None:
		"""Notification handler of the specified registry.
		@param registry: the registry to mark outdated
		@type registry: AudioSourceRegistry
		"""
		super(SessionNotifications, self).__init__()
		self._registry = registry

	def on_session_created(self, new_session: AudioSession) -> None:
		"""A new audio session has been created, it may belong to an already found application."""
		self._registry.markAppsChanged()


class SessionManagerEntry(NamedTuple):
	"""Session manager of an active audio device and the subscription to its new audio sessions."""

	flow: EDataFlow
	deviceId: str
	manager: IAudioSessionManager2
	# None if the subscription has failed: the sessions are still listed
	notifications: Optional[SessionNotifications]


class AudioSourceRegistry(object):
	"""All audio sources whose volume can be adjusted.
	The list of audio devices is kept until it is rescanned, while applications are looked up on demand:
	their audio sessions appear and disappear all the time, and looking them up takes a few milliseconds.
	"""

	def __init__(self) -> None:
		"""Initially no audio devices are known, they are detected by start() or scanDevices()."""
		self._devices: List[DeviceSource] = []
		# Devices hidden in the add-on settings, used when the devices are rescanned after a notification
		self._hide: List[str] = []
		# Flags set by the notification handlers in Windows threads and applied in the main thread
		self._devicesChanged: bool = False
		# Incremented whenever the found applications may be outdated
		self._generation: int = 0
		self._enumerator = None
		self._deviceNotifications: Optional[DeviceNotifications] = None
		# Session managers of all active audio devices, the default output device is the first one
		self._sessionManagers: List[SessionManagerEntry] = []

	def start(self, hide: Iterable[str] = ()) -> None:
		"""Detect the audio devices and subscribe to the notifications about audio devices and sessions.
		Must be called in the main thread, stop() must be called when the registry is no longer used.
		@param hide: IDs of the audio devices hidden in the add-on settings
		@type hide: Iterable[str]
		"""
		self.scanDevices(hide)
		try:
			self._enumerator = AudioUtilities.GetDeviceEnumerator()
			self._deviceNotifications = DeviceNotifications(self)
			self._enumerator.RegisterEndpointNotificationCallback(self._deviceNotifications)
		except COMError:
			log.debugWarning("Unable to subscribe to the notifications about audio devices", exc_info=True)
			self._enumerator = self._deviceNotifications = None
		self._subscribeSessions()

	def stop(self) -> None:
		"""Unsubscribe from all notifications. The registry can be started again."""
		self._unsubscribeSessions()
		if self._enumerator is not None and self._deviceNotifications is not None:
			try:
				self._enumerator.UnregisterEndpointNotificationCallback(self._deviceNotifications)
			except COMError:
				log.debugWarning(
					"Unable to unsubscribe from the notifications about audio devices",
					exc_info=True,
				)
		self._enumerator = self._deviceNotifications = None

	def _subscribeSessions(self) -> None:
		"""Get the session managers of all active output and input devices
		and subscribe to the creation of audio sessions on each of them.
		The default output device is the first one, so its applications are listed first.
		"""
		try:
			enumerator = AudioUtilities.GetDeviceEnumerator()
		except COMError:
			log.debugWarning("Unable to get the audio device enumerator", exc_info=True)
			return
		defaultIds = self.getDefaultDeviceIds(enumerator, ERole.eMultimedia)
		entries: List[SessionManagerEntry] = []
		for flow in (EDataFlow.eRender, EDataFlow.eCapture):
			try:
				collection = enumerator.EnumAudioEndpoints(flow.value, DEVICE_STATE.ACTIVE.value)
				count = collection.GetCount()
			except COMError:
				log.debugWarning("Unable to list the active audio devices", exc_info=True)
				continue
			for i in range(count):
				try:
					immDevice = collection.Item(i)
					id = immDevice.GetId()
					manager = getSessionManager(immDevice)
				except COMError:
					continue
				notifications: Optional[SessionNotifications] = SessionNotifications(self)
				try:
					manager.RegisterSessionNotification(notifications)
					# Windows sends the notifications only after the session enumerator has been requested
					manager.GetSessionEnumerator()
				except COMError:
					log.debugWarning(
						f"Unable to subscribe to the notifications about audio sessions of {id}",
						exc_info=True,
					)
					notifications = None
				entries.append(SessionManagerEntry(flow, id, manager, notifications))
		entries.sort(key=lambda entry: entry.deviceId not in defaultIds)
		self._sessionManagers = entries

	def _unsubscribeSessions(self) -> None:
		"""Unsubscribe from the creation of audio sessions on all audio devices."""
		for entry in self._sessionManagers:
			if entry.notifications is None:
				continue
			try:
				entry.manager.UnregisterSessionNotification(entry.notifications)
			except COMError:
				log.debugWarning(
					f"Unable to unsubscribe from the notifications about audio sessions of {entry.deviceId}",
					exc_info=True,
				)
		self._sessionManagers = []

	def markDevicesChanged(self) -> None:
		"""Mark the audio devices outdated. Called by the notification handlers in Windows threads."""
		self._devicesChanged = True
		self._generation += 1

	def markAppsChanged(self) -> None:
		"""Mark the found applications outdated. Called by the notification handler in a Windows thread."""
		self._generation += 1

	def _update(self) -> None:
		"""Apply the changes notified by Windows. Called in the main thread before the lists are used.
		The flags are cleared before rebuilding, so a notification received meanwhile is applied next time.
		"""
		if self._devicesChanged:
			self._devicesChanged = False
			# Devices may have appeared or disappeared, or the default output device whose applications go first has changed
			self._unsubscribeSessions()
			self._subscribeSessions()
			self._devices = self.getAllDevices(self._hide)

	def isOutdated(self, app: AppSource) -> bool:
		"""Check whether the previously found application must be looked up again:
		its audio session has expired, a new audio session has been created
		or the audio devices have changed since it was found.
		@param app: previously found application
		@type app: AppSource
		@return: whether the application must be looked up again
		@rtype: bool
		"""
		return app.generation != self._generation or app.isExpired

	@property
	def devices(self) -> List[DeviceSource]:
		"""Audio devices found by the last scan, the default output device is the first one.
		The list is rescanned if Windows has notified about changes of the audio devices.
		@return: audio devices whose volume can be adjusted
		@rtype: List[DeviceSource]
		"""
		self._update()
		return self._devices

	def scanDevices(self, hide: Iterable[str] = ()) -> None:
		"""Detect the audio devices whose volume can be adjusted and keep them until the next scan.
		It takes a few milliseconds, so it runs in the calling thread, which also uses the created COM objects.
		@param hide: IDs of the audio devices hidden in the add-on settings
		@type hide: Iterable[str]
		"""
		self._hide = list(hide)
		self._devicesChanged = False
		self._devices = self.getAllDevices(self._hide)

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
			defaultIds = self.getDefaultDeviceIds(enumerator, ERole.eMultimedia)
			communicationIds = self.getDefaultDeviceIds(enumerator, ERole.eCommunications)
			default = createDevice(defaultDevice, OutputDeviceSource, defaultIds, communicationIds)
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
					device = createDevice(immDevice, deviceClass, defaultIds, communicationIds)
				except COMError:
					continue
				if device.name:
					devices.append(device)
		return devices

	@staticmethod
	def getDefaultDeviceIds(enumerator: object, role: ERole) -> List[str]:
		"""Get the IDs of the default output and input devices for the specified role.
		@param enumerator: the device enumerator
		@type enumerator: pycaw.IMMDeviceEnumerator
		@param role: the role of the default devices, e.g. multimedia or communications
		@type role: ERole
		@return: IDs of the default devices, without the data flows that have no default device
		@rtype: List[str]
		"""
		ids: List[str] = []
		for flow in (EDataFlow.eRender, EDataFlow.eCapture):
			try:
				ids.append(enumerator.GetDefaultAudioEndpoint(flow.value, role.value).GetId())
			except COMError:
				continue
		return ids

	def getSessions(self, flow: EDataFlow) -> List[AudioSession]:
		"""Get the audio sessions of all active devices of the data flow, the default device goes first.
		The caller applies the notified changes with _update() before.
		@param flow: output (eRender) or input (eCapture) devices
		@type flow: EDataFlow
		@return: audio sessions of the devices
		@rtype: List[pycaw.AudioSession]
		"""
		sessions: List[AudioSession] = []
		for entry in self._sessionManagers:
			if entry.flow == flow:
				sessions.extend(listSessions(entry.manager))
		return sessions

	def _getApps(self, flow: EDataFlow, appClass: Type[AppT], hide: Iterable[str]) -> List[AppT]:
		"""Get the applications with audio sessions on the active devices of the data flow.
		There is one audio source per process name, in the order of the audio sessions,
		and all audio sessions of the application on all devices are adjusted together.
		@param flow: output (eRender) or input (eCapture) devices
		@type flow: EDataFlow
		@param appClass: class of the created audio sources
		@type appClass: Type[AppSource]
		@param hide: names of the processes hidden in the add-on settings
		@type hide: Iterable[str]
		@return: the applications
		@rtype: List[AppSource]
		"""
		self._update()
		# Read before the sessions are listed: a notification received meanwhile makes the result outdated
		generation = self._generation
		hidden = set(hide)
		groups: Dict[str, List[AudioSession]] = {}
		for session in self.getSessions(flow):
			name = session.Process.name() if session.Process else ""
			if name and name not in hidden:
				groups.setdefault(name, []).append(session)
		apps = [appClass(name, sessions) for name, sessions in groups.items()]
		for app in apps:
			app.generation = generation
		return apps

	def getApps(self, hide: Iterable[str] = ()) -> List[PlaybackAppSource]:
		"""Get the applications playing sound on any active output device.
		@param hide: names of the processes hidden in the add-on settings
		@type hide: Iterable[str]
		@return: applications playing sound, those of the default output device go first
		@rtype: List[PlaybackAppSource]
		"""
		return self._getApps(EDataFlow.eRender, PlaybackAppSource, hide)

	def getRecordingApps(self, hide: Iterable[str] = ()) -> List[RecordingAppSource]:
		"""Get the applications recording sound from any active input device.
		@param hide: names of the processes hidden in the add-on settings
		@type hide: Iterable[str]
		@return: applications recording sound, those of the default input device go first
		@rtype: List[RecordingAppSource]
		"""
		return self._getApps(EDataFlow.eCapture, RecordingAppSource, hide)

	def findApp(
		self,
		name: str,
		pid: int = 0,
		kind: SourceKind = SourceKind.PLAYBACK_APP,
	) -> Optional[AppSource]:
		"""Find the application playing or recording sound by its process ID or name.
		The process ID is not enough on its own: e.g. in web browsers the sound is usually played
		by a child process, not by the process of the focused window.
		The exact process name is preferred to a partial match (e.g. "code.exe" is not "vscode.exe").
		There is no fallback to another application: adjusting the volume of NVDA or of an unrelated program
		instead of the requested one would be confusing.
		@param name: full name or part of the process name
		@type name: str
		@param pid: ID of the process whose application is preferred, 0 to search by name only
		@type pid: int
		@param kind: playback or recording applications
		@type kind: SourceKind
		@return: the application, None if it has no audio session in the category
		@rtype: Optional[AppSource]
		"""
		apps: List[AppSource] = [
			*(self.getRecordingApps() if kind == SourceKind.RECORDING_APP else self.getApps()),
		]
		if pid:
			app = next((app for app in apps if pid in app.processIds), None)
			if app is not None:
				return app
		name = name.lower()
		return next((app for app in apps if app.name.lower() == name), None) or next(
			(app for app in apps if name in app.name.lower()),
			None,
		)


# Global instance shared by the global plugin and the settings panel
registry = AudioSourceRegistry()
