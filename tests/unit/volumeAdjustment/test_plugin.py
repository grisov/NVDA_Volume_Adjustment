# A part of the NVDA Volume Adjustment add-on
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.
# Copyright (C) 2020-2026 Oleksandr Gryshchenko <grisov.nvaccess@mailgw.com>

"""The global plugin: default gestures, descriptions of the commands, the Sound dialog and the secure mode."""

import inspect
import re
import sys

from volumeAdjustmentSupport import addon, log, module, options
from volumeAdjustmentSupport.case import AddonTestCase
from volumeAdjustmentSupport.fakes import makeDevice

GESTURES = addon.GlobalPlugin._GlobalPlugin__defaultGestures
# The default gestures of version 1.5.0, which users may rely on
VERSION_1_5_0 = {
	"kb:NVDA+windows+upArrow": "volumeUp",
	"kb:NVDA+windows+downArrow": "volumeDown",
	"kb:NVDA+windows+home": "volumeMax",
	"kb:NVDA+windows+end": "volumeMin",
	"kb:NVDA+windows+escape": "mute",
	"kb:NVDA+windows+rightArrow": "next",
	"kb:NVDA+windows+leftArrow": "prev",
	"kb:NVDA+windows+pageUp": "nextOutputDevice",
	"kb:NVDA+windows+pageDown": "prevOutputDevice",
	"kb:NVDA+shift+windows+rightArrow": "nextChannel",
	"kb:NVDA+shift+windows+leftArrow": "prevChannel",
	"kb:NVDA+shift+windows+upArrow": "channelVolumeUp",
	"kb:NVDA+shift+windows+downArrow": "channelVolumeDown",
	"kb:NVDA+shift+windows+home": "channelVolumeMax",
	"kb:NVDA+shift+windows+end": "channelVolumeMin",
	"kb:NVDA+shift+windows+escape": "channelVolumeAverage",
}


def normalized(gesture):
	"""Like inputCore.normalizeGestureIdentifier: NVDA does not depend on the order or case of the modifiers."""
	device, keys = gesture.split(":", 1)
	return device, frozenset(key.lower() for key in keys.split("+"))


class TestGestures(AddonTestCase):
	def test_gestures_of_version_1_5_0_are_kept(self):
		current = {normalized(gesture): script for gesture, script in GESTURES.items()}
		for gesture, script in VERSION_1_5_0.items():
			self.assertEqual(current.get(normalized(gesture)), script, gesture)

	def test_every_gesture_starts_with_nvda_windows(self):
		self.assertTrue(all(gesture.startswith("kb:NVDA+windows+") for gesture in GESTURES))

	def test_no_gesture_is_bound_twice(self):
		self.assertEqual(len({normalized(gesture) for gesture in GESTURES}), len(GESTURES))
		self.assertEqual(len(set(GESTURES.values())), len(GESTURES))

	def test_every_gesture_has_its_script(self):
		for script in GESTURES.values():
			self.assertTrue(hasattr(self.plugin, f"script_{script}"), script)

	def test_every_script_has_a_description(self):
		for name in dir(addon.GlobalPlugin):
			if name.startswith("script_"):
				description = getattr(addon.GlobalPlugin, name).__doc__ or ""
				# A description given to @script replaces the docstring, which documents the parameters
				self.assertTrue(description and ":param" not in description, name)

	def test_scripts_do_not_depend_on_the_gesture(self):
		for name in dir(addon.GlobalPlugin):
			if name.startswith("script_") and not re.search(r"\d$", name):
				source = inspect.getsource(getattr(addon.GlobalPlugin, name))
				self.assertNotRegex(source, r"\bgesture\.", name)

	def test_no_default_gestures_after_installation(self):
		self.assertEqual(self.plugin.boundGestures, {})

	def test_default_gestures_with_the_option(self):
		options["gestures"] = True
		self.windowsOutputs[:] = [("{a}", "Speakers"), ("{b}", "Headphones")]
		plugin = addon.GlobalPlugin()
		try:
			for gesture, script in GESTURES.items():
				self.assertEqual(plugin.boundGestures[gesture], script)
			self.assertEqual(plugin.boundGestures["kb:NVDA+windows+control+f2"], "setCommunicationDevice2")
			self.assertNotIn("kb:NVDA+windows+f3", plugin.boundGestures)
		finally:
			plugin.terminate()


class TestLifetime(AddonTestCase):
	def test_settings_panel_is_registered_and_removed(self):
		categories = sys.modules["gui.settingsDialogs"].NVDASettingsDialog.categoryClasses
		self.assertIn(module("settings").VASettingsPanel, categories)
		self.plugin.terminate()
		self.assertNotIn(module("settings").VASettingsPanel, categories)
		self.plugin = addon.GlobalPlugin()

	def test_muted_sources_are_unmuted_on_exit(self):
		device = makeDevice("output", "{a}", "Speakers", level=0.52)
		self.outputs[:] = [device]
		self.refresh()
		device.mute()
		self.plugin.terminate()
		self.assertAlmostEqual(device.volume.level, 0.52)
		self.plugin = addon.GlobalPlugin()

	def test_secure_mode_replaces_the_plugin(self):
		appArgs = sys.modules["globalVars"].appArgs
		self.patch(appArgs, "secure", True)
		replaced = addon.disableInSecureMode(addon.GlobalPlugin)
		self.assertIs(replaced, sys.modules["globalPluginHandler"].GlobalPlugin)


class TestSoundDialog(AddonTestCase):
	def setUp(self):
		super().setUp()
		self.devices = module("devices")
		self.started = []
		self.opened = []
		self.patch(self.devices.subprocess, "Popen", lambda args, **kwargs: self.started.append(args))
		self.patch(self.devices.os, "startfile", self.opened.append)

	def test_classic_sound_dialog(self):
		self.patch(self.devices.os.path, "isfile", lambda path: True)
		self.press("openSoundDialog")
		self.assertEqual(self.started[0][1], "mmsys.cpl")
		self.assertTrue(self.started[0][0].lower().endswith("control.exe"))
		self.assertEqual(self.opened, [])

	def test_settings_page_when_the_dialog_is_missing(self):
		self.patch(self.devices.os.path, "isfile", lambda path: False)
		self.press("openSoundDialog")
		self.assertEqual(self.started, [])
		self.assertEqual(self.opened, ["ms-settings:sound"])

	def test_settings_page_when_the_dialog_fails(self):
		def fail(args, **kwargs):
			raise OSError("not found")

		self.patch(self.devices.os.path, "isfile", lambda path: True)
		self.patch(self.devices.subprocess, "Popen", fail)
		self.press("openSoundDialog")
		self.assertEqual(self.opened, ["ms-settings:sound"])
		self.assertEqual(log.errors, ["Unable to open the Sound dialog of Windows"])
