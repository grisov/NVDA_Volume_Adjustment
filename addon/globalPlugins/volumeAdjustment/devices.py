# devices.py
# Audio devices of Windows: the output devices, the default devices and the data flow of a device
# A part of the NVDA Volume Adjustment add-on
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.
# Copyright (C) 2020-2026 Oleksandr Gryshchenko <grisov.nvaccess@mailgw.com>

from __future__ import annotations
import os
import subprocess
from typing import Any, cast
from comtypes import COMError
from logHandler import log
from pycaw.constants import DEVICE_STATE
from pycaw.utils import AudioUtilities, EDataFlow, ERole
from .audiocore import (
	PKEY_Device_FriendlyName,
	getDataFlow,
	getDeviceEnumerator,
	getDeviceProperties,
	logDebugWarning,
)
from .audiotypes import DeviceEnumerator
from .sources import DeviceSource, InputDeviceSource, OutputDeviceSource, createDevice


def getDevice(id: str) -> DeviceSource | None:
	"""Get the active audio device with its current attributes, e.g. after it has become a default device.

	:param id: the device ID
	:return: the audio device, None if it is not available
	"""
	try:
		enumerator = getDeviceEnumerator()
		immDevice = enumerator.GetDevice(id)
		deviceClass = (
			InputDeviceSource if getDataFlow(immDevice) == EDataFlow.eCapture.value else OutputDeviceSource
		)
		return createDevice(
			immDevice,
			deviceClass,
			getDefaultDeviceIds(enumerator, ERole.eMultimedia),
			getDefaultDeviceIds(enumerator, ERole.eCommunications),
		)
	except COMError:
		return None


def isInputDevice(id: str) -> bool:
	"""Check whether the audio device is an input device, also when it is unplugged or disabled now.

	:param id: the device ID
	:return: whether the device records sound
	"""
	try:
		return getDataFlow(getDeviceEnumerator().GetDevice(id)) == EDataFlow.eCapture.value
	except COMError:
		# A device removed from Windows: the data flow is the second number of its ID, e.g. {0.0.1.00000000}.{...}
		return id.startswith("{0.0.1.")


def getOutputDevices() -> list[tuple[str, str]]:
	"""Get all active output devices in the order of Windows, regardless of the hidden devices and categories.
	Only the names are read, unlike utils.mmdevice.getOutputDevices() of NVDA, which wraps every device
	with AudioUtilities.CreateDevice() and reads its whole property store.

	:return: IDs and names of the output devices
	"""
	try:
		collection = getDeviceEnumerator().EnumAudioEndpoints(
			EDataFlow.eRender.value,
			DEVICE_STATE.ACTIVE.value,
		)
		count = collection.GetCount()
	except COMError:
		logDebugWarning("Unable to list the active output devices")
		return []
	devices: list[tuple[str, str]] = []
	for i in range(count):
		try:
			immDevice = collection.Item(i)
			id = immDevice.GetId()
		except COMError:
			continue
		(name,) = getDeviceProperties(immDevice, [PKEY_Device_FriendlyName])
		devices.append((id, name if isinstance(name, str) and name else id))
	return devices


def getDefaultOutputId(role: ERole) -> str:
	"""Get the ID of the default output device of Windows for the role.

	:param role: multimedia or communications
	:return: the device ID, empty if there is no default output device
	"""
	try:
		return getDeviceEnumerator().GetDefaultAudioEndpoint(EDataFlow.eRender.value, role.value).GetId()
	except COMError:
		return ""


def setDefaultOutput(id: str, roles: list[ERole]) -> bool:
	"""Make the output device the default device of Windows for the roles.
	All programs that use the default device, including NVDA with its "default" output, move to it immediately.

	:param id: the device ID
	:param roles: the roles, e.g. console and multimedia, or communications
	:return: whether the default device has been changed
	"""
	try:
		cast(Any, AudioUtilities).SetDefaultDevice(id, roles)
	except (OSError, COMError):
		log.error(f"Unable to set the default output device {id}", exc_info=True)
		return False
	return True


def getDefaultDeviceIds(enumerator: DeviceEnumerator, role: ERole) -> list[str]:
	"""Get the IDs of the default output and input devices for the specified role.

	:param enumerator: the device enumerator
	:param role: the role of the default devices, e.g. multimedia or communications
	:return: IDs of the default devices, without the data flows that have no default device
	"""
	ids: list[str] = []
	for flow in (EDataFlow.eRender, EDataFlow.eCapture):
		try:
			ids.append(enumerator.GetDefaultAudioEndpoint(flow.value, role.value).GetId())
		except COMError:
			continue
	return ids


def openSoundDialog() -> None:
	"""Open the classic Sound dialog of the Windows Control Panel (mmsys.cpl),
	which lists all playback and recording devices with their properties.
	If it is missing (e.g. removed in a future or customized Windows), the Sound page of the Windows Settings is opened.
	"""
	system32 = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32")
	if os.path.isfile(os.path.join(system32, "mmsys.cpl")):
		try:
			_ = subprocess.Popen([os.path.join(system32, "control.exe"), "mmsys.cpl"])
			return
		except OSError:
			log.error("Unable to open the Sound dialog of Windows", exc_info=True)
	try:
		os.startfile("ms-settings:sound")
	except OSError:
		log.error("Unable to open the Sound settings of Windows", exc_info=True)
