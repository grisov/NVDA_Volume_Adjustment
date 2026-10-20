# A part of the NVDA Volume Adjustment add-on
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.
# Copyright (C) 2020-2026 Oleksandr Gryshchenko <grisov.nvaccess@mailgw.com>

"""Switching the output device of NVDA and the default output, input and communication devices of Windows."""

from volumeAdjustmentSupport import audio, events, options
from volumeAdjustmentSupport.case import AddonTestCase
from volumeAdjustmentSupport.fakes import makeDevice

PREFIXES = ("switchNvdaOutputToDevice", "setDefaultOutputDevice", "setCommunicationDevice")
INPUT_PREFIXES = ("setDefaultInputDevice", "setCommunicationInputDevice")


class SwitchingTestCase(AddonTestCase):
	def setUp(self):
		super().setUp()
		self.windowsOutputs[:] = [
			("{realtek}", "Realtek speakers"),
			("{usb}", "USB headphones"),
			("{hdmi}", "HDMI monitor"),
		]
		self.windowsInputs[:] = [
			("{0.0.1.00000000}.{array}", "Microphone array"),
			("{0.0.1.00000000}.{headset}", "Headset microphone"),
		]
		self.windows.update(default="{usb}", communication="{realtek}")
		self.plugin.bindSwitchingMethods()


class TestDeviceCommands(SwitchingTestCase):
	def test_one_command_per_device_found_when_nvda_starts(self):
		for prefix in PREFIXES:
			self.assertTrue(all(hasattr(self.plugin, f"script_{prefix}{number}") for number in (1, 2, 3)))
			self.assertFalse(hasattr(self.plugin, f"script_{prefix}4"))

	def test_descriptions_with_number_and_name(self):
		self.assertEqual(
			self.plugin.script_setCommunicationDevice3.__doc__,
			"Set the device 3 (HDMI monitor) as the default communication device",
		)
		self.assertEqual(
			self.plugin.script_switchNvdaOutputToDevice1.__doc__,
			"Switch NVDA output to the device 1 (Realtek speakers)",
		)

	def test_gestures_only_with_the_option_and_up_to_f12(self):
		self.assertNotIn("kb:NVDA+windows+f1", self.plugin.boundGestures)
		options["gestures"] = True
		self.windowsOutputs[:] = [(f"{{d{n}}}", f"Device {n}") for n in range(1, 15)]
		self.plugin.bindSwitchingMethods()
		self.assertEqual(self.plugin.boundGestures["kb:NVDA+windows+shift+f12"], "setDefaultOutputDevice12")
		self.assertNotIn("kb:NVDA+windows+f13", self.plugin.boundGestures)
		self.assertTrue(hasattr(self.plugin, "script_setDefaultOutputDevice14"))

	def test_commands_of_removed_devices_are_deleted_when_recreated(self):
		self.windowsOutputs.pop()
		self.plugin.bindSwitchingMethods()
		self.assertFalse(any(hasattr(self.plugin, f"script_{prefix}3") for prefix in PREFIXES))


class TestNvdaOutput(SwitchingTestCase):
	def test_device_by_number(self):
		self.assertEqual(self.press("switchNvdaOutputToDevice3"), ["HDMI monitor"])
		self.assertEqual(audio["outputDevice"], "{hdmi}")
		self.assertIn(("setSynth", "espeak"), events)
		self.assertIn("tones.initialize", events)

	def test_next_and_previous_wrap_around(self):
		self.assertEqual(self.press("nextOutputDevice"), ["Realtek speakers"])
		self.assertEqual(self.press("prevOutputDevice"), ["HDMI monitor"])
		self.assertEqual(self.press("nextOutputDevice"), ["Realtek speakers"])

	def test_previous_from_the_default_device_is_the_last_one(self):
		self.assertEqual(self.press("prevOutputDevice"), ["HDMI monitor"])

	def test_back_to_the_default_device(self):
		self.press("switchNvdaOutputToDevice2")
		self.assertEqual(self.press("switchNvdaOutputToDefault"), ["Default output device"])
		self.assertEqual(audio["outputDevice"], "default")

	def test_disconnected_device(self):
		self.windowsOutputs.remove(("{usb}", "USB headphones"))
		self.assertEqual(self.press("switchNvdaOutputToDevice2"), ["USB headphones is not available"])
		self.assertEqual(audio["outputDevice"], "default")


class TestWindowsDefaults(SwitchingTestCase):
	def test_default_output_device(self):
		self.assertEqual(self.press("setDefaultOutputDevice3"), ["HDMI monitor"])
		self.assertEqual(self.windows["set"], [("{hdmi}", ["eConsole", "eMultimedia"])])
		self.assertEqual(self.windows["communication"], "{realtek}")
		self.assertEqual(audio["outputDevice"], "default")

	def test_default_output_next_and_previous(self):
		self.assertEqual(self.press("nextDefaultOutputDevice"), ["HDMI monitor"])
		self.assertEqual(self.press("prevDefaultOutputDevice"), ["USB headphones"])

	def test_communication_device(self):
		self.assertEqual(self.press("setCommunicationDevice2"), ["USB headphones"])
		self.assertEqual(self.windows["set"], [("{usb}", ["eCommunications"])])
		self.assertEqual(self.press("nextCommunicationDevice"), ["HDMI monitor"])
		self.assertEqual(self.press("prevCommunicationDevice"), ["USB headphones"])

	def test_windows_refuses(self):
		self.windows["fail"] = True
		self.assertEqual(self.press("setDefaultOutputDevice1"), ["Unable to set the default device"])

	def test_no_default_device(self):
		self.windows["default"] = ""
		self.assertEqual(self.press("nextDefaultOutputDevice"), ["Realtek speakers"])

	def test_device_connected_later_is_reachable_with_next(self):
		self.windowsOutputs.append(("{bt}", "Bluetooth headset"))
		self.windows["default"] = "{hdmi}"
		self.assertEqual(self.press("nextDefaultOutputDevice"), ["Bluetooth headset"])

	def test_device_details_after_the_name(self):
		options["deviceDetails"] = True
		self.outputs[:] = [makeDevice("output", "{usb}", "USB headphones", isDefaultCommunicationDevice=True)]
		self.assertEqual(self.press("setCommunicationDevice2"), ["USB headphones, communication"])

	def test_no_output_devices(self):
		self.windowsOutputs.clear()
		self.assertEqual(self.press("nextOutputDevice"), [])


class TestInputDevices(SwitchingTestCase):
	def test_commands_for_the_input_devices_found_when_nvda_starts(self):
		for prefix in INPUT_PREFIXES:
			self.assertTrue(all(hasattr(self.plugin, f"script_{prefix}{number}") for number in (1, 2)))
			self.assertFalse(hasattr(self.plugin, f"script_{prefix}3"))

	def test_descriptions_with_number_and_name(self):
		self.assertEqual(
			self.plugin.script_setDefaultInputDevice1.__doc__,
			"Set the input device 1 (Microphone array) as the default input device",
		)
		self.assertEqual(
			self.plugin.script_setCommunicationInputDevice2.__doc__,
			"Set the input device 2 (Headset microphone) as the default communication input device",
		)

	def test_gestures_only_with_the_option_and_up_to_0(self):
		self.assertNotIn("kb:NVDA+windows+shift+1", self.plugin.boundGestures)
		options["gestures"] = True
		self.windowsInputs[:] = [(f"{{0.0.1.00000000}}.{{m{n}}}", f"Microphone {n}") for n in range(1, 12)]
		self.plugin.bindSwitchingMethods()
		self.assertEqual(self.plugin.boundGestures["kb:NVDA+windows+shift+1"], "setDefaultInputDevice1")
		self.assertEqual(self.plugin.boundGestures["kb:NVDA+windows+control+9"], "setCommunicationInputDevice9")
		self.assertEqual(self.plugin.boundGestures["kb:NVDA+windows+shift+0"], "setDefaultInputDevice10")
		self.assertNotIn("setDefaultInputDevice11", self.plugin.boundGestures.values())
		self.assertTrue(hasattr(self.plugin, "script_setDefaultInputDevice11"))
		self.assertNotIn("kb:NVDA+windows+1", self.plugin.boundGestures)

	def test_default_input_device(self):
		self.assertEqual(self.press("setDefaultInputDevice2"), ["Headset microphone"])
		self.assertEqual(self.windows["set"], [("{0.0.1.00000000}.{headset}", ["eConsole", "eMultimedia"])])

	def test_communication_input_device(self):
		self.assertEqual(self.press("setCommunicationInputDevice1"), ["Microphone array"])
		self.assertEqual(self.windows["set"], [("{0.0.1.00000000}.{array}", ["eCommunications"])])

	def test_disconnected_input_device(self):
		self.windowsInputs.pop()
		self.assertEqual(self.press("setDefaultInputDevice2"), ["Headset microphone is not available"])
		self.assertEqual(self.windows["set"], [])

	def test_commands_of_removed_input_devices_are_deleted_when_recreated(self):
		self.windowsInputs.pop()
		self.plugin.bindSwitchingMethods()
		self.assertFalse(any(hasattr(self.plugin, f"script_{prefix}2") for prefix in INPUT_PREFIXES))
		self.assertTrue(hasattr(self.plugin, "script_setDefaultOutputDevice3"))
