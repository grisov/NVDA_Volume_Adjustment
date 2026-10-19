# audiocore.py
# The main components for working with system audio devices and audio sessions of running processes
# A part of the NVDA Volume Adjustment add-on
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.
# Copyright (C) 2020-2026 Oleksandr Gryshchenko <grisov.nvaccess@mailgw.com>

from __future__ import annotations
import json
from os import path
import addonHandler
from typing import Any, cast
from collections.abc import MutableMapping, Sequence
import config
from comtypes import CLSCTX_ALL, GUID, COMError
from globalVars import appArgs
from logHandler import log
from pycaw.api.audiopolicy import IAudioSessionControl2, IAudioSessionManager2
from pycaw.api.endpointvolume import IAudioEndpointVolume
from pycaw.api.mmdeviceapi import IMMEndpoint
from pycaw.api.mmdeviceapi.depend.structures import PROPERTYKEY
from pycaw.constants import STGM
from pycaw.utils import AudioSession, AudioUtilities
from .audiotypes import Device, DeviceEnumerator, EndpointVolume, Session, SessionManager

addonName = path.basename(path.dirname(__file__))
# The summary of the add-on from its manifest, translated by NVDA; the manifest has no type annotations
addonSummary: str = cast(Any, addonHandler.Addon(path.join(path.dirname(__file__), "..", ".."))).manifest[
	"summary"
]


def logDebugWarning(message: str) -> None:
	"""Log a debug warning with the exception being handled.
	Logger.debugWarning of NVDA has no type annotations, so it is called through this function.
	@param message: the message to log
	@type message: str
	"""
	cast(Any, log).debugWarning(message, exc_info=True)


def getNvdaConfig(section: str) -> MutableMapping[str, Any]:
	"""Get a section of the NVDA configuration in the current configuration profile.
	NVDA declares config.conf as None until the configuration is loaded, so its type is given here once.
	The section is looked up on every call: the configuration profile may change at any time.
	@param section: the name of the section, e.g. "audio"
	@type section: str
	@return: the section of the configuration
	@rtype: MutableMapping[str, Any]
	"""
	return cast(Any, config.conf)[section]


def getAddonConfig() -> MutableMapping[str, Any]:
	"""Get the add-on section of the NVDA configuration in the current configuration profile.
	@return: the options of the add-on
	@rtype: MutableMapping[str, Any]
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
		@return: collection of audio devices IDs
		@rtype: Dict[str, str]
		"""
		return self._data.get("devices", {})

	@devices.setter
	def devices(self, devices: dict[str, str]) -> Configuration:
		"""Update a list of devices that needs to hide.
		@param devices: dict with devices in which the key is the ID and the value is the device name
		@type devices: Dict[str, str]
		@return: updated self object
		@rtype: Configuration
		"""
		self._data["devices"] = devices
		return self

	@property
	def quickMute(self) -> dict[str, str]:
		"""Input devices muted and unmuted together by one command.
		@return: dict with devices in which the key is the ID and the value is the device name
		@rtype: Dict[str, str]
		"""
		return self._data.get("quickMute", {})

	@quickMute.setter
	def quickMute(self, devices: dict[str, str]) -> None:
		"""Update the input devices muted and unmuted together by one command.
		@param devices: dict with devices in which the key is the ID and the value is the device name
		@type devices: Dict[str, str]
		"""
		self._data["quickMute"] = dict(devices)

	@property
	def processes(self) -> list[str]:
		"""List of processes that need to be hidden.
		@return: list of full names of processes
		@rtype: List[str]
		"""
		return self._data.get("processes", [])

	@processes.setter
	def processes(self, processes: list[str]) -> Configuration:
		"""Update the list of processes to hide.
		@param processes: list of the full names of processes
		@type processes: List[str]
		@return: updated self object
		@rtype: Configuration
		"""
		self._data["processes"] = list(processes)
		return self

	def isChangedDevices(self, devices: dict[str, str]) -> bool:
		"""Determine if the new list of audio devices differs from the existing one.
		@param devices: dict with devices in which the key is the ID and the value is the device name
		@type devices: Dict[str, str]
		@return: indication of whether the data are different
		@rtype: bool
		"""
		return bool(set(self.devices) ^ set(devices))

	def isChangedProcesses(self, processes: list[str]) -> bool:
		"""Determine if the new processes list differs from the existing one.
		@param processes: list of the full names of processes
		@type processes: List[str]
		@return: indication of whether the data are different
		@rtype: bool
		"""
		return bool(set(self.processes) ^ set(processes))

	@property
	def muted(self) -> list[str]:
		"""List of audio sources that have been muted by the methods of this add-on.
		@return: list of names of audio sessions and IDs of audio devices
		@rtype: List[str]
		"""
		return self._data.get("muted", [])

	def addMuted(self, name: str | None, level: float | None = None) -> Configuration:
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

	def getMutedLevel(self, name: str) -> float | None:
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


def getDeviceEnumerator() -> DeviceEnumerator:
	"""Get the enumerator of the audio devices.
	@return: the device enumerator
	@rtype: DeviceEnumerator
	@raise COMError: the audio service is not available
	"""
	return cast(DeviceEnumerator, AudioUtilities.GetDeviceEnumerator())


def getEndpointVolume(device: Device) -> EndpointVolume:
	"""Get the volume interface of the audio device.
	QueryInterface() adds a COM reference for the new pointer object. ctypes.cast() must not be used here:
	it creates a second pointer object without a reference, so the interface was released twice
	when the device objects were discarded, which crashed NVDA after the devices were rescanned.
	@param device: audio device
	@type device: Device
	@return: the volume interface of the device
	@rtype: EndpointVolume
	@raise COMError: the device is not available anymore
	"""
	# _iid_ is the way of comtypes to get the ID of an interface
	iid = IAudioEndpointVolume._iid_  # pyright: ignore[reportPrivateUsage]
	return cast(EndpointVolume, device.Activate(iid, CLSCTX_ALL, None).QueryInterface(IAudioEndpointVolume))


def getSessionManager(device: Device) -> SessionManager:
	"""Get the manager of the audio sessions of the audio device.
	@param device: audio device
	@type device: Device
	@return: the session manager of the device
	@rtype: SessionManager
	@raise COMError: the device is not available anymore
	"""
	# _iid_ is the way of comtypes to get the ID of an interface
	iid = IAudioSessionManager2._iid_  # pyright: ignore[reportPrivateUsage]
	return cast(SessionManager, device.Activate(iid, CLSCTX_ALL, None).QueryInterface(IAudioSessionManager2))


def getDataFlow(device: Device) -> int:
	"""Get the data flow of the audio device.
	@param device: audio device
	@type device: Device
	@return: the value of EDataFlow: output (eRender) or input (eCapture)
	@rtype: int
	@raise COMError: the device is not available anymore
	"""
	return cast(int, device.QueryInterface(IMMEndpoint).GetDataFlow())


def listSessions(manager: SessionManager) -> list[Session]:
	"""Get all audio sessions of the session manager of an audio device.
	Unlike AudioUtilities.GetAllSessions() from pycaw 20251023+, this does not wrap the device
	with AudioUtilities.CreateDevice(), which reads the whole property store of the device
	and makes every call several times slower.
	@param manager: the session manager of the audio device
	@type manager: SessionManager
	@return: audio sessions of the device, empty if the device is not available anymore
	@rtype: List[Session]
	"""
	try:
		sessionEnumerator = manager.GetSessionEnumerator()
	except COMError:
		logDebugWarning("Unable to get audio sessions of the audio device")
		return []
	sessions: list[Session] = []
	for i in range(sessionEnumerator.GetCount()):
		control = sessionEnumerator.GetSession(i)
		if control is None:
			continue
		sessions.append(cast(Session, AudioSession(control.QueryInterface(IAudioSessionControl2))))
	return sessions


# Format ID of the device property keys PKEY_Device_FriendlyName (14) and PKEY_Device_DeviceDesc (2)
DEVICE_PROPERTIES_FMTID = GUID("{a45c254e-df1c-4efd-8020-67d146a850e0}")
# Property keys of audio devices: (format ID, property ID)
PropertyKey = tuple[GUID, int]
PKEY_Device_FriendlyName: PropertyKey = (DEVICE_PROPERTIES_FMTID, 14)
PKEY_Device_DeviceDesc: PropertyKey = (DEVICE_PROPERTIES_FMTID, 2)
PKEY_Device_EnumeratorName: PropertyKey = (DEVICE_PROPERTIES_FMTID, 24)
PKEY_AudioEndpoint_FormFactor: PropertyKey = (GUID("{1da5d803-d492-4edd-8c23-e0c0ffee7f0e}"), 0)
PKEY_DeviceInterface_FriendlyName: PropertyKey = (GUID("{026e516e-b814-414b-83cd-856d6fef4822}"), 2)
# Device interface path of the audio adapter of the endpoint, e.g. \\?\usb#vid_35d8&pid_011d...
PKEY_Endpoint_AdapterInterfacePath: PropertyKey = (GUID("{233164c8-1b2c-4c7d-bc68-b671687a2567}"), 1)
# Type of an empty PROPVARIANT: the property is not set
VT_EMPTY = 0


def getDeviceProperties(device: Device, keys: Sequence[PropertyKey]) -> list[Any]:
	"""Read the specified properties of the audio device.
	Only these properties are read, unlike AudioUtilities.CreateDevice() which reads the whole property store.
	@param device: audio device
	@type device: Device
	@param keys: property keys to read
	@type keys: Sequence[PropertyKey]
	@return: values in the order of the keys, None for a property that is not set or cannot be read
	@rtype: List[Any]
	"""
	try:
		store = device.OpenPropertyStore(STGM.STGM_READ.value)
	except COMError:
		return [None] * len(keys)
	values: list[Any] = []
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
