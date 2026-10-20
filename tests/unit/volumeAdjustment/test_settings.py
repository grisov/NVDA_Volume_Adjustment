# A part of the NVDA Volume Adjustment add-on
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.
# Copyright (C) 2020-2026 Oleksandr Gryshchenko <grisov.nvaccess@mailgw.com>

"""The settings panel of the add-on with the controls of wx replaced: shown values, lists and saving."""

import sys
import types
from unittest.mock import MagicMock

from volumeAdjustmentSupport import module, options, spoken
from volumeAdjustmentSupport.case import AddonTestCase
from volumeAdjustmentSupport.fakes import FakeSession, makeDevice

settings = module("settings")


class ListBox:
	"""Stands for nvdaControls.CustomCheckListBox: keeps the items with their data and the checked ones."""

	def __init__(self, choices=()):
		self.items = [(choice, None) for choice in choices]
		self.checked = []

	def Append(self, name, data=None):
		self.items.append((name, data))

	def Clear(self):
		self.items = []

	def SetItems(self, items):
		self.items = [(item, None) for item in items]

	def SetCheckedStrings(self, strings):
		self.checked = list(strings)

	def SetCheckedItems(self, indexes):
		self.checked = [self.items[index][0] for index in indexes]

	def Check(self, index, check=True):
		name = self.items[index][0]
		if check and name not in self.checked:
			self.checked.append(name)
		elif not check and name in self.checked:
			self.checked.remove(name)

	def GetCheckedItems(self):
		return [index for index, (name, _data) in enumerate(self.items) if name in self.checked]

	def GetCheckedStrings(self):
		return [name for name, _data in self.items if name in self.checked]

	def GetClientData(self, index):
		return self.items[index][1]

	def names(self):
		return [name for name, _data in self.items]

	def __getattr__(self, name):
		return MagicMock()


class SettingsTestCase(AddonTestCase):
	def setUp(self):
		super().setUp()
		self.outputs[:] = [makeDevice("output", "{out1}", "Speakers"), makeDevice("output", "{out2}", "Headphones")]
		self.inputs[:] = [makeDevice("input", "{0.0.1.00000000}.{in1}", "Microphone")]
		self.playing[:] = [FakeSession(1, "nvda.exe"), FakeSession(2, "firefox.exe"), FakeSession(3, "firefox.exe")]
		self.recording[:] = [FakeSession(9, "obs64.exe")]
		self.refresh()
		self.cfg.processes = ["hidden.exe"]
		self.cfg.devices = {"{gone}": "Old headset", "{0.0.1.00000000}.{gone}": "Old microphone"}
		self.labels = []
		helper = MagicMock()
		helper.addItem.side_effect = lambda *args, **kwargs: MagicMock()

		def addLabeledControl(*args, **kwargs):
			label = args[0] if args else kwargs.get("labelText")
			self.labels.append(label)
			if "choices" in kwargs and (args[1:2] or [kwargs.get("wxCtrlClass")])[0] is not sys.modules["wx"].Choice:
				return ListBox(kwargs["choices"])
			return MagicMock()

		helper.addLabeledControl.side_effect = addLabeledControl
		guiHelper = MagicMock()
		guiHelper.BoxSizerHelper.return_value = helper
		self.patch(settings, "guiHelper", guiHelper)
		self.panel = self.openPanel()

	def openPanel(self):
		panel = settings.VASettingsPanel(None)
		panel.makeSettings(MagicMock())
		return panel


class TestLists(SettingsTestCase):
	def test_processes_playing_and_recording_plus_hidden_ones(self):
		self.assertEqual(self.panel.hideProcesses.names(), ["nvda.exe", "firefox.exe", "obs64.exe", "hidden.exe"])

	def test_output_and_input_devices_with_hidden_ones(self):
		self.assertEqual(self.panel.hideOutputDevices.names(), ["Old headset", "Speakers", "Headphones"])
		self.assertEqual(self.panel.hideInputDevices.names(), ["Old microphone", "Microphone"])
		self.assertEqual(self.panel.hideOutputDevices.checked, ["Old headset"])

	def test_clear_and_refresh_a_device_list(self):
		self.panel.onClearDevicesButton(self.panel.hideOutputDevices, isInput=False)
		self.assertEqual(self.panel.hideOutputDevices.names(), ["Speakers", "Headphones"])
		self.assertEqual(self.panel.hideOutputDevices.GetCheckedItems(), [])
		self.assertEqual(self.panel.hideInputDevices.names(), ["Old microphone", "Microphone"])
		self.panel.onUpdateDevicesButton(self.panel.hideOutputDevices, isInput=False)
		self.assertEqual(self.panel.hideOutputDevices.checked, ["Old headset"])

	def test_clear_and_refresh_the_processes(self):
		self.panel.onClearProcessesButton(None)
		self.assertEqual(self.panel.hideProcesses.names(), ["nvda.exe", "firefox.exe", "obs64.exe"])
		self.panel.onUpdateProcessesButton(None)
		self.assertIn("hidden.exe", self.panel.hideProcesses.names())

	def test_quick_mute_microphones(self):
		self.cfg.quickMute = {"{0.0.1.00000000}.{old}": "Old mic"}
		panel = self.openPanel()
		self.assertEqual(panel.quickMuteDevices.names(), ["Old mic", "Microphone"])
		self.assertEqual(panel.quickMuteDevices.checked, ["Old mic"])


class TestSaving(SettingsTestCase):
	def test_hidden_devices_of_both_lists_and_processes(self):
		self.panel.hideOutputDevices.SetCheckedStrings(["Headphones"])
		self.panel.hideInputDevices.SetCheckedStrings(["Microphone"])
		self.panel.hideProcesses.SetCheckedStrings(["firefox.exe"])
		self.panel.units.GetClientData.return_value = "percent"
		self.panel.onSave()
		self.assertEqual(sorted(self.cfg.devices.values()), ["Headphones", "Microphone"])
		self.assertEqual(self.cfg.processes, ["firefox.exe"])
		self.assertNotIn("Headphones", [device.name for device in self.registry.devices])

	def test_quick_mute_does_not_change_the_hidden_devices(self):
		hidden = dict(self.cfg.devices)
		self.panel.quickMuteDevices.SetCheckedStrings(["Microphone"])
		self.panel.units.GetClientData.return_value = "percent"
		self.panel.onSave()
		self.assertEqual(list(self.cfg.quickMute.values()), ["Microphone"])
		self.assertEqual(self.cfg.devices, hidden)

	def test_options(self):
		self.panel.deviceDetailsChk.GetValue.return_value = True
		self.panel.defaultGesturesChk.GetValue.return_value = True
		self.panel.units.GetClientData.return_value = "decibels"
		self.panel.onSave()
		self.assertTrue(options["deviceDetails"])
		# Saved with the other options when the add-ons are reloaded later
		self.assertTrue(options["gestures"])
		self.assertEqual(options["units"], "decibels")


class TestControls(SettingsTestCase):
	def test_step_label_with_the_percent_sign(self):
		self.assertIn("Volume level change &step, %:", self.labels)

	def test_units_choice(self):
		added = [call.args for call in self.panel.units.Append.call_args_list]
		self.assertEqual(
			added,
			[("Percent", "percent"), ("Percent, number only", "number"), ("Decibels, if the source supports it", "decibels")],
		)
		options["units"] = "decibels"
		self.assertEqual(self.openPanel().units.Select.call_args.args, (2,))

	def test_visible_categories(self):
		categories = self.panel.visibleCategories
		self.assertEqual(categories.names(), ["Output devices", "Input devices", "Playback apps", "Recording apps"])
		options["categories"] = "IP"
		self.assertEqual(self.openPanel().visibleCategories.checked, ["Input devices", "Playback apps"])

	def test_last_category_cannot_be_unchecked(self):
		categories = self.panel.visibleCategories
		for index in (0, 1, 3):
			categories.Check(index, False)
		categories.Check(2, False)
		self.panel.onVisibleCategoriesCheck(types.SimpleNamespace(GetInt=lambda: 2))
		self.assertEqual(categories.checked, ["Playback apps"])
		self.assertEqual(spoken[-1], "Category cannot be hidden. Playback apps is already the only visible category")
		self.panel.units.GetClientData.return_value = "percent"
		self.panel.onSave()
		self.assertEqual(options["categories"], "P")

	def test_no_removed_options(self):
		self.assertFalse(hasattr(self.panel, "advancedChk"))
		self.assertFalse(hasattr(self.panel, "hideDuplicatesChk"))


class TestWarningDialog(AddonTestCase):
	def test_warning_about_the_volume_of_nvda(self):
		dialog = settings.NvdaVolumeWarningDialog(None)
		self.assertIn("audio session of NVDA itself", dialog.message)
		self.assertEqual((dialog.dialogType, dialog.buttons), ("WARNING", "OK_CANCEL"))
		self.assertEqual(dialog.title, "Volume Adjustment")
		self.assertTrue(hasattr(dialog, "dontShowAgainChk"))
