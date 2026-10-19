# A part of the NVDA Volume Adjustment add-on
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.
# Copyright (C) 2020-2026 Oleksandr Gryshchenko <grisov.nvaccess@mailgw.com>

"""Unit tests of model.py: the volume step, the categories of audio sources and the connection of audio devices.
The module is loaded by its path: importing the add-on package would need NVDA and Windows.
"""

import importlib.util
import struct
import sys
import unittest
from pathlib import Path

MODEL_PATH = Path(__file__).parents[3] / "addon" / "globalPlugins" / "volumeAdjustment" / "model.py"
_spec = importlib.util.spec_from_file_location("volumeAdjustmentModel", MODEL_PATH)
assert _spec is not None and _spec.loader is not None
model = importlib.util.module_from_spec(_spec)
# Registered before execution, as the import system does for every module
sys.modules[_spec.name] = model
_spec.loader.exec_module(model)


def float32(value: float) -> float:
	"""The value as Windows stores volume levels: a 32-bit float, e.g. 0.29 is read back as 0.28999999."""
	return struct.unpack("f", struct.pack("f", value))[0]


class TestStepLevel(unittest.TestCase):
	"""The volume level changes by the step and stops at whole percents."""

	def test_whole_percent_changes_by_the_step(self):
		self.assertEqual(model.stepLevel(0.5, 1), 0.51)
		self.assertEqual(model.stepLevel(0.5, -1), 0.49)
		self.assertEqual(model.stepLevel(0.5, 10), 0.6)

	def test_float32_level_is_treated_as_the_whole_percent(self):
		# 29 % is read back from Windows as 28.999999 %: the next step must give 30 %, not 29 %
		self.assertEqual(model.stepLevel(float32(0.29), 1), 0.3)
		self.assertEqual(model.stepLevel(float32(0.29), -1), 0.28)

	def test_level_between_whole_percents_moves_to_the_next_one_in_the_direction(self):
		# A level set by another program, e.g. 29.6 %, first moves to 30 % up or to 29 % down
		self.assertEqual(model.stepLevel(0.296, 1), 0.3)
		self.assertEqual(model.stepLevel(0.296, -1), 0.29)

	def test_limits(self):
		self.assertEqual(model.stepLevel(0.99, 5), 1.0)
		self.assertEqual(model.stepLevel(1.0, 1), 1.0)
		self.assertEqual(model.stepLevel(0.02, -5), 0.0)
		self.assertEqual(model.stepLevel(0.0, -1), 0.0)

	def test_every_step_from_0_to_100_and_back_is_announced_once(self):
		level = 0.0
		percents = []
		for _ in range(100):
			level = float32(model.stepLevel(level, 1))
			percents.append(round(level * 100))
		self.assertEqual(percents, list(range(1, 101)))
		for _ in range(100):
			level = float32(model.stepLevel(level, -1))
			percents.append(round(level * 100))
		self.assertEqual(percents[100:], list(range(99, -1, -1)))


class TestCategories(unittest.TestCase):
	"""The categories of audio sources and their letters in the configuration."""

	def test_order_and_letters(self):
		self.assertEqual([kind.value for kind in model.SourceKind], ["O", "I", "P", "R"])

	def test_parse_keeps_the_order_of_the_categories(self):
		kind = model.SourceKind
		self.assertEqual(model.parseCategories("RO"), [kind.OUTPUT_DEVICE, kind.RECORDING_APP])
		self.assertEqual(model.parseCategories("P"), [kind.PLAYBACK_APP])

	def test_parse_without_categories_gives_all_of_them(self):
		self.assertEqual(model.parseCategories(""), list(model.SourceKind))
		self.assertEqual(model.parseCategories("xyz"), list(model.SourceKind))

	def test_format_keeps_the_order_and_skips_duplicates(self):
		kind = model.SourceKind
		self.assertEqual(model.formatCategories([kind.RECORDING_APP, kind.OUTPUT_DEVICE, kind.OUTPUT_DEVICE]), "OR")
		self.assertEqual(model.formatCategories(list(kind)), "OIPR")
		self.assertEqual(model.formatCategories([]), "")

	def test_format_and_parse_round_trip(self):
		for letters in ("O", "IP", "OIPR", "PR"):
			self.assertEqual(model.formatCategories(model.parseCategories(letters)), letters)


class TestConnection(unittest.TestCase):
	"""How an audio device is connected, from its device enumerator and the interface path of its adapter."""

	def test_enumerators(self):
		connection = model.Connection
		self.assertIs(connection.fromEnumeratorName("HDAUDIO"), connection.INTERNAL)
		self.assertIs(connection.fromEnumeratorName("INTELAUDIO"), connection.INTERNAL)
		self.assertIs(connection.fromEnumeratorName("USB"), connection.USB)
		self.assertIs(connection.fromEnumeratorName("BTHENUM"), connection.BLUETOOTH)
		self.assertIs(connection.fromEnumeratorName("BTHHFENUM"), connection.BLUETOOTH)
		self.assertIs(connection.fromEnumeratorName("ROOT"), connection.VIRTUAL)
		self.assertIs(connection.fromEnumeratorName("SWD"), connection.VIRTUAL)
		self.assertIs(connection.fromEnumeratorName("usb"), connection.USB)

	def test_unknown_or_missing_enumerator(self):
		self.assertIs(model.Connection.fromEnumeratorName("XYZ"), model.Connection.OTHER)
		self.assertIs(model.Connection.fromEnumeratorName(None), model.Connection.OTHER)

	def test_intel_usb_audio_offload_is_usb(self):
		path = r"\\?\intelaudio#ctlr_dev_51ca&linktype_06&devtype_06&ven_8086#{6994ad04}\intcusbwaverender_99e8"
		self.assertIs(model.Connection.fromEnumeratorName("INTELAUDIO", path), model.Connection.USB)

	def test_intel_sound_card_and_microphones_stay_internal(self):
		codec = r"\\?\intelaudio#func_01&ven_10ec&dev_0289#{6994ad04}\rearlineoutwavesst"
		microphones = r"\\?\intelaudio#ctlr_dev_51ca&linktype_02&devtype_00#{6994ad04}\intcdmicwave_0"
		self.assertIs(model.Connection.fromEnumeratorName("INTELAUDIO", codec), model.Connection.INTERNAL)
		self.assertIs(model.Connection.fromEnumeratorName("INTELAUDIO", microphones), model.Connection.INTERNAL)


class TestFormFactor(unittest.TestCase):
	"""The physical types of audio devices follow EndpointFormFactor of Windows."""

	def test_values_of_windows(self):
		self.assertEqual(model.FormFactor.SPEAKERS, 1)
		self.assertEqual(model.FormFactor.HEADPHONES, 3)
		self.assertEqual(model.FormFactor.MICROPHONE, 4)
		self.assertEqual(model.FormFactor.DIGITAL_AUDIO_DISPLAY_DEVICE, 9)
		self.assertEqual(model.FormFactor.UNKNOWN, 10)


if __name__ == "__main__":
	unittest.main()
