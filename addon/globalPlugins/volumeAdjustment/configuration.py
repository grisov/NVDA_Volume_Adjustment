# configuration.py
# The configuration of the add-on: the NVDA options and the data file with muted and hidden audio sources
# A part of the NVDA Volume Adjustment add-on
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.
# Copyright (C) 2020-2026 Oleksandr Gryshchenko <grisov.nvaccess@mailgw.com>

from __future__ import annotations

import json
from collections.abc import MutableMapping
from os import path
from typing import Any, cast

import addonHandler
import config
from globalVars import appArgs
from logHandler import log

addonName = path.basename(path.dirname(__file__))


# The summary of the add-on from its manifest, translated by NVDA; the manifest has no type annotations
addonSummary: str = cast(Any, addonHandler.Addon(path.join(path.dirname(__file__), "..", ".."))).manifest[
	"summary"
]


# The options of the add-on in the NVDA configuration
confspec: dict[str, str] = {
	"status": "boolean(default=true)",
	"step": "integer(default=1,min=1,max=20)",
	# Units of the announced volume level: percent, percent without the sign (number),
	# or decibels for the sources that provide them (audio devices)
	"units": 'option("percent", "number", "decibels", default="percent")',
	"focus": "boolean(default=true)",
	# Letters of the visible categories of audio sources, see model.SourceKind
	"categories": 'string(default="OIPR")',
	"announceCategories": "boolean(default=true)",
	# Announce the type, connection and default role of audio devices
	"deviceDetails": "boolean(default=false)",
	"muteCompletely": "boolean(default=false)",
	"mutePercentage": "integer(default=75,min=1,max=99)",
	"unmuteOnExit": "boolean(default=true)",
	"warnNvdaVolume": "boolean(default=true)",
	"gestures": "boolean(default=false)",
}


def getNvdaConfig(section: str) -> MutableMapping[str, Any]:
	"""Get a section of the NVDA configuration in the current configuration profile.
	NVDA declares config.conf as None until the configuration is loaded, so its type is given here once.
	The section is looked up on every call: the configuration profile may change at any time.

	:param section: the name of the section, e.g. "audio"
	:return: the section of the configuration
	"""
	return cast(Any, config.conf)[section]


def getAddonConfig() -> MutableMapping[str, Any]:
	"""Get the add-on section of the NVDA configuration in the current configuration profile.

	:return: the options of the add-on
	"""
	return getNvdaConfig(addonName)


class Configuration:
	"""Collection of devices and processes that need to be hidden,
	and list of muted audio sources.
	"""

	def __init__(self) -> None:
		"""File name for saving data and loading previously saved data."""
		super().__init__()
		# appArgs of NVDA has no type annotations
		configPath: str = cast(Any, appArgs).configPath
		self._file: str = path.join(configPath, addonName + ".json")
		self._data: dict[str, Any] = {}
		self.load()

	def load(self) -> None:
		"""Load previously saved data."""
		try:
			with open(self._file, encoding="utf-8") as f:
				self._data = json.load(f)
		except Exception:
			pass
		if "version" not in self._data:
			self._data = {"version": 0}

	def save(self) -> None:
		"""Save the data to an external file, an error is logged."""
		try:
			with open(self._file, "w", encoding="utf-8") as f:
				json.dump(self._data, f, skipkeys=True, ensure_ascii=False, indent=4)
		except Exception:
			log.error(f"Unable to save {self._file}", exc_info=True)

	@property
	def devices(self) -> dict[str, str]:
		"""Return a set of audio devices that need to be hidden.

		:return: collection of audio devices IDs
		"""
		return self._data.get("devices", {})

	@devices.setter
	def devices(self, devices: dict[str, str]) -> Configuration:
		"""Update a list of devices that needs to hide.

		:param devices: dict with devices in which the key is the ID and the value is the device name
		:return: updated self object
		"""
		self._data["devices"] = devices
		return self

	@property
	def quickMute(self) -> dict[str, str]:
		"""Input devices muted and unmuted together by one command.

		:return: dict with devices in which the key is the ID and the value is the device name
		"""
		return self._data.get("quickMute", {})

	@quickMute.setter
	def quickMute(self, devices: dict[str, str]) -> None:
		"""Update the input devices muted and unmuted together by one command.

		:param devices: dict with devices in which the key is the ID and the value is the device name
		"""
		self._data["quickMute"] = dict(devices)

	@property
	def processes(self) -> list[str]:
		"""List of processes that need to be hidden.

		:return: list of full names of processes
		"""
		return self._data.get("processes", [])

	@processes.setter
	def processes(self, processes: list[str]) -> Configuration:
		"""Update the list of processes to hide.

		:param processes: list of the full names of processes
		:return: updated self object
		"""
		self._data["processes"] = list(processes)
		return self

	def isChangedDevices(self, devices: dict[str, str]) -> bool:
		"""Determine if the new list of audio devices differs from the existing one.

		:param devices: dict with devices in which the key is the ID and the value is the device name
		:return: indication of whether the data are different
		"""
		return bool(set(self.devices) ^ set(devices))

	def isChangedProcesses(self, processes: list[str]) -> bool:
		"""Determine if the new processes list differs from the existing one.

		:param processes: list of the full names of processes
		:return: indication of whether the data are different
		"""
		return bool(set(self.processes) ^ set(processes))

	@property
	def muted(self) -> list[str]:
		"""List of audio sources that have been muted by the methods of this add-on.

		:return: list of names of audio sessions and IDs of audio devices
		"""
		return self._data.get("muted", [])

	def addMuted(self, name: str | None, level: float | None = None) -> Configuration:
		"""Add name of the audio source to the collection of muted.

		:param name: name of the audio session or ID of the audio device
		:param level: exact volume level before muting, restored when the audio source is unmuted
		:return: the current object instance for further reference to its attributes
		"""
		if name and name not in self.muted:
			# The list must be stored first: without the "muted" key the property returns a new empty list
			self._data.setdefault("muted", []).append(name)
			if level is not None:
				self._data.setdefault("mutedLevels", {})[name] = level
		return self

	def getMutedLevel(self, name: str) -> float | None:
		"""Get the exact volume level of the audio source before it was muted.

		:param name: name of the audio session or ID of the audio device
		:return: the volume level, None if it is unknown (e.g. muted by a previous version of the add-on)
		"""
		return self._data.get("mutedLevels", {}).get(name)

	def delMuted(self, name: str) -> Configuration:
		"""Remove name of the audio source from the list of muted.

		:param name: the name of the audio session or ID of the audio device
		:return: the current object instance for further reference to its attributes
		"""
		try:
			self.muted.remove(name)
		except ValueError:
			pass
		else:
			self._data["muted"] = self.muted
		self._data.get("mutedLevels", {}).pop(name, None)
		return self


# Global Configuration instance
cfg = Configuration()
