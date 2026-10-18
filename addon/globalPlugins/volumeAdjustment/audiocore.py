# audiocore.py
# The main components for working with system audio devices and audio sessions of running processes
# A part of the NVDA Volume Adjustment add-on
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.
# Copyright (C) 2020-2026 Oleksandr Gryshchenko <grisov.nvaccess@mailgw.com>

from __future__ import annotations
import json
from os import path
from typing import Any, Dict, List, Optional, Sequence, Tuple
from comtypes import CLSCTX_ALL, GUID, COMError
from globalVars import appArgs
from logHandler import log
from pycaw.api.audiopolicy import IAudioSessionControl2, IAudioSessionManager2
from pycaw.api.mmdeviceapi import IMMDevice
from pycaw.api.mmdeviceapi.depend.structures import PROPERTYKEY
from pycaw.constants import STGM
from pycaw.utils import (
	AudioSession,
	AudioUtilities,
	EDataFlow,
	ERole,
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

	def addMuted(self, name: Optional[str], level: Optional[float] = None) -> Configuration:
		"""Add name of the audio source to the collection of muted.
		@param name: name of the audio session or ID of the audio device
		@type name: Optional[str]
		@param level: exact volume level before muting, restored when the audio source is unmuted
		@type level: Optional[float]
		@return: the current object instance for further reference to its attributes
		@rtype: Configuration
		"""
		if name and name not in self.muted:
			# The list must be stored first: without the "muted" key the property returns a new empty list
			self._data.setdefault("muted", []).append(name)
			if level is not None:
				self._data.setdefault("mutedLevels", {})[name] = level
		return self

	def getMutedLevel(self, name: str) -> Optional[float]:
		"""Get the exact volume level of the audio source before it was muted.
		@param name: name of the audio session or ID of the audio device
		@type name: str
		@return: the volume level, None if it is unknown (e.g. muted by a previous version of the add-on)
		@rtype: Optional[float]
		"""
		return self._data.get("mutedLevels", {}).get(name)

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
		self._data.get("mutedLevels", {}).pop(name, None)
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
# Property keys of audio devices: (format ID, property ID)
PropertyKey = Tuple[GUID, int]
PKEY_Device_FriendlyName: PropertyKey = (DEVICE_PROPERTIES_FMTID, 14)
PKEY_Device_DeviceDesc: PropertyKey = (DEVICE_PROPERTIES_FMTID, 2)
PKEY_Device_EnumeratorName: PropertyKey = (DEVICE_PROPERTIES_FMTID, 24)
PKEY_AudioEndpoint_FormFactor: PropertyKey = (GUID("{1da5d803-d492-4edd-8c23-e0c0ffee7f0e}"), 0)
PKEY_DeviceInterface_FriendlyName: PropertyKey = (GUID("{026e516e-b814-414b-83cd-856d6fef4822}"), 2)
# Type of an empty PROPVARIANT: the property is not set
VT_EMPTY = 0


def getDeviceProperties(immDevice: IMMDevice, keys: Sequence[PropertyKey]) -> List[Any]:
	"""Read the specified properties of the audio device.
	Only these properties are read, unlike AudioUtilities.CreateDevice() which reads the whole property store.
	@param immDevice: audio device
	@type immDevice: pycaw.IMMDevice
	@param keys: property keys to read
	@type keys: Sequence[PropertyKey]
	@return: values in the order of the keys, None for a property that is not set or cannot be read
	@rtype: List[Any]
	"""
	try:
		store = immDevice.OpenPropertyStore(STGM.STGM_READ.value)
	except COMError:
		return [None] * len(keys)
	values: List[Any] = []
	for fmtid, pid in keys:
		key = PROPERTYKEY()
		key.fmtid = fmtid
		key.pid = pid
		try:
			value = store.GetValue(key)
		except COMError:
			values.append(None)
			continue
		# pycaw returns the text "0:?" for a property that is not set
		values.append(None if value.vt == VT_EMPTY else value.GetValue())
		value.clear()
	return values
