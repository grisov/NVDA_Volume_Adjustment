# audiotypes.py
# Types of the Windows Core Audio interfaces and pycaw objects used by the add-on
# A part of the NVDA Volume Adjustment add-on
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.
# Copyright (C) 2020-2026 Oleksandr Gryshchenko <grisov.nvaccess@mailgw.com>

"""comtypes creates the methods of COM interfaces at run time and pycaw has no type annotations,
so the type checker knows nothing about them. These protocols describe only the methods the add-on uses.
The objects get these types in audiocore, where they are obtained from pycaw.
"""

from __future__ import annotations

from typing import Any, Protocol

import psutil


class SimpleVolume(Protocol):
	"""ISimpleAudioVolume: the volume of an audio session."""

	def GetMasterVolume(self) -> float: ...

	def SetMasterVolume(self, level: float, context: object | None) -> None: ...

	def GetMute(self) -> int: ...

	def SetMute(self, mute: int, context: object | None) -> None: ...


class ChannelVolume(Protocol):
	"""IChannelAudioVolume: the volume of the channels of an audio session."""

	def GetChannelCount(self) -> int: ...

	def GetChannelVolume(self, channel: int) -> float: ...

	def SetChannelVolume(self, channel: int, level: float, context: object | None) -> None: ...


class EndpointVolume(Protocol):
	"""IAudioEndpointVolume: the volume of an audio device."""

	def GetMasterVolumeLevelScalar(self) -> float: ...

	def SetMasterVolumeLevelScalar(self, level: float, context: object | None) -> None: ...

	def GetMasterVolumeLevel(self) -> float: ...

	def GetChannelCount(self) -> int: ...

	def GetChannelVolumeLevelScalar(self, channel: int) -> float: ...

	def SetChannelVolumeLevelScalar(self, channel: int, level: float, context: object | None) -> None: ...

	def GetChannelVolumeLevel(self, channel: int) -> float: ...

	def GetVolumeRange(self) -> tuple[float, float, float]: ...

	def GetMute(self) -> int: ...

	def SetMute(self, mute: int, context: object | None) -> None: ...


class PropVariant(Protocol):
	"""PROPVARIANT: the value of a property of an audio device."""

	vt: int

	def GetValue(self) -> Any: ...

	def clear(self) -> None: ...


class PropertyStore(Protocol):
	"""IPropertyStore: the properties of an audio device."""

	def GetValue(self, key: Any) -> PropVariant: ...


class Device(Protocol):
	"""IMMDevice: an audio device."""

	def GetId(self) -> str: ...

	def Activate(self, iid: Any, clsctx: int, params: None) -> Any: ...

	def OpenPropertyStore(self, access: int) -> PropertyStore: ...

	def QueryInterface(self, interface: Any) -> Any: ...


class DeviceCollection(Protocol):
	"""IMMDeviceCollection: a list of audio devices."""

	def GetCount(self) -> int: ...

	def Item(self, index: int) -> Device: ...


class DeviceEnumerator(Protocol):
	"""IMMDeviceEnumerator: lists the audio devices and notifies about their changes."""

	def EnumAudioEndpoints(self, flow: int, stateMask: int) -> DeviceCollection: ...

	def GetDefaultAudioEndpoint(self, flow: int, role: int) -> Device: ...

	def GetDevice(self, id: str) -> Device: ...

	def RegisterEndpointNotificationCallback(self, client: Any) -> None: ...

	def UnregisterEndpointNotificationCallback(self, client: Any) -> None: ...


class SessionControl(Protocol):
	"""IAudioSessionControl: an audio session as returned by the session enumerator."""

	def QueryInterface(self, interface: Any) -> Any: ...


class SessionEnumerator(Protocol):
	"""IAudioSessionEnumerator: the audio sessions of an audio device."""

	def GetCount(self) -> int: ...

	def GetSession(self, index: int) -> SessionControl | None: ...


class SessionManager(Protocol):
	"""IAudioSessionManager2: the audio sessions of an audio device and the notifications about new ones."""

	def GetSessionEnumerator(self) -> SessionEnumerator: ...

	def RegisterSessionNotification(self, notification: Any) -> None: ...

	def UnregisterSessionNotification(self, notification: Any) -> None: ...


class Session(Protocol):
	"""pycaw.utils.AudioSession: an audio session of a running program."""

	@property
	def ProcessId(self) -> int: ...

	@property
	def Process(self) -> psutil.Process | None: ...

	@property
	def DisplayName(self) -> str: ...

	@property
	def State(self) -> int: ...

	@property
	def SimpleAudioVolume(self) -> SimpleVolume: ...

	def channelAudioVolume(self) -> ChannelVolume: ...
