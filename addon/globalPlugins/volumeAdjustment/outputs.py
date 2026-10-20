# outputs.py
# Switching the output device of NVDA and the default output and input devices of Windows
# A part of the NVDA Volume Adjustment add-on
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.
# Copyright (C) 2020-2026 Oleksandr Gryshchenko <grisov.nvaccess@mailgw.com>

from __future__ import annotations
from enum import Enum
import tones
import ui
from pycaw.utils import ERole
from synthDriverHandler import getSynth, setSynth
from utils.mmdevice import getOutputDevices as getNvdaOutputDevices
from .devices import getDefaultOutputId, getDevice, getInputDevices, getOutputDevices, setDefaultDevice
from .configuration import getNvdaConfig
from .messages import announceDeviceNotAvailable, announceUnableToSetDefaultDevice, getAnnouncedDeviceDetails


class OutputTarget(Enum):
	"""What the switching between audio devices changes."""

	# The output device of NVDA speech and sounds
	NVDA = "nvda"
	# The default output device of Windows (console and multimedia roles)
	DEFAULT = "default"
	# The default communication device of Windows
	COMMUNICATION = "communication"
	# The default input device of Windows (console and multimedia roles)
	DEFAULT_INPUT = "defaultInput"
	# The default communication input device of Windows
	COMMUNICATION_INPUT = "communicationInput"

	@property
	def isInput(self) -> bool:
		"""Whether the target is a default input device of Windows.

		:return: True for the default input devices, False for the output devices
		"""
		return self in (OutputTarget.DEFAULT_INPUT, OutputTarget.COMMUNICATION_INPUT)


class OutputSwitcher:
	"""Switches the output of NVDA or a default device of Windows to another device."""

	def getCurrentOutputId(self, target: OutputTarget) -> str:
		"""Get the ID of the output device currently used for the target.

		:param target: NVDA output or a default device of Windows
		:return: the device ID, "default" or empty if NVDA or Windows uses no specific device
		"""
		if target == OutputTarget.NVDA:
			return getNvdaConfig("audio")["outputDevice"]
		if target == OutputTarget.DEFAULT:
			return getDefaultOutputId(ERole.eMultimedia)
		return getDefaultOutputId(ERole.eCommunications)

	def setOutputDevice(self, target: OutputTarget, id: str, name: str) -> None:
		"""Switch the output of NVDA or a default device of Windows to the specified device and announce its name.

		:param target: NVDA output or a default device of Windows
		:param id: the device ID, the configuration default of NVDA for its "default" output
		:param name: the name of the device to announce
		"""
		if target == OutputTarget.NVDA:
			getNvdaConfig("audio")["outputDevice"] = id
			# The synthesizer is restarted to use the new output device
			synth = getSynth()
			if synth is not None and setSynth(synth.name):
				tones.terminate()
				tones.initialize()
		else:
			roles = (
				[ERole.eCommunications]
				if target in (OutputTarget.COMMUNICATION, OutputTarget.COMMUNICATION_INPUT)
				else [ERole.eConsole, ERole.eMultimedia]
			)
			if not setDefaultDevice(id, roles):
				announceUnableToSetDefaultDevice()
				return
		# The attributes are read after switching: the default roles may have changed
		ui.message(", ".join([name, *getAnnouncedDeviceDetails(getDevice(id))]))

	def selectOutputDeviceById(self, target: OutputTarget, id: str, name: str) -> None:
		"""Switch to the output or input device found when NVDA was started, if it is still available.

		:param target: NVDA output or a default device of Windows
		:param id: the device ID
		:param name: the name of the device
		"""
		activeDevices = getInputDevices() if target.isInput else getOutputDevices()
		if id not in [deviceId for deviceId, _deviceName in activeDevices]:
			announceDeviceNotAvailable(name)
			return
		self.setOutputDevice(target, id, name)

	def selectOutputDeviceByStep(self, target: OutputTarget, step: int) -> None:
		"""Switch to the next or previous output device in the order of Windows.
		If no specific device is used (e.g. NVDA follows the default device), the first or last one is selected.

		:param target: NVDA output or a default device of Windows
		:param step: offset in the list of output devices (usually 1 or -1)
		"""
		outputDevices = getOutputDevices()
		if not outputDevices:
			return
		ids = [id for id, _name in outputDevices]
		current = self.getCurrentOutputId(target)
		if current in ids:
			index = (ids.index(current) + step) % len(outputDevices)
		else:
			index = 0 if step > 0 else -1
		self.setOutputDevice(target, *outputDevices[index])

	def switchNvdaOutputToDefault(self) -> None:
		"""Switch NVDA output to the default output device of Windows, so NVDA follows its changes."""
		# The first item is the "default" output with its name translated by NVDA; the devices are not read
		default = next(getNvdaOutputDevices(includeDefault=True))
		self.setOutputDevice(OutputTarget.NVDA, default.id, default.friendlyName)
