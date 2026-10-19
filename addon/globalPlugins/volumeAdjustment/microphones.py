# microphones.py
# The quick mute of the microphones selected in the add-on settings, with its sounds
# A part of the NVDA Volume Adjustment add-on
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.
# Copyright (C) 2020-2026 Oleksandr Gryshchenko <grisov.nvaccess@mailgw.com>

from __future__ import annotations
import os.path
import wave
from typing import Any, cast
import core
import nvwave
from comtypes import COMError
from logHandler import log
from .audiocore import logDebugWarning
from .configuration import cfg
from .messages import announceNoQuickMuteMicrophones, announceQuickMuteMicrophonesNotConnected
from .registry import registry
from .sources import InputDeviceSource

# Sounds of the quick mute of the microphones, generated for the add-on
_soundsDir = os.path.join(os.path.dirname(__file__), "sounds")
MICROPHONES_ON_SOUND = os.path.join(_soundsDir, "micOn.wav")
MICROPHONES_OFF_SOUND = os.path.join(_soundsDir, "micOff.wav")


def getSoundDuration(path: str) -> int:
	"""Get the duration of a wave file.

	:param path: the path of the wave file
	:return: the duration in milliseconds, 0 if the file cannot be read
	"""
	try:
		with wave.open(path, "rb") as sound:
			return round(sound.getnframes() / sound.getframerate() * 1000)
	except (OSError, EOFError, wave.Error):
		return 0


class QuickMute:
	"""Mutes and unmutes in Windows the microphones selected in the add-on settings, for all programs at once."""

	def getQuickMuteDevices(self) -> list[InputDeviceSource]:
		"""Get the connected input devices selected for the quick mute in the add-on settings.
		Hidden devices and categories do not matter: the quick mute works for all selected microphones.

		:return: the connected input devices of the quick mute
		"""
		ids = cfg.quickMute
		return [
			device
			for device in registry.getAllDevices()
			if isinstance(device, InputDeviceSource) and device.id in ids
		]

	def setQuickMute(self, devices: list[InputDeviceSource], mute: bool) -> None:
		"""Mute or unmute the input devices in Windows, so all programs get silence or sound from them.

		:param devices: the input devices of the quick mute
		:param mute: whether to mute the devices
		"""
		for device in devices:
			volume = device.volume
			if volume is None:
				continue
			try:
				volume.SetMute(int(mute), None)
			except COMError:
				logDebugWarning(f"Unable to change the mute state of {device.name}")

	def playSound(self, path: str) -> None:
		"""Play a sound of the add-on without waiting for its end, an error is logged.

		:param path: the path of the wave file
		"""
		try:
			nvwave.playWaveFile(path, asynchronous=True)
		except Exception:
			log.error(f"Unable to play {path}", exc_info=True)

	def toggle(self) -> None:
		"""Mute all microphones selected in the add-on settings if any of them is on, otherwise unmute them all.
		Only a sound is played: after muting and before unmuting, so the microphones do not record it.
		"""
		if not cfg.quickMute:
			announceNoQuickMuteMicrophones()
			return
		devices = self.getQuickMuteDevices()
		if not devices:
			announceQuickMuteMicrophonesNotConnected()
			return
		isMuted: list[bool] = []
		for device in devices:
			volume = device.volume
			try:
				isMuted.append(volume is not None and bool(volume.GetMute()))
			except COMError:
				isMuted.append(False)
		if not all(isMuted):
			# Any microphone on: all of them are muted, so the first press always gives silence
			self.setQuickMute(devices, mute=True)
			self.playSound(MICROPHONES_OFF_SOUND)
			return
		# The microphones are unmuted when the sound has been played, so it is not recorded
		self.playSound(MICROPHONES_ON_SOUND)
		# core.callLater of NVDA has no type annotations
		cast(Any, core).callLater(
			getSoundDuration(MICROPHONES_ON_SOUND) + 20,
			self.setQuickMute,
			devices,
			False,
		)
