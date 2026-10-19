# A part of the NVDA Volume Adjustment add-on
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.
# Copyright (C) 2020-2026 Oleksandr Gryshchenko <grisov.nvaccess@mailgw.com>

"""The warning before the volume or a channel of NVDA itself is lowered or muted, and the channel commands."""

import os

from volumeAdjustmentSupport import audio, brailled, dialog, options
from volumeAdjustmentSupport.case import AddonTestCase
from volumeAdjustmentSupport.fakes import FakeSession, makeDevice


class ProtectionTestCase(AddonTestCase):
	def setUp(self):
		super().setUp()
		self.nvda = FakeSession(os.getpid(), "nvda.exe", level=0.5)
		self.player = FakeSession(61, "player.exe", level=0.5)
		self.playing[:] = [self.nvda, self.player]
		self.focusOn("nvda", os.getpid())
		self.press("volumeUp")


class TestNvdaVolume(ProtectionTestCase):
	def test_cancel_keeps_the_volume(self):
		dialog["result"] = 0
		self.assertEqual(self.press("volumeDown"), [])
		self.assertEqual(dialog["shown"], 1)
		self.assertAlmostEqual(self.nvda.SimpleAudioVolume.level, 0.51)

	def test_ok_lowers_the_volume(self):
		self.assertEqual(self.press("volumeDown"), ["Volume 50%"])
		self.assertEqual(dialog["shown"], 1)

	def test_mute_and_minimum_are_warned_too(self):
		dialog["result"] = 0
		self.press("mute")
		self.press("volumeMin")
		self.assertEqual(dialog["shown"], 2)
		self.assertEqual(self.cfg.muted, [])

	def test_raising_and_unmuting_are_not_warned(self):
		self.press("volumeUp")
		self.press("volumeMax")
		self.assertEqual(dialog["shown"], 0)

	def test_do_not_show_again(self):
		dialog["dontShow"] = True
		self.press("volumeDown")
		self.assertFalse(options["warnNvdaVolume"])
		self.press("volumeDown")
		self.assertEqual(dialog["shown"], 1)

	def test_warning_disabled_in_the_settings(self):
		options["warnNvdaVolume"] = False
		self.press("volumeDown")
		self.assertEqual(dialog["shown"], 0)

	def test_other_applications_are_not_warned(self):
		self.focusOn("player", 61)
		self.press("volumeDown")
		self.assertEqual(dialog["shown"], 0)


class TestNvdaChannels(ProtectionTestCase):
	def test_lowering_a_channel_is_warned(self):
		dialog["result"] = 0
		self.press("channelVolumeDown")
		self.press("channelVolumeMin")
		self.assertEqual(dialog["shown"], 2)
		self.assertEqual(self.nvda.channels.levels, [1.0, 1.0])

	def test_average_of_different_channels_is_warned(self):
		self.nvda.channels.levels = [1.0, 0.5]
		dialog["result"] = 0
		self.press("channelVolumeAverage")
		self.assertEqual(dialog["shown"], 1)

	def test_average_of_equal_channels_is_not_warned(self):
		self.nvda.channels.levels = [0.7, 0.7]
		self.assertEqual(self.press("channelVolumeAverage"), ["Volume 70%"])
		self.assertEqual(dialog["shown"], 0)

	def test_raising_a_channel_is_not_warned(self):
		self.press("channelVolumeUp")
		self.press("channelVolumeMax")
		self.assertEqual(dialog["shown"], 0)


class TestChannels(AddonTestCase):
	def setUp(self):
		super().setUp()
		self.player = FakeSession(61, "player.exe", level=0.5)
		self.playing[:] = [self.player]
		self.focusOn("player", 61)
		self.press("volumeUp")

	def test_channels_of_an_application(self):
		self.assertEqual(self.press("nextChannel"), ["Channel 2, Volume 100%"])
		self.assertEqual(brailled[-1], "Channel 2: 100%")
		self.assertEqual(self.press("channelVolumeDown"), ["Volume 99%"])
		self.assertAlmostEqual(self.player.channels.levels[1], 0.99)
		self.assertEqual(self.player.channels.levels[0], 1.0)

	def test_sound_split_uses_the_channels_of_applications(self):
		for state in (1, 2, 7):
			audio["soundSplitState"] = state
			self.assertEqual(self.press("channelVolumeDown"), ["Channels are used by NVDA sound split"])
		self.assertEqual(self.player.channels.levels, [1.0, 1.0])

	def test_application_without_channels(self):
		self.playing[:] = [FakeSession(64, "nochannels.exe", channels=0)]
		self.focusOn("nochannels", 64)
		self.assertEqual(self.press("nextChannel")[-1], "Not supported")

	def test_sound_split_does_not_block_devices(self):
		audio["soundSplitState"] = 2
		options["focus"] = False
		self.outputs[:] = [makeDevice("output", "{a}", "Speakers", level=0.5)]
		self.refresh()
		self.plugin.event_gainFocus(None, lambda: None)
		self.assertEqual(self.press("channelVolumeUp"), ["Volume 51%"])
