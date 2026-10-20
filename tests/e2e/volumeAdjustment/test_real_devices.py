# A part of the NVDA Volume Adjustment add-on
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.
# Copyright (C) 2020-2026 Oleksandr Gryshchenko <grisov.nvaccess@mailgw.com>

"""The add-on with the real audio devices of Windows, only reading them: attributes, levels, sessions, notifications.
Skipped without Windows, without the real comtypes and pycaw, or without an active output device.
"""

import gc
import unittest

from volumeAdjustmentSupport import REAL_WINDOWS, module

if REAL_WINDOWS:
	from pycaw.constants import DEVICE_STATE
	from pycaw.utils import AudioUtilities, EDataFlow, ERole


def activeOutputDevices() -> int:
	if not REAL_WINDOWS:
		return 0
	try:
		enumerator = AudioUtilities.GetDeviceEnumerator()
		return enumerator.EnumAudioEndpoints(EDataFlow.eRender.value, DEVICE_STATE.ACTIVE.value).GetCount()
	except Exception:
		return 0


@unittest.skipUnless(activeOutputDevices() > 0, "needs Windows with an active audio output device")
class TestRealDevices(unittest.TestCase):
	def setUp(self):
		self.registry = module("registry").AudioSourceRegistry()
		self.devices = self.registry.getAllDevices()
		self.model = module("model")
		self.sources = module("sources")

	def test_default_output_device_first_then_outputs_then_inputs(self):
		self.assertTrue(self.devices[0].isDefaultDevice)
		self.assertIsInstance(self.devices[0], self.sources.OutputDeviceSource)
		inputs = [isinstance(device, self.sources.InputDeviceSource) for device in self.devices]
		self.assertEqual(inputs, sorted(inputs))

	def test_attributes_of_every_device(self):
		for device in self.devices:
			self.assertIsInstance(device.formFactor, self.model.FormFactor)
			self.assertIsInstance(device.connection, self.model.Connection)
			self.assertTrue(device.name)

	def test_levels_and_decibels_within_the_range(self):
		for device in self.devices:
			level = device.volumeLevel
			self.assertTrue(0.0 <= level <= 1.0, device.name)
			low, high, _step = device.volume.GetVolumeRange()
			self.assertTrue(low - 0.01 <= device.getVolumeDecibels() <= high + 0.01, device.name)
			for channel in range(device.channelCount):
				self.assertIsNotNone(device.getVolumeDecibels(channel))

	def test_data_flow_of_every_device(self):
		devices = module("devices")
		for device in self.devices:
			self.assertEqual(devices.isInputDevice(device.id), isinstance(device, self.sources.InputDeviceSource))

	def test_output_devices_in_the_order_of_windows(self):
		devices = module("devices")
		outputs = devices.getOutputDevices()
		self.assertEqual(len(outputs), activeOutputDevices())
		ids = [id for id, _name in outputs]
		self.assertIn(devices.getDefaultOutputId(ERole.eMultimedia), ids)
		self.assertIn(devices.getDefaultOutputId(ERole.eCommunications), ids)
		self.assertIsNotNone(devices.getDevice(ids[0]))

	def test_input_devices_with_their_names(self):
		devices = module("devices")
		inputs = devices.getInputDevices()
		self.assertEqual(
			[id for id, _name in inputs],
			[device.id for device in self.devices if isinstance(device, self.sources.InputDeviceSource)],
		)
		self.assertTrue(all(name and devices.isInputDevice(id) for id, name in inputs))

	def test_applications_of_all_devices(self):
		self.registry.start()
		try:
			self.assertEqual(
				{entry.deviceId for entry in self.registry._sessionManagers if entry.flow == EDataFlow.eRender},
				{id for id, _name in module("devices").getOutputDevices()},
			)
			for app in [*self.registry.getApps(), *self.registry.getRecordingApps()]:
				self.assertTrue(0.0 <= app.volumeLevel <= 1.0, app.name)
		finally:
			self.registry.stop()

	def test_repeated_start_and_stop_does_not_crash(self):
		# The COM objects are released correctly: this crashed NVDA when ctypes.cast() was used
		for _ in range(30):
			self.registry.start()
			self.registry.getApps()
			self.registry.markDevicesChanged()
			_ = self.registry.devices
			self.registry.stop()
			gc.collect()
