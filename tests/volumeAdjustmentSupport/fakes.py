# A part of the NVDA Volume Adjustment add-on
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.
# Copyright (C) 2020-2026 Oleksandr Gryshchenko <grisov.nvaccess@mailgw.com>

"""Fake audio sessions, audio devices and volume interfaces: the tests never touch real audio."""

from __future__ import annotations
import os
import struct
import sys
import types
from typing import Any

from . import events, module

# The exception of comtypes used by the add-on, the real one or its stand-in
COMError: type[Exception] = sys.modules["comtypes"].COMError


def float32(value: float) -> float:
	"""The value as Windows stores volume levels: a 32-bit float, e.g. 0.29 is read back as 0.28999999."""
	return struct.unpack("f", struct.pack("f", value))[0]


def comError() -> Exception:
	"""The error of a disconnected device."""
	try:
		return COMError(-2147023728, "Element not found", None)
	except TypeError:
		return COMError("Element not found")


class FakeSimpleVolume:
	"""ISimpleAudioVolume of an audio session."""

	def __init__(self, level: float = 1.0, mute: int = 0) -> None:
		self.level, self.mute = float32(level), mute

	def GetMasterVolume(self) -> float:
		return self.level

	def SetMasterVolume(self, level: float, context: object) -> None:
		self.level = float32(level)

	def GetMute(self) -> int:
		return self.mute

	def SetMute(self, mute: int, context: object) -> None:
		self.mute = int(mute)


class FakeChannelVolume:
	"""IChannelAudioVolume of an audio session."""

	def __init__(self, count: int = 2) -> None:
		self.levels = [1.0] * count

	def GetChannelCount(self) -> int:
		return len(self.levels)

	def GetChannelVolume(self, channel: int) -> float:
		return self.levels[channel]

	def SetChannelVolume(self, channel: int, level: float, context: object) -> None:
		self.levels[channel] = float32(level)


class FakeSession:
	"""pycaw.utils.AudioSession of a program."""

	def __init__(self, pid: int, name: str, level: float = 1.0, channels: int = 2, displayName: str = "") -> None:
		self.ProcessId = pid
		self.Process = types.SimpleNamespace(name=lambda: name)
		self.DisplayName = displayName
		# AudioSessionState: 1 is active, 2 is expired
		self.State = 1
		self.SimpleAudioVolume = FakeSimpleVolume(level)
		self.channels = FakeChannelVolume(channels)

	def channelAudioVolume(self) -> FakeChannelVolume:
		return self.channels


class FakeEndpointVolume:
	"""IAudioEndpointVolume of an audio device; the mute changes are recorded among the events."""

	def __init__(self, name: str, level: float = 0.5, channels: int = 2, mute: int = 0) -> None:
		self.name = name
		self.level, self.mute = float32(level), mute
		self.channels = [float32(level)] * channels
		self.broken = False

	def _check(self) -> None:
		if self.broken:
			raise comError()

	def GetMasterVolumeLevelScalar(self) -> float:
		self._check()
		return self.level

	def SetMasterVolumeLevelScalar(self, level: float, context: object) -> None:
		self._check()
		self.level = float32(level)

	def GetMasterVolumeLevel(self) -> float:
		self._check()
		# A made-up curve of the device: 0 dB at 100 %, -40 dB at 0 %
		return -40.0 * (1.0 - self.level)

	def GetChannelCount(self) -> int:
		self._check()
		return len(self.channels)

	def GetChannelVolumeLevelScalar(self, channel: int) -> float:
		self._check()
		return self.channels[channel]

	def SetChannelVolumeLevelScalar(self, channel: int, level: float, context: object) -> None:
		self._check()
		self.channels[channel] = float32(level)

	def GetChannelVolumeLevel(self, channel: int) -> float:
		self._check()
		return -40.0 * (1.0 - self.channels[channel])

	def GetVolumeRange(self) -> tuple[float, float, float]:
		return -40.0, 0.0, 0.5

	def GetMute(self) -> int:
		self._check()
		return self.mute

	def SetMute(self, mute: int, context: object) -> None:
		self._check()
		self.mute = int(mute)
		events.append(("mute", self.name, int(mute)))


def makeDevice(
	kind: str,
	id: str,
	name: str,
	level: float = 0.5,
	channels: int = 2,
	**attributes: Any,
) -> Any:
	"""Create an audio device of the add-on with a fake volume interface.

	:param kind: "output" or "input"
	:param id: the device ID
	:param name: the name of the device
	:param level: the volume level
	:param channels: the number of channels
	:param attributes: attributes of the device, e.g. formFactor or isDefaultDevice
	:return: the OutputDeviceSource or InputDeviceSource
	"""
	sources = module("sources")
	deviceClass = sources.OutputDeviceSource if kind == "output" else sources.InputDeviceSource
	device = deviceClass(id=id, name=name, volume=FakeEndpointVolume(name, level, channels))
	for attribute, value in attributes.items():
		setattr(device, attribute, value)
	return device


class FakeWarningDialog:
	"""Stands for the warning dialog about the volume of NVDA, answers as set in support.dialog."""

	def __init__(self, parent: object) -> None:
		from . import dialog

		self._dialog = dialog
		dialog["shown"] += 1
		self.dontShowAgainChk = types.SimpleNamespace(GetValue=lambda: dialog["dontShow"])

	def __enter__(self) -> FakeWarningDialog:
		return self

	def __exit__(self, *exc: object) -> bool:
		return False

	def ShowModal(self) -> int:
		return self._dialog["result"]


SOUNDS_DIR = os.path.join(os.path.dirname(module("microphones").__file__ or ""), "sounds")
