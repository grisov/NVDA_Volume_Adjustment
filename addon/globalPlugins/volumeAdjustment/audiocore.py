# audiocore.py
# The main components for working with system audio devices and audio sessions of running processes
# A part of the NVDA Volume Adjustment add-on
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.
# Copyright (C) 2020-2026 Oleksandr Gryshchenko <grisov.nvaccess@mailgw.com>

from __future__ import annotations
import json
from os import path
from typing import Dict, List, Optional
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
