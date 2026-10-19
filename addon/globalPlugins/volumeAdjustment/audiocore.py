# audiocore.py
# Low-level access to Windows Core Audio: the device enumerator, volume interfaces, audio sessions and device properties
# A part of the NVDA Volume Adjustment add-on
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.
# Copyright (C) 2020-2026 Oleksandr Gryshchenko <grisov.nvaccess@mailgw.com>

from __future__ import annotations
from typing import Any, cast
from collections.abc import Sequence
from comtypes import CLSCTX_ALL, GUID, COMError
from logHandler import log
from pycaw.api.audiopolicy import IAudioSessionControl2, IAudioSessionManager2
from pycaw.api.endpointvolume import IAudioEndpointVolume
from pycaw.api.mmdeviceapi import IMMEndpoint
from pycaw.api.mmdeviceapi.depend.structures import PROPERTYKEY
from pycaw.constants import STGM
from pycaw.utils import AudioSession, AudioUtilities
from .audiotypes import Device, DeviceEnumerator, EndpointVolume, Session, SessionManager


def logDebugWarning(message: str) -> None:
	"""Log a debug warning with the exception being handled.
	Logger.debugWarning of NVDA has no type annotations, so it is called through this function.

	:param message: the message to log
	"""
	cast(Any, log).debugWarning(message, exc_info=True)


def getDeviceEnumerator() -> DeviceEnumerator:
	"""Get the enumerator of the audio devices.

	:return: the device enumerator
	:raises COMError: the audio service is not available
	"""
	return cast(DeviceEnumerator, AudioUtilities.GetDeviceEnumerator())


def getEndpointVolume(device: Device) -> EndpointVolume:
	"""Get the volume interface of the audio device.
	QueryInterface() adds a COM reference for the new pointer object. ctypes.cast() must not be used here:
	it creates a second pointer object without a reference, so the interface was released twice
	when the device objects were discarded, which crashed NVDA after the devices were rescanned.

	:param device: audio device
	:return: the volume interface of the device
	:raises COMError: the device is not available anymore
	"""
	# _iid_ is the way of comtypes to get the ID of an interface
	iid = IAudioEndpointVolume._iid_  # pyright: ignore[reportPrivateUsage]
	return cast(EndpointVolume, device.Activate(iid, CLSCTX_ALL, None).QueryInterface(IAudioEndpointVolume))


def getSessionManager(device: Device) -> SessionManager:
	"""Get the manager of the audio sessions of the audio device.

	:param device: audio device
	:return: the session manager of the device
	:raises COMError: the device is not available anymore
	"""
	# _iid_ is the way of comtypes to get the ID of an interface
	iid = IAudioSessionManager2._iid_  # pyright: ignore[reportPrivateUsage]
	return cast(SessionManager, device.Activate(iid, CLSCTX_ALL, None).QueryInterface(IAudioSessionManager2))


def getDataFlow(device: Device) -> int:
	"""Get the data flow of the audio device.

	:param device: audio device
	:return: the value of EDataFlow: output (eRender) or input (eCapture)
	:raises COMError: the device is not available anymore
	"""
	return cast(int, device.QueryInterface(IMMEndpoint).GetDataFlow())


def listSessions(manager: SessionManager) -> list[Session]:
	"""Get all audio sessions of the session manager of an audio device.
	Unlike AudioUtilities.GetAllSessions() from pycaw 20251023+, this does not wrap the device
	with AudioUtilities.CreateDevice(), which reads the whole property store of the device
	and makes every call several times slower.

	:param manager: the session manager of the audio device
	:return: audio sessions of the device, empty if the device is not available anymore
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

	:param device: audio device
	:param keys: property keys to read
	:return: values in the order of the keys, None for a property that is not set or cannot be read
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
