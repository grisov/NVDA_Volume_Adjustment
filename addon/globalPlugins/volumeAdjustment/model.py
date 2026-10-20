# model.py
# Basic types and calculations of the add-on without dependencies on Windows or NVDA, covered by unit tests
# A part of the NVDA Volume Adjustment add-on
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.
# Copyright (C) 2020-2026 Oleksandr Gryshchenko <grisov.nvaccess@mailgw.com>

from __future__ import annotations

import math
from collections.abc import Iterable
from enum import Enum, IntEnum

# Windows stores volume levels as 32-bit floats: 29 % is read back as 28.999999 %.
# A level closer than this to a whole percent (in percent) is treated as that whole percent.
LEVEL_TOLERANCE = 0.01


def stepLevel(level: float, step: int) -> float:
	"""Change the volume level by the step in percent, stopping at whole percents.
	A level at a whole percent changes exactly by the step. A level set by another program between
	whole percents first moves to the next whole percent in the direction of the step,
	so every keypress changes the announced level by the step.

	:param level: current volume level (from 0.0 to 1.0)
	:param step: change in percent, negative to decrease the level
	:return: new volume level (from 0.0 to 1.0)
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
SourceKey = tuple[SourceKind, str]


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
	def fromEnumeratorName(cls, name: str | None, adapterPath: str | None = None) -> Connection:
		"""Guess the connection from the name of the device enumerator and the interface path of the adapter.
		USB devices connected through Intel USB Audio Offload are enumerated by the Intel audio driver (INTELAUDIO)
		like the internal sound card: only the interface path of their adapter tells they are USB devices.

		:param name: value of the PKEY_Device_EnumeratorName property
		:param adapterPath: the device interface path of the audio adapter, see PKEY_Endpoint_AdapterInterfacePath
		:return: the connection of the device
		"""
		path = (adapterPath or "").lower()
		# Link type 6 of Intel Smart Sound Technology is USB, e.g. intelaudio#ctlr_dev_51ca&linktype_06...\intcusbwave...
		if "linktype_06" in path or "intcusbwave" in path:
			return cls.USB
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


def parseCategories(letters: str) -> list[SourceKind]:
	"""Get the categories of audio sources from their letters saved in the configuration, in their order.

	:param letters: letters of the categories, e.g. "OIPR"
	:return: the categories, all of them if the text contains none
	"""
	return [kind for kind in SourceKind if kind.value in letters] or list(SourceKind)


def formatCategories(categories: Iterable[SourceKind]) -> str:
	"""Get the letters of the categories of audio sources to save in the configuration, always in their order.

	:param categories: the categories
	:return: the letters, e.g. "OIPR"
	"""
	selected = set(categories)
	return "".join(kind.value for kind in SourceKind if kind in selected)
