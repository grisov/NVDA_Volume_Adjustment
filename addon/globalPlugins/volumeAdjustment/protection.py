# protection.py
# The warning before the volume of NVDA itself is lowered or muted
# A part of the NVDA Volume Adjustment add-on
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.
# Copyright (C) 2020-2026 Oleksandr Gryshchenko <grisov.nvaccess@mailgw.com>

from __future__ import annotations

import os
from collections.abc import Callable
from typing import cast

import gui
import wx
from gui.message import ReturnCode

from .configuration import getAddonConfig
from .settings import NvdaVolumeWarningDialog
from .sources import AudioSource, PlaybackAppSource


class NvdaVolumeGuard:
	"""Asks for confirmation before the volume or a channel of NVDA itself is lowered or muted:
	NVDA could become silent, and Windows keeps this volume after NVDA restarts.
	"""

	def __init__(self) -> None:
		"""The warning is not shown yet."""
		super().__init__()
		# Whether the warning about lowering the volume of NVDA itself is currently shown
		self._isWarningShown: bool = False

	def isNvdaSession(self, source: AudioSource) -> bool:
		"""Check whether the audio source is the audio session of NVDA itself, which plays NVDA speech.

		:param source: audio source to check
		:return: whether the audio source belongs to the running NVDA process
		"""
		return isinstance(source, PlaybackAppSource) and os.getpid() in source.processIds

	def runWithNvdaWarning(self, source: AudioSource, action: Callable[[], None]) -> None:
		"""Run the action that lowers or mutes the volume of the audio source.
		For the audio session of NVDA itself, the action runs only after the user confirms the warning,
		unless the warning has been disabled with its checkbox or in the add-on settings.

		:param source: the audio source whose volume is changed
		:param action: the change of the volume and its announcement
		"""
		if not getAddonConfig()["warnNvdaVolume"] or not self.isNvdaSession(source):
			action()
			return
		if self._isWarningShown:
			return

		def showWarning() -> None:
			self._isWarningShown = True
			confirmed = False
			try:
				dialog = NvdaVolumeWarningDialog(cast(wx.Window, gui.mainFrame))
				with dialog:
					confirmed = dialog.ShowModal() == ReturnCode.OK
					if confirmed and dialog.dontShowAgainChk.GetValue():
						getAddonConfig()["warnNvdaVolume"] = False
			finally:
				self._isWarningShown = False
			if confirmed:
				action()

		wx.CallAfter(showWarning)
