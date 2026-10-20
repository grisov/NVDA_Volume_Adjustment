# A part of the NVDA Volume Adjustment add-on
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.
# Copyright (C) 2020-2026 Oleksandr Gryshchenko <grisov.nvaccess@mailgw.com>

"""The quick mute of the microphones selected in the add-on settings."""

import os

from volumeAdjustmentSupport import events, log, module
from volumeAdjustmentSupport.case import AddonTestCase
from volumeAdjustmentSupport.fakes import makeDevice

microphones = module("microphones")


class TestQuickMute(AddonTestCase):
	def setUp(self):
		super().setUp()
		self.headset = makeDevice("input", "{0.0.1.00000000}.{a}", "Headset mic")
		self.webcam = makeDevice("input", "{0.0.1.00000000}.{b}", "Webcam mic")
		self.laptop = makeDevice("input", "{0.0.1.00000000}.{c}", "Laptop mic")
		self.outputs[:] = [makeDevice("output", "{out}", "Speakers")]
		self.inputs[:] = [self.headset, self.webcam, self.laptop]
		self.cfg.quickMute = {self.headset.id: "Headset mic", self.webcam.id: "Webcam mic", "{gone}": "Old mic"}

	def test_nothing_selected(self):
		self.cfg.quickMute = {}
		self.assertEqual(self.press("toggleQuickMute"), ["No microphones are selected for the quick mute"])

	def test_selected_microphones_not_connected(self):
		self.inputs[:] = [self.laptop]
		self.assertEqual(self.press("toggleQuickMute"), ["The microphones selected for the quick mute are not connected"])

	def test_mute_then_the_sound_without_messages(self):
		self.assertEqual(self.press("toggleQuickMute"), [])
		self.assertEqual(
			events,
			[("mute", "Headset mic", 1), ("mute", "Webcam mic", 1), ("sound", "micOff.wav")],
		)
		self.assertEqual(self.laptop.volume.mute, 0)

	def test_unmute_after_the_sound(self):
		self.headset.volume.mute = self.webcam.volume.mute = 1
		self.assertEqual(self.press("toggleQuickMute"), [])
		duration = microphones.getSoundDuration(microphones.MICROPHONES_ON_SOUND)
		self.assertEqual(
			events,
			[("sound", "micOn.wav"), ("later", duration + 20), ("mute", "Headset mic", 0), ("mute", "Webcam mic", 0)],
		)

	def test_any_microphone_on_mutes_all_of_them(self):
		self.webcam.volume.mute = 1
		self.press("toggleQuickMute")
		self.assertEqual((self.headset.volume.mute, self.webcam.volume.mute), (1, 1))

	def test_not_in_the_list_of_muted_sources(self):
		self.press("toggleQuickMute")
		self.assertEqual(self.cfg.muted, [])

	def test_failing_microphone(self):
		self.webcam.volume.broken = True
		self.press("toggleQuickMute")
		self.assertEqual(self.headset.volume.mute, 1)

	def test_sounds_of_the_add_on(self):
		for path in (microphones.MICROPHONES_ON_SOUND, microphones.MICROPHONES_OFF_SOUND):
			self.assertTrue(os.path.isfile(path))
			self.assertGreater(microphones.getSoundDuration(path), 100)

	def test_missing_sound(self):
		self.assertEqual(microphones.getSoundDuration(microphones.MICROPHONES_ON_SOUND + ".missing"), 0)
		self.patch(microphones, "MICROPHONES_ON_SOUND", microphones.MICROPHONES_ON_SOUND + ".missing")
		self.headset.volume.mute = self.webcam.volume.mute = 1
		self.press("toggleQuickMute")
		self.assertIn(("later", 20), events)
		self.assertEqual(self.headset.volume.mute, 0)
		self.assertEqual(log.errors, [])

	def test_microphones_stay_muted_when_nvda_exits(self):
		self.press("toggleQuickMute")
		self.plugin.navigator.unmuteAllAudioSources()
		self.assertEqual([self.headset.volume.GetMute(), self.webcam.volume.GetMute()], [1, 1])
