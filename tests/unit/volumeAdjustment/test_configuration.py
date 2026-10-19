# A part of the NVDA Volume Adjustment add-on
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.
# Copyright (C) 2020-2026 Oleksandr Gryshchenko <grisov.nvaccess@mailgw.com>

"""The data file of the add-on: muted audio sources with their levels, hidden devices and processes, quick mute."""

import json
import os
import tempfile
import unittest

from volumeAdjustmentSupport import module

configuration = module("configuration")


class TestConfiguration(unittest.TestCase):
	def setUp(self):
		self.folder = tempfile.TemporaryDirectory()
		self.config = configuration.Configuration()
		self.config._file = os.path.join(self.folder.name, "volumeAdjustment.json")
		self.config._data = {"version": 0}

	def tearDown(self):
		self.folder.cleanup()

	def test_first_muted_source_is_remembered_with_its_level(self):
		self.config.addMuted("firefox.exe", 0.5)
		self.assertEqual(self.config.muted, ["firefox.exe"])
		self.assertEqual(self.config.getMutedLevel("firefox.exe"), 0.5)

	def test_muted_without_level(self):
		self.config.addMuted("{device}")
		self.assertIsNone(self.config.getMutedLevel("{device}"))

	def test_muted_once(self):
		self.config.addMuted("a", 0.3).addMuted("a", 0.9)
		self.assertEqual(self.config.muted, ["a"])
		self.assertEqual(self.config.getMutedLevel("a"), 0.3)

	def test_unmuted_source_forgets_its_level(self):
		self.config.addMuted("a", 0.3).delMuted("a")
		self.assertEqual(self.config.muted, [])
		self.assertIsNone(self.config.getMutedLevel("a"))
		self.config.delMuted("not muted")

	def test_hidden_devices_and_processes(self):
		self.config.devices = {"{a}": "Speakers"}
		self.config.processes = ["hidden.exe"]
		self.assertFalse(self.config.isChangedDevices({"{a}": "Other name"}))
		self.assertTrue(self.config.isChangedDevices({"{b}": "Speakers"}))
		self.assertFalse(self.config.isChangedProcesses(["hidden.exe"]))
		self.assertTrue(self.config.isChangedProcesses([]))

	def test_quick_mute_microphones(self):
		self.assertEqual(self.config.quickMute, {})
		self.config.quickMute = {"{0.0.1.00000000}.{mic}": "Microphone"}
		self.assertEqual(self.config.quickMute, {"{0.0.1.00000000}.{mic}": "Microphone"})

	def test_saved_and_loaded_again(self):
		self.config.addMuted("zoom.exe", 0.25)
		self.config.quickMute = {"{mic}": "Microphone"}
		self.config.save()
		with open(self.config._file, encoding="utf-8") as file:
			self.assertEqual(json.load(file)["muted"], ["zoom.exe"])
		loaded = configuration.Configuration()
		loaded._file = self.config._file
		loaded.load()
		self.assertEqual(loaded.getMutedLevel("zoom.exe"), 0.25)
		self.assertEqual(loaded.quickMute, {"{mic}": "Microphone"})

	def test_missing_or_broken_file_gives_empty_data(self):
		self.config.load()
		self.assertEqual(self.config._data, {"version": 0})
		with open(self.config._file, "w", encoding="utf-8") as file:
			file.write("{broken")
		self.config.load()
		self.assertEqual(self.config._data, {"version": 0})

	def test_options_have_defaults(self):
		self.assertIn("default=false", configuration.confspec["gestures"])
		self.assertIn('default="OIPR"', configuration.confspec["categories"])
		self.assertIn('default="percent"', configuration.confspec["units"])
