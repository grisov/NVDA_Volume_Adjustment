# A part of the NVDA Volume Adjustment add-on
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.
# Copyright (C) 2020-2026 Oleksandr Gryshchenko <grisov.nvaccess@mailgw.com>

"""Switching between audio sources and categories, the application in focus and the volume commands."""

import os

from volumeAdjustmentSupport import module, options
from volumeAdjustmentSupport.case import AddonTestCase
from volumeAdjustmentSupport.fakes import FakeSession, makeDevice

kind = module("model").SourceKind


class NavigationTestCase(AddonTestCase):
	"""Two output devices, a microphone, three playing and two recording programs."""

	def setUp(self):
		super().setUp()
		self.speakers = makeDevice("output", "{out1}", "Speakers", level=0.5, default=True)
		self.headphones = makeDevice("output", "{out2}", "USB headphones", level=0.3)
		self.microphone = makeDevice("input", "{0.0.1.00000000}.{in1}", "Microphone", level=0.7)
		self.outputs[:] = [self.speakers, self.headphones]
		self.inputs[:] = [self.microphone]
		self.nvda = FakeSession(os.getpid(), "nvda.exe")
		self.firefox = FakeSession(2, "firefox.exe", level=0.5)
		self.zoom = FakeSession(7, "Zoom.exe", level=0.5)
		self.zoomRecording = FakeSession(7, "Zoom.exe", level=0.8)
		self.obs = FakeSession(9, "obs64.exe", level=0.6)
		self.playing[:] = [self.nvda, self.firefox, self.zoom]
		self.recording[:] = [self.zoomRecording, self.obs]
		self.refresh()

	def keys(self):
		return [f"{source.kind.value}:{source.id}" for source in self.navigator.getAllSources()]


class TestSourceList(NavigationTestCase):
	def test_order_of_the_categories(self):
		self.assertEqual(
			self.keys(),
			[
				"O:{out1}",
				"O:{out2}",
				"I:{0.0.1.00000000}.{in1}",
				"P:nvda.exe",
				"P:firefox.exe",
				"P:Zoom.exe",
				"R:Zoom.exe",
				"R:obs64.exe",
			],
		)

	def test_hidden_categories_and_processes(self):
		options["categories"] = "PR"
		self.cfg.processes = ["Zoom.exe"]
		self.assertEqual(self.keys(), ["P:nvda.exe", "P:firefox.exe", "R:obs64.exe"])


class TestArrows(NavigationTestCase):
	def setUp(self):
		super().setUp()
		options["focus"] = False
		options["status"] = False

	def test_next_goes_through_all_categories_and_wraps(self):
		titles = [self.press("next")[0] for _ in range(8)]
		self.assertEqual(
			titles,
			[
				"USB headphones",
				"Microphone",
				"nvda",
				"firefox",
				"Zoom",
				"Zoom",
				"obs64",
				"Default audio device: Speakers",
			],
		)

	def test_previous_from_the_first_source_is_the_last_one(self):
		self.assertEqual(self.press("prev"), ["obs64"])

	def test_status_after_the_name(self):
		options["status"] = True
		self.assertEqual(self.press("next"), ["USB headphones", "Volume 30%"])

	def test_category_name_at_its_boundary(self):
		options["announceCategories"] = True
		heard = [self.press("next")[0] for _ in range(4)]
		self.assertEqual(heard, ["USB headphones", "Input devices, Microphone", "Playback apps, nvda", "firefox"])

	def test_device_details_after_the_level(self):
		options["status"] = True
		options["deviceDetails"] = True
		self.headphones.connection = module("model").Connection.USB
		self.assertEqual(self.press("next"), ["USB headphones", "Volume 30%, USB"])

	def test_selected_source_is_adjusted(self):
		self.press("next")
		self.assertEqual(self.press("volumeUp"), ["Volume 31%"])
		self.assertAlmostEqual(self.headphones.volume.level, 0.31)


class TestCategoryJumps(NavigationTestCase):
	def setUp(self):
		super().setUp()
		options["focus"] = False
		options["status"] = False

	def test_next_and_previous_category(self):
		self.assertEqual(self.press("nextCategory"), ["Input devices, Microphone"])
		self.assertEqual(self.press("nextCategory"), ["Playback apps, nvda"])
		self.assertEqual(self.press("prevCategory"), ["Input devices, Microphone"])

	def test_empty_and_hidden_categories_are_skipped(self):
		self.inputs.clear()
		self.refresh()
		self.assertEqual(self.press("nextCategory"), ["Playback apps, nvda"])
		options["categories"] = "OR"
		self.assertEqual(self.press("nextCategory"), ["Recording apps, Zoom"])


class TestFocus(NavigationTestCase):
	def test_application_in_focus_is_adjusted_with_its_title_once(self):
		self.focusOn("firefox", 2)
		self.assertEqual(self.press("volumeDown"), ["firefox", "Volume 49%"])
		self.assertEqual(self.press("volumeDown"), ["Volume 48%"])

	def test_application_in_focus_without_sound(self):
		self.focusOn("notepad", 42)
		self.assertEqual(self.press("volumeUp"), ["notepad is not playing any sound."])
		self.assertEqual(self.nvda.SimpleAudioVolume.level, 1.0)

	def test_arrows_start_from_the_application_in_focus(self):
		options["status"] = False
		self.focusOn("firefox", 2)
		self.assertEqual(self.press("next"), ["Zoom"])
		self.focusOn("firefox", 2)
		self.assertEqual(self.press("prev"), ["nvda"])

	def test_arrows_from_an_application_without_sound(self):
		options["status"] = False
		self.focusOn("notepad", 42)
		self.assertEqual(self.press("next"), ["nvda"])
		self.focusOn("notepad", 42)
		self.assertEqual(self.press("prev"), ["obs64"])

	def test_new_session_of_the_application_is_used(self):
		self.focusOn("firefox", 2)
		self.press("volumeDown")
		restarted = FakeSession(22, "firefox.exe", level=0.5)
		self.firefox.State = 2
		self.playing[:] = [self.nvda, restarted]
		self.press("volumeDown")
		self.assertAlmostEqual(restarted.SimpleAudioVolume.level, 0.49)

	def test_focus_change_drops_the_selection(self):
		options["status"] = False
		self.press("next")
		self.focusOn("Zoom", 7)
		self.assertEqual(self.press("volumeUp"), ["Zoom", "Volume 51%"])


class TestSelection(NavigationTestCase):
	def setUp(self):
		super().setUp()
		options["focus"] = False

	def test_without_focus_tracking_the_first_source_is_adjusted(self):
		self.assertEqual(self.press("volumeUp"), ["Volume 51%"])
		self.assertAlmostEqual(self.speakers.volume.level, 0.51)

	def test_removed_device_falls_back_to_the_default_output(self):
		self.navigator._selected = (kind.INPUT_DEVICE, self.microphone.id)
		self.inputs.clear()
		self.refresh()
		self.assertEqual(self.press("volumeUp"), ["Default audio device: Speakers", "Volume 51%"])

	def test_application_that_stopped_playing(self):
		self.navigator._selected = (kind.PLAYBACK_APP, "ghost.exe")
		self.assertEqual(self.press("volumeUp"), ["ghost is not playing any sound."])

	def test_recording_application_that_stopped_recording(self):
		self.navigator._selected = (kind.RECORDING_APP, "Zoom.exe")
		self.recording.remove(self.zoomRecording)
		self.registry.markAppsChanged()
		self.assertEqual(self.press("volumeUp"), ["Zoom is not recording any sound."])

	def test_selection_of_a_hidden_category_is_dropped(self):
		self.navigator._selected = (kind.RECORDING_APP, "obs64.exe")
		options["categories"] = "OIP"
		self.press("volumeUp")
		self.assertEqual(self.navigator._selected, (kind.OUTPUT_DEVICE, "{out1}"))

	def test_mute_and_unmute_the_selected_source(self):
		self.speakers.volume.level = 0.52
		self.assertEqual(self.press("mute"), ["The sound is muted, Volume 13%"])
		self.assertEqual(self.press("mute"), ["Volume 52%"])

	def test_volume_down_to_zero_mutes(self):
		self.speakers.volume.level = 0.01
		self.assertEqual(self.press("volumeDown"), ["The sound is muted, Volume 0%"])

	def test_unmute_all_on_exit(self):
		self.press("mute")
		self.navigator._selected = (kind.PLAYBACK_APP, "firefox.exe")
		self.press("mute")
		self.navigator.unmuteAllAudioSources()
		self.assertEqual(self.cfg.muted, [])
		self.assertAlmostEqual(self.firefox.SimpleAudioVolume.level, 0.5)


class TestCategoryVisibility(NavigationTestCase):
	def test_hide_and_show(self):
		self.assertEqual(self.press("toggleRecordingApps"), ["Recording apps hidden"])
		self.assertEqual(options["categories"], "OIP")
		self.assertEqual(self.press("toggleRecordingApps"), ["Recording apps shown, 2 sources"])
		self.assertEqual(self.press("toggleInputDevices"), ["Input devices hidden"])
		self.assertEqual(self.press("toggleInputDevices"), ["Input devices shown, 1 source"])

	def test_only_one_category(self):
		self.assertEqual(self.press("showOnlyPlaybackApps"), ["Playback apps only, 3 sources"])
		self.assertEqual(options["categories"], "P")
		self.assertEqual(self.press("showOnlyPlaybackApps"), ["Playback apps is already the only visible category"])

	def test_last_category_cannot_be_hidden(self):
		options["categories"] = "P"
		self.assertEqual(
			self.press("togglePlaybackApps"),
			["Category cannot be hidden. Playback apps is already the only visible category"],
		)
		self.assertEqual(options["categories"], "P")

	def test_every_category_has_its_commands(self):
		for name in ("OutputDevices", "InputDevices", "PlaybackApps", "RecordingApps"):
			self.assertTrue(hasattr(self.plugin, f"script_toggle{name}"))
			self.assertTrue(hasattr(self.plugin, f"script_showOnly{name}"))
