# sources.py
# Audio sources whose volume can be adjusted: audio devices and applications playing or recording sound
# A part of the NVDA Volume Adjustment add-on
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.
# Copyright (C) 2020-2026 Oleksandr Gryshchenko <grisov.nvaccess@mailgw.com>

from __future__ import annotations
from abc import ABCMeta, abstractmethod
from typing import TypeVar, cast, override
from collections.abc import Callable, Iterable
from comtypes import COMError
from pycaw.constants import AudioSessionState
from .configuration import cfg, getAddonConfig
from .model import (
	Connection,
	FormFactor,
	SourceKey,
	SourceKind,
	formatCategories,
	parseCategories,
	stepLevel,
)
from .audiotypes import Device, EndpointVolume, Session, SimpleVolume
from .audiocore import (
	PKEY_AudioEndpoint_FormFactor,
	PKEY_Device_DeviceDesc,
	PKEY_Device_EnumeratorName,
	PKEY_Device_FriendlyName,
	PKEY_DeviceInterface_FriendlyName,
	PKEY_Endpoint_AdapterInterfacePath,
	getDeviceProperties,
	getEndpointVolume,
)


def callVolume[VolumeT, ResultT](
	volume: VolumeT | None,
	action: Callable[[VolumeT], ResultT],
	default: ResultT,
) -> ResultT:
	"""Call a volume interface of an audio source, which may be missing or belong to a disconnected device.

	:param volume: the volume interface, None if the audio source has none
	:param action: the call of the interface
	:param default: the result if there is no interface or the device is not available anymore
	:return: the result of the call or the default
	"""
	if volume is None:
		return default
	try:
		return action(volume)
	except COMError:
		return default


class SessionGroupVolume:
	"""Volume control of all audio sessions of one application, used like a single ISimpleAudioVolume:
	the volume level and the mute state are read from the first session and set for all of them.
	"""

	def __init__(self, volumes: list[SimpleVolume]) -> None:
		"""Volume control of the specified audio sessions.

		:param volumes: volume interfaces of the audio sessions, at least one
		"""
		super().__init__()
		self._volumes = volumes

	def GetMasterVolume(self) -> float:
		"""Get the volume level of the first audio session.

		:return: volume level (from 0.0 to 1.0)
		"""
		return self._volumes[0].GetMasterVolume()

	def SetMasterVolume(self, level: float, context: object | None) -> None:
		"""Set the volume level of all audio sessions.

		:param level: target volume level (from 0.0 to 1.0)
		:param context: event context passed to the audio sessions
		"""
		for volume in self._volumes:
			volume.SetMasterVolume(level, context)

	def GetMute(self) -> int:
		"""Get the mute state of the first audio session.

		:return: whether the audio session is muted
		"""
		return self._volumes[0].GetMute()

	def SetMute(self, mute: int, context: object | None) -> None:
		"""Mute or unmute all audio sessions.

		:param mute: whether to mute the audio sessions
		:param context: event context passed to the audio sessions
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
		volume: SimpleVolume | EndpointVolume | None = None,
	) -> None:
		"""The main properties of an audio source.

		:param id: audio source ID (audio device ID or audio session name)
		:param name: name of audio source
		:param volume: the interface to adjust the volume of the audio source
		"""
		super().__init__()
		self._id = id
		self._name = name
		self._volume = volume
		self._channel: int = 0
		# Whether the audio source is the default output device
		self.default: bool = False

	@property
	def id(self) -> str:
		"""ID of the current audio source.

		:return: device ID or audio session name
		"""
		return self._id

	def getVolumeDecibels(self, channel: int | None = None) -> float | None:
		"""Get the volume level in decibels, if the audio source provides it.
		Only audio devices do: the applications have just the levels from 0 to 100 %.

		:param channel: the number of the channel, None for the master volume level
		:return: the volume level in decibels, None if it is not available
		"""
		return None

	@property
	def mutedKey(self) -> str:
		"""Key of the audio source in the list of muted audio sources saved in the add-on configuration.

		:return: device ID or audio session name
		"""
		return self.id

	@property
	def name(self) -> str:
		"""Name of the current audio source.

		:return: audio source name
		"""
		return self._name

	@property
	def volume(self) -> SimpleVolume | EndpointVolume | None:
		"""An object that gives access to control the volume of the sound source.

		:return: volume control object
		"""
		return self._volume

	@property
	def channel(self) -> int:
		"""Get selected channel of the audio source.

		:return: the number of the audio channel
		"""
		return self._channel

	@channel.setter
	def channel(self, number: int) -> None:
		"""Select the channel of the audio source.

		:param number: the number of the audio channel
		"""
		try:
			number %= self.channelCount
		except ZeroDivisionError:
			number = 0
		self._channel = number

	@property
	@abstractmethod
	def volumeLevel(self) -> float:
		"""Get the volume level of the sound source.
		The method must be overridden for each type of sound sources.

		:return: current volume level (from 0.0 to 1.0)
		"""
		raise NotImplementedError("This property must be overridden in the child class!")

	@volumeLevel.setter
	@abstractmethod
	def volumeLevel(self, level: float) -> None:
		"""Set the volume level of the sound source.
		The method must be overridden for each type of sound sources.

		:param level: target volume level (from 0.0 to 1.0)
		"""
		raise NotImplementedError("This property must be overridden in the child class!")

	def volumeUp(self) -> float:
		"""Increase the volume level by the specified step.

		:return: current volume level
		"""
		if self.isMuted:
			self.unmute()
		level = self.volumeLevel = stepLevel(self.volumeLevel, getAddonConfig()["step"])
		return level

	def volumeDown(self) -> float:
		"""Decrease the volume level by the specified step.

		:return: current volume level
		"""
		if self.isMuted:
			if self.volumeLevel <= 0.0:
				# Already silent: unmuting just to mute again would only rewrite the configuration file
				return 0.0
			self.unmute()
		level = self.volumeLevel = stepLevel(self.volumeLevel, -getAddonConfig()["step"])
		return level

	def volumeMax(self) -> float:
		"""Set the maximum volume level of the audio source.

		:return: current volume level
		"""
		if self.isMuted:
			self.unmute()
		self.volumeLevel = 1.0
		return self.volumeLevel

	def volumeMin(self) -> float:
		"""Set the minimum volume level of the audio source.

		:return: current volume level
		"""
		if self.isMuted:
			self.unmute()
		self.volumeLevel = 0.0
		return self.volumeLevel

	@property
	def isMuted(self) -> bool:
		"""Check whether the current audio source is muted.

		:return: a state of the audio source (muted or no)
		"""
		volume = self.volume
		state = False if volume is None else bool(volume.GetMute())
		if not getAddonConfig()["muteCompletely"]:
			return (self.mutedKey in cfg.muted) or state
		return state

	def mute(self) -> None:
		"""Mute the current audio source, completely or by decreasing its volume level."""
		# Exact volume level before muting, restored when the audio source is unmuted
		level: float | None = None
		volume = self.volume
		if volume is None:
			return
		if getAddonConfig()["muteCompletely"]:
			volume.SetMute(1, None)
		elif not self.isMuted:
			level = self.volumeLevel
			self.volumeLevel = level * (100 - getAddonConfig()["mutePercentage"]) / 100.0
		# The file is written only when the list of muted audio sources changes
		if self.mutedKey not in cfg.muted:
			cfg.addMuted(self.mutedKey, level).save()

	def unmute(self) -> None:
		"""Unmute the current audio source and restore its volume level before muting."""
		volume = self.volume
		if volume is None:
			return
		volume.SetMute(0, None)
		if self.isMuted:
			level = cfg.getMutedLevel(self.mutedKey)
			if level is None:
				# Muted by a previous version of the add-on, which did not save the exact level
				percentage = getAddonConfig()["mutePercentage"]
				level = min(1.0, self.volumeLevel * 100.0 / (100.0 - percentage))
			self.volumeLevel = level
		# The file is written only when the list of muted audio sources changes
		if self.mutedKey in cfg.muted:
			cfg.delMuted(self.mutedKey).save()

	@property
	@abstractmethod
	def channelCount(self) -> int:
		"""Get the number of channels available in the current audio source.
		The method must be overridden for each type of sound sources.

		:return: the number of channels
		"""
		raise NotImplementedError("This property must be overridden in the child class!")

	@abstractmethod
	def getChannelVolumeLevel(self, channel: int = -1) -> float:
		"""Get the volume level of the specified audio source channel.
		The method must be overridden for each type of sound sources.

		:param channel: the number of the specified audio channel
		:return: the volume level
		"""
		raise NotImplementedError("This property must be overridden in the child class!")

	@abstractmethod
	def setChannelVolumeLevel(self, level: float, channel: int = -1) -> None:
		"""Set the volume level of the specified audio source channel.
		The method must be overridden for each type of sound sources.

		:param channel: the number of the specified audio channels
		:param level: target volume level (from 0.0 to 1.0)
		"""
		raise NotImplementedError("This property must be overridden in the child class!")

	def _stepChannelVolume(self, channel: int, step: int) -> float:
		"""Change the volume level of the channel by the step, the audio source is unmuted first.

		:param channel: the number of the audio channel, negative for the selected channel
		:param step: change in percent, negative to decrease the level
		:return: current volume level (from 0.0 to 1.0, -1.0 if it is not available)
		"""
		if self.isMuted:
			self.unmute()
		if channel < 0:
			channel = self.channel
		level: float = self.getChannelVolumeLevel(channel)
		if level < 0:
			return level
		level = stepLevel(level, step)
		self.setChannelVolumeLevel(level, channel)
		return level

	def _setChannelVolume(self, channel: int, level: float) -> float:
		"""Set the volume level of the channel, the audio source is unmuted first.

		:param channel: the number of the audio channel, negative for the selected channel
		:param level: target volume level (from 0.0 to 1.0)
		:return: current volume level (-1.0 if it is not available)
		"""
		if self.isMuted:
			self.unmute()
		if channel < 0:
			channel = self.channel
		self.setChannelVolumeLevel(level, channel)
		return self.getChannelVolumeLevel(channel)

	def channelVolumeUp(self, channel: int = -1) -> float:
		"""Increase the volume level for selected channel by the specified step.

		:param channel: the number of the specified audio channel
		:return: current volume level (from 0.0 to 1.0, -1.0 if it is not available)
		"""
		return self._stepChannelVolume(channel, getAddonConfig()["step"])

	def channelVolumeDown(self, channel: int = -1) -> float:
		"""Decrease the volume level for selected channel by the specified step.

		:param channel: the number of the specified audio channel
		:return: current volume level (from 0.0 to 1.0, -1.0 if it is not available)
		"""
		return self._stepChannelVolume(channel, -getAddonConfig()["step"])

	def channelVolumeMax(self, channel: int = -1) -> float:
		"""Set the maximum volume level of the selected channel.

		:param channel: the number of the specified audio channel
		:return: current volume level (1.0, -1.0 if it is not available)
		"""
		return self._setChannelVolume(channel, 1.0)

	def channelVolumeMin(self, channel: int = -1) -> float:
		"""Set the minimum volume level of the selected channel.

		:param channel: the number of the specified audio channel
		:return: current volume level (0.0, -1.0 if it is not available)
		"""
		return self._setChannelVolume(channel, 0.0)

	def channelVolumeAverage(self) -> float:
		"""Set the average volume level for all audio channels.

		:return: average volume level (from 0.0 to 1.0, -1.0 if it is not available)
		"""
		if self.channelCount <= 0:
			return -1.0
		level: float = (
			sum(self.getChannelVolumeLevel(channel) for channel in range(self.channelCount))
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
	@override
	def volume(self) -> EndpointVolume | None:
		"""The volume interface of the audio device.

		:return: volume control object
		"""
		return cast(EndpointVolume | None, self._volume)

	@property
	@override
	def volumeLevel(self) -> float:
		"""Get the volume level of the audio device.

		:return: current volume level (from 0.0 to 1.0, -1.0 if it is not available)
		"""
		return callVolume(self.volume, lambda volume: volume.GetMasterVolumeLevelScalar(), -1.0)

	@volumeLevel.setter
	@override
	def volumeLevel(self, level: float) -> None:
		"""Set the volume level of the audio device.

		:param level: target volume level (from 0.0 to 1.0)
		"""
		callVolume(self.volume, lambda volume: volume.SetMasterVolumeLevelScalar(level, None), None)

	@property
	@override
	def channelCount(self) -> int:
		"""Get the number of channels available in the current audio device.

		:return: the number of channels
		"""
		return callVolume(self.volume, lambda volume: volume.GetChannelCount(), 0)

	@override
	def getChannelVolumeLevel(self, channel: int = -1) -> float:
		"""Get the volume level of the specified audio source channel.

		:param channel: the number of the specified audio channel
		:return: the volume level
		"""
		if channel < 0:
			channel = self.channel
		return callVolume(self.volume, lambda volume: volume.GetChannelVolumeLevelScalar(channel), -1.0)

	@override
	def setChannelVolumeLevel(self, level: float, channel: int = -1) -> None:
		"""Set the volume level of the specified audio source channel.

		:param channel: the number of the specified audio channel
		:param level: target volume level (from 0.0 to 1.0)
		"""
		if channel < 0:
			channel = self.channel
		callVolume(self.volume, lambda volume: volume.SetChannelVolumeLevelScalar(channel, level, None), None)

	@override
	def getVolumeDecibels(self, channel: int | None = None) -> float | None:
		"""Get the volume level of the device in decibels (IAudioEndpointVolume).

		:param channel: the number of the channel, None for the master volume level
		:return: the volume level in decibels, None if it cannot be read
		"""
		if channel is None:
			return callVolume(self.volume, lambda volume: volume.GetMasterVolumeLevel(), None)
		return callVolume(self.volume, lambda volume: volume.GetChannelVolumeLevel(channel), None)


class OutputDeviceSource(DeviceSource):
	"""Audio output device, e.g. speakers or headphones."""

	kind = SourceKind.OUTPUT_DEVICE


class InputDeviceSource(DeviceSource):
	"""Audio input device, e.g. a microphone."""

	kind = SourceKind.INPUT_DEVICE


def createDevice(
	immDevice: Device,
	deviceClass: type[DeviceSource],
	defaultIds: Iterable[str] = (),
	communicationIds: Iterable[str] = (),
) -> DeviceSource:
	"""Create the presentation of the specified audio device with its attributes.

	:param immDevice: audio device
	:param deviceClass: class of the audio source according to the data flow of the device
	:param defaultIds: IDs of the default devices for multimedia
	:param communicationIds: IDs of the default devices for communications
	:return: audio device with the interface to adjust its volume
	"""
	id: str = immDevice.GetId() or "default"
	friendlyName, description, enumeratorName, formFactor, adapterName, adapterPath = getDeviceProperties(
		immDevice,
		(
			PKEY_Device_FriendlyName,
			PKEY_Device_DeviceDesc,
			PKEY_Device_EnumeratorName,
			PKEY_AudioEndpoint_FormFactor,
			PKEY_DeviceInterface_FriendlyName,
			PKEY_Endpoint_AdapterInterfacePath,
		),
	)
	name: str = next((value for value in (friendlyName, description) if isinstance(value, str) and value), id)
	device = deviceClass(id=id, name=name, volume=getEndpointVolume(immDevice))
	try:
		device.formFactor = FormFactor(formFactor)
	except ValueError:
		device.formFactor = FormFactor.UNKNOWN
	device.connection = Connection.fromEnumeratorName(enumeratorName, adapterPath)
	device.adapterName = adapterName if isinstance(adapterName, str) else ""
	device.isDefaultDevice = id in defaultIds
	device.isDefaultCommunicationDevice = id in communicationIds
	return device


class AppSource(AudioSource):
	"""All audio sessions of one running application (process name), adjusted together."""

	kind: SourceKind

	def __init__(self, name: str, sessions: list[Session]) -> None:
		"""Initialize the application with its audio sessions.

		:param name: the full name of the process, also used as the ID of the muted audio source
		:param sessions: audio sessions of the application, at least one
		"""
		super().__init__(
			id=name,
			name=name,
			volume=SessionGroupVolume([session.SimpleAudioVolume for session in sessions]),
		)
		self._sessions = sessions
		# Version of the registry state when the application was looked up, see AudioSourceRegistry.isOutdated()
		self.generation: int = 0

	@property
	def processIds(self) -> list[int]:
		"""IDs of the processes playing the audio sessions of the application.

		:return: process IDs
		"""
		return [session.ProcessId for session in self._sessions]

	@property
	def title(self) -> str:
		"""Getter method - returns human friendly name of the application.

		:return: human friendly name of the application
		"""
		try:
			name = self._sessions[0].DisplayName
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

		:return: whether any of the audio sessions has expired or is not available anymore
		"""
		try:
			return any(session.State == AudioSessionState.Expired for session in self._sessions)
		except (AttributeError, COMError):
			return True

	@property
	@override
	def volume(self) -> SimpleVolume | None:
		"""The volume interface of all audio sessions of the application.

		:return: volume control object
		"""
		return cast(SimpleVolume | None, self._volume)

	@property
	@override
	def volumeLevel(self) -> float:
		"""Get the volume level of the audio session.

		:return: current volume level (from 0.0 to 1.0, -1.0 if it is not available)
		"""
		return callVolume(self.volume, lambda volume: volume.GetMasterVolume(), -1.0)

	@volumeLevel.setter
	@override
	def volumeLevel(self, level: float) -> None:
		"""Set the volume level of the audio session.

		:param level: target volume level (from 0.0 to 1.0)
		"""
		callVolume(self.volume, lambda volume: volume.SetMasterVolume(level, None), None)

	@property
	@override
	def channelCount(self) -> int:
		"""Get the number of channels of the first audio session of the application (usually 2).
		The channel levels are relative to the volume level of the session.
		NVDA sound split changes the same channels, see GlobalPlugin.getChannelSource().

		:return: the number of channels, 0 if they are not available
		"""
		try:
			return self._sessions[0].channelAudioVolume().GetChannelCount()
		except (AttributeError, COMError):
			return 0

	@override
	def getChannelVolumeLevel(self, channel: int = -1) -> float:
		"""Get the volume level of the specified channel of the first audio session.

		:param channel: the number of the specified audio channel
		:return: the volume level, -1.0 if it is not available
		"""
		if channel < 0:
			channel = self.channel
		try:
			return self._sessions[0].channelAudioVolume().GetChannelVolume(channel)
		except (AttributeError, COMError):
			return -1.0

	@override
	def setChannelVolumeLevel(self, level: float, channel: int = -1) -> None:
		"""Set the volume level of the specified channel of all audio sessions of the application.
		Sessions without such a channel are skipped.

		:param channel: the number of the specified audio channel
		:param level: target volume level (from 0.0 to 1.0)
		"""
		if channel < 0:
			channel = self.channel
		for session in self._sessions:
			try:
				channelVolume = session.channelAudioVolume()
				if channel < channelVolume.GetChannelCount():
					channelVolume.SetChannelVolume(channel, level, None)
			except (AttributeError, COMError):
				continue


class PlaybackAppSource(AppSource):
	"""Application playing sound."""

	kind = SourceKind.PLAYBACK_APP


class RecordingAppSource(AppSource):
	"""Application recording sound."""

	kind = SourceKind.RECORDING_APP

	@property
	@override
	def mutedKey(self) -> str:
		"""Key of the application in the list of muted audio sources, distinct from the same playback application.
		A colon cannot be a part of a file name, so it cannot clash with a process name.

		:return: the process name with a prefix
		"""
		return f"recording:{self.name}"


AppT = TypeVar("AppT", bound=AppSource)


def getSourceKey(source: AudioSource) -> SourceKey:
	"""Get the key that identifies the audio source between keypresses.

	:param source: the audio source
	:return: the category and the ID of the audio source
	"""
	return source.kind, source.id


def getVisibleCategories() -> list[SourceKind]:
	"""Categories of audio sources available for switching, in their order.

	:return: the visible categories, all of them if the saved value contains none
	"""
	return parseCategories(getAddonConfig()["categories"])


def setVisibleCategories(categories: list[SourceKind]) -> None:
	"""Save the visible categories of audio sources, always in the order of the categories.

	:param categories: the categories to show
	"""
	getAddonConfig()["categories"] = formatCategories(categories)
