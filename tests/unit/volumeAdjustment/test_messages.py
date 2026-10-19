# A part of the NVDA Volume Adjustment add-on
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.
# Copyright (C) 2020-2026 Oleksandr Gryshchenko <grisov.nvaccess@mailgw.com>

"""The messages announced to the user: volume levels in all units, muting, device details, categories."""

import types

from volumeAdjustmentSupport import brailled, module, options, spoken
from volumeAdjustmentSupport.case import AddonTestCase
from volumeAdjustmentSupport.fakes import FakeSession, makeDevice

messages = module("messages")
model = module("model")


class TestVolumeLevel(AddonTestCase):
	def test_percent_with_the_sign_by_default(self):
		self.assertEqual(messages.formatVolumeLevel(0.29), "Volume 29%")

	def test_float32_level_is_rounded(self):
		self.assertEqual(messages.formatVolumeLevel(0.28999999), "Volume 29%")

	def test_number_only(self):
		options["units"] = "number"
		self.assertEqual(messages.formatVolumeLevel(0.29), "Volume 29")

	def test_decibels_of_a_device(self):
		options["units"] = "decibels"
		device = makeDevice("output", "{a}", "Speakers", level=0.5)
		self.assertEqual(messages.formatVolumeLevel(0.5, device), "Volume -20.0 dB")

	def test_decibels_of_a_channel(self):
		options["units"] = "decibels"
		device = makeDevice("output", "{a}", "Speakers", level=0.5)
		device.volume.channels[1] = 0.75
		self.assertEqual(messages.formatVolumeLevel(0.75, device, 1), "Volume -10.0 dB")

	def test_decibels_unknown_for_applications_give_percent(self):
		options["units"] = "decibels"
		app = self.sources.PlaybackAppSource("player.exe", [FakeSession(1, "player.exe", level=0.4)])
		self.assertEqual(messages.formatVolumeLevel(0.4, app), "Volume 40%")

	def test_no_minus_sign_before_zero_decibels(self):
		options["units"] = "decibels"
		nearZero = types.SimpleNamespace(getVolumeDecibels=lambda channel=None: -0.04)
		self.assertEqual(messages.formatVolumeLevel(1.0, nearZero), "Volume 0.0 dB")

	def test_only_the_level_on_a_braille_display(self):
		device = makeDevice("output", "{a}", "Speakers", level=0.5)
		messages.announceVolumeLevel(0.29, device)
		options["units"] = "number"
		messages.announceVolumeLevel(0.29, device)
		options["units"] = "decibels"
		messages.announceVolumeLevel(0.5, device)
		self.assertEqual(spoken, ["Volume 29%", "Volume 29", "Volume -20.0 dB"])
		self.assertEqual(brailled, ["29%", "29", "-20.0 dB"])


class TestMuted(AddonTestCase):
	def setUp(self):
		super().setUp()
		self.device = makeDevice("output", "{a}", "Speakers", level=0.13)

	def test_complete_mute_without_level(self):
		options["muteCompletely"] = True
		self.cfg.addMuted("{a}")
		self.assertEqual(messages.formatMuted(self.device), ("The sound is muted", "muted"))

	def test_volume_down_mode_with_the_remaining_level(self):
		self.cfg.addMuted("{a}", 0.52)
		self.assertEqual(messages.formatMuted(self.device), ("The sound is muted, Volume 13%", "muted 13%"))

	def test_muted_by_windows_without_level(self):
		self.device.volume.mute = 1
		self.assertEqual(messages.formatMuted(self.device), ("The sound is muted", "muted"))


class TestDeviceDetails(AddonTestCase):
	def test_type_connection_and_roles(self):
		device = makeDevice(
			"output",
			"{h}",
			"Headset (USB)",
			formFactor=model.FormFactor.HEADSET,
			connection=model.Connection.USB,
			isDefaultDevice=True,
			isDefaultCommunicationDevice=True,
		)
		self.assertEqual(messages.getDeviceDetails(device), ["headset", "USB", "default", "communication"])

	def test_internal_connection_and_unknown_type_are_not_announced(self):
		device = makeDevice("output", "{s}", "Speakers", connection=model.Connection.INTERNAL)
		self.assertEqual(messages.getDeviceDetails(device), [])
		device.formFactor = model.FormFactor.SPEAKERS
		self.assertEqual(messages.getDeviceDetails(device), ["speakers"])

	def test_announced_details_follow_the_option(self):
		device = makeDevice("input", "{c}", "Cable", connection=model.Connection.VIRTUAL)
		self.assertEqual(messages.getAnnouncedDeviceDetails(device), [])
		options["deviceDetails"] = True
		self.assertEqual(messages.getAnnouncedDeviceDetails(device), ["virtual"])

	def test_applications_have_no_details(self):
		options["deviceDetails"] = True
		app = self.sources.PlaybackAppSource("player.exe", [FakeSession(1, "player.exe")])
		self.assertEqual(messages.getAnnouncedDeviceDetails(app), [])
		self.assertEqual(messages.getAnnouncedDeviceDetails(None), [])


class TestTitles(AddonTestCase):
	def test_default_output_device_has_a_prefix(self):
		device = makeDevice("output", "{a}", "Speakers")
		self.assertEqual(messages.getSourceTitle(device), "Speakers")
		device.default = True
		self.assertEqual(messages.getSourceTitle(device), "Default audio device: Speakers")

	def test_application_title(self):
		app = self.sources.PlaybackAppSource("firefox.exe", [FakeSession(1, "firefox.exe")])
		self.assertEqual(messages.getSourceTitle(app), "firefox")
		named = self.sources.PlaybackAppSource("app.exe", [FakeSession(1, "app.exe", displayName="My player")])
		self.assertEqual(messages.getSourceTitle(named), "My player")

	def test_system_sounds(self):
		session = FakeSession(0, "", displayName=r"@%SystemRoot%\System32\AudioSrv.Dll,-202")
		self.assertEqual(messages.getSourceTitle(self.sources.PlaybackAppSource("x", [session])), "System Sound")


class TestCategories(AddonTestCase):
	def test_category_names(self):
		kind = model.SourceKind
		names = [messages.getCategoryName(k) for k in kind]
		self.assertEqual(names, ["Output devices", "Input devices", "Playback apps", "Recording apps"])

	def test_only_visible_category(self):
		self.assertEqual(
			messages.getOnlyVisibleCategoryMessage("Playback apps"),
			"Playback apps is already the only visible category",
		)
		self.assertEqual(
			messages.getOnlyVisibleCategoryMessage("Playback apps", hiding=True),
			"Category cannot be hidden. Playback apps is already the only visible category",
		)

	def test_shown_with_singular_and_plural(self):
		messages.announceCategoryShown("Input devices", 1)
		messages.announceCategoryShown("Recording apps", 2)
		messages.announceOnlyCategory("Playback apps", 0)
		self.assertEqual(
			spoken,
			["Input devices shown, 1 source", "Recording apps shown, 2 sources", "Playback apps only, 0 sources"],
		)


class TestOtherMessages(AddonTestCase):
	def test_channels_are_numbered_from_one(self):
		options["status"] = False
		device = makeDevice("output", "{a}", "Speakers")
		messages.announceChannel(device)
		device.channel = 1
		messages.announceChannel(device)
		self.assertEqual(spoken, ["Channel 1", "Channel 2"])

	def test_application_without_sound(self):
		messages.announceNotPlaying("player")
		messages.announceNotPlaying("Zoom", model.SourceKind.RECORDING_APP)
		self.assertEqual(spoken, ["player is not playing any sound.", "Zoom is not recording any sound."])

	def test_channel_level_or_not_supported(self):
		device = makeDevice("output", "{a}", "Speakers")
		messages.announceChannelVolumeLevel(device, 0.4)
		messages.announceChannelVolumeLevel(device, -1.0)
		self.assertEqual(spoken, ["Volume 40%", "Not supported"])
