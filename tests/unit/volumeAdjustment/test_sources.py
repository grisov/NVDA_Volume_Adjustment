# A part of the NVDA Volume Adjustment add-on
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.
# Copyright (C) 2020-2026 Oleksandr Gryshchenko <grisov.nvaccess@mailgw.com>

"""Audio sources: volume steps with exact levels, muting and unmuting, channels, groups of sessions."""

from volumeAdjustmentSupport import module, options
from volumeAdjustmentSupport.case import AddonTestCase
from volumeAdjustmentSupport.fakes import FakeSession, makeDevice

sources = module("sources")


class TestVolumeSteps(AddonTestCase):
	def test_every_step_changes_the_announced_level_once(self):
		app = sources.PlaybackAppSource("player.exe", [FakeSession(1, "player.exe", level=0.25)])
		levels = [round(app.volumeUp() * 100) for _ in range(10)]
		self.assertEqual(levels, list(range(26, 36)))
		levels = [round(app.volumeDown() * 100) for _ in range(10)]
		self.assertEqual(levels, list(range(34, 24, -1)))

	def test_step_option(self):
		options["step"] = 5
		device = makeDevice("output", "{a}", "Speakers", level=0.5)
		self.assertEqual(device.volumeUp(), 0.55)

	def test_maximum_and_minimum(self):
		device = makeDevice("output", "{a}", "Speakers", level=0.5)
		self.assertEqual(device.volumeMax(), 1.0)
		self.assertEqual(device.volumeMin(), 0.0)


class TestMuting(AddonTestCase):
	def test_volume_down_mode_restores_the_exact_level(self):
		session = FakeSession(1, "player.exe", level=0.5)
		app = sources.PlaybackAppSource("player.exe", [session])
		app.mute()
		self.assertAlmostEqual(session.SimpleAudioVolume.level, 0.125, places=5)
		self.assertTrue(app.isMuted)
		app.unmute()
		self.assertAlmostEqual(session.SimpleAudioVolume.level, 0.5, places=6)
		self.assertFalse(app.isMuted)
		self.assertEqual(self.cfg.muted, [])

	def test_complete_mute(self):
		options["muteCompletely"] = True
		device = makeDevice("output", "{a}", "Speakers", level=0.4)
		device.mute()
		self.assertEqual(device.volume.mute, 1)
		self.assertEqual(device.volume.level, device.volume.level)
		device.unmute()
		self.assertEqual(device.volume.mute, 0)

	def test_muted_by_an_old_version_without_the_exact_level(self):
		session = FakeSession(1, "player.exe", level=0.1)
		app = sources.PlaybackAppSource("player.exe", [session])
		self.cfg.addMuted("player.exe")
		app.unmute()
		self.assertAlmostEqual(session.SimpleAudioVolume.level, 0.4, places=5)

	def test_volume_down_while_silent_does_not_unmute(self):
		session = FakeSession(1, "player.exe", level=0.0)
		app = sources.PlaybackAppSource("player.exe", [session])
		self.cfg.addMuted("player.exe", 0.3)
		self.assertEqual(app.volumeDown(), 0.0)
		self.assertEqual(self.cfg.muted, ["player.exe"])

	def test_volume_up_unmutes_first(self):
		session = FakeSession(1, "player.exe", level=0.5)
		app = sources.PlaybackAppSource("player.exe", [session])
		app.mute()
		self.assertAlmostEqual(app.volumeUp(), 0.51)
		self.assertEqual(self.cfg.muted, [])

	def test_recording_application_is_muted_under_its_own_key(self):
		recording = sources.RecordingAppSource("Zoom.exe", [FakeSession(7, "Zoom.exe", level=0.8)])
		playing = sources.PlaybackAppSource("Zoom.exe", [FakeSession(7, "Zoom.exe", level=0.8)])
		recording.mute()
		self.assertEqual(self.cfg.muted, ["recording:Zoom.exe"])
		self.assertFalse(playing.isMuted)


class TestApplications(AddonTestCase):
	def test_all_sessions_of_an_application_are_adjusted_together(self):
		first, second = FakeSession(31, "firefox.exe", 0.5), FakeSession(32, "firefox.exe", 0.5)
		app = sources.PlaybackAppSource("firefox.exe", [first, second])
		app.volumeDown()
		self.assertAlmostEqual(first.SimpleAudioVolume.level, 0.49)
		self.assertAlmostEqual(second.SimpleAudioVolume.level, 0.49)
		self.assertEqual(app.processIds, [31, 32])

	def test_expired_session(self):
		session = FakeSession(1, "player.exe")
		app = sources.PlaybackAppSource("player.exe", [session])
		self.assertFalse(app.isExpired)
		session.State = 2
		self.assertTrue(app.isExpired)

	def test_channels_of_all_sessions(self):
		stereo, mono = FakeSession(1, "player.exe"), FakeSession(2, "player.exe", channels=1)
		app = sources.PlaybackAppSource("player.exe", [stereo, mono])
		self.assertEqual(app.channelCount, 2)
		app.setChannelVolumeLevel(0.3, 1)
		self.assertAlmostEqual(stereo.channels.levels[1], 0.3)
		self.assertEqual(mono.channels.levels, [1.0])
		app.setChannelVolumeLevel(0.6, 0)
		self.assertAlmostEqual(mono.channels.levels[0], 0.6)

	def test_channel_steps_and_average(self):
		session = FakeSession(1, "player.exe")
		app = sources.PlaybackAppSource("player.exe", [session])
		self.assertAlmostEqual(app.channelVolumeDown(0), 0.99)
		self.assertEqual(app.channelVolumeMin(1), 0.0)
		self.assertAlmostEqual(app.channelVolumeAverage(), 0.495, places=5)
		self.assertEqual(app.channelVolumeMax(0), 1.0)

	def test_selected_channel_wraps_around(self):
		app = sources.PlaybackAppSource("player.exe", [FakeSession(1, "player.exe")])
		app.channel += 1
		self.assertEqual(app.channel, 1)
		app.channel += 1
		self.assertEqual(app.channel, 0)


class TestDevices(AddonTestCase):
	def test_level_channels_and_decibels(self):
		device = makeDevice("output", "{a}", "Speakers", level=0.5)
		self.assertEqual(device.volumeLevel, 0.5)
		self.assertEqual(device.channelCount, 2)
		self.assertEqual(device.getVolumeDecibels(), -20.0)
		device.setChannelVolumeLevel(0.25, 0)
		self.assertEqual(device.getChannelVolumeLevel(0), 0.25)
		self.assertEqual(device.getVolumeDecibels(0), -30.0)

	def test_disconnected_device_gives_default_values(self):
		device = makeDevice("output", "{a}", "Speakers")
		device.volume.broken = True
		self.assertEqual(device.volumeLevel, -1.0)
		self.assertEqual(device.channelCount, 0)
		self.assertEqual(device.getChannelVolumeLevel(0), -1.0)
		self.assertIsNone(device.getVolumeDecibels())
		device.volumeLevel = 0.3
		self.assertEqual(device.channelVolumeUp(0), -1.0)

	def test_device_without_volume_interface(self):
		device = sources.InputDeviceSource(id="{m}", name="Microphone", volume=None)
		self.assertEqual(device.volumeLevel, -1.0)
		self.assertEqual(device.channelCount, 0)
		self.assertFalse(device.isMuted)

	def test_call_volume(self):
		self.assertEqual(sources.callVolume(None, lambda volume: 1, 0), 0)
		self.assertEqual(sources.callVolume(object(), lambda volume: 1, 0), 1)


class TestCategoriesOptions(AddonTestCase):
	def test_visible_categories(self):
		kind = sources.SourceKind
		options["categories"] = "PR"
		self.assertEqual(sources.getVisibleCategories(), [kind.PLAYBACK_APP, kind.RECORDING_APP])
		sources.setVisibleCategories([kind.RECORDING_APP, kind.OUTPUT_DEVICE])
		self.assertEqual(options["categories"], "OR")

	def test_source_keys(self):
		device = makeDevice("input", "{m}", "Microphone")
		self.assertEqual(sources.getSourceKey(device), (sources.SourceKind.INPUT_DEVICE, "{m}"))
