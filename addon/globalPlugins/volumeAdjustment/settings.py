#settings.py
# A part of NonVisual Desktop Access (NVDA)
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.
# Copyright (C) 2020 Olexandr Gryshchenko <grisov.nvaccess@mailnull.com>

import addonHandler
from logHandler import log
try:
	addonHandler.initTranslation()
except addonHandler.AddonError:
	log.warning("Unable to initialise translations. This may be because the addon is running from NVDA scratchpad.")

from gui import SettingsPanel, guiHelper, nvdaControls
import wx
import config
from . import addonName, addonSummary
from .core import devices, AudioUtilities


class VASettingsPanel(SettingsPanel):
	"""Add-on settings panel object"""
	title = addonSummary

	def __init__(self, parent):
		"""Initializing the add-on settings panel object"""
		super(VASettingsPanel, self).__init__(parent)

	def makeSettings(self, sizer: wx._core.BoxSizer):
		"""Populate the panel with settings controls.
		@param sizer: The sizer to which to add the settings controls.
		@type sizer: wx._core.BoxSizer
		"""
		sHelper = guiHelper.BoxSizerHelper(self, sizer=sizer)
		# Translators:
		self.hideDevices = sHelper.addLabeledControl(_("Hide audio &devices:"), nvdaControls.CustomCheckListBox, choices=[])
		for i in range(len(devices)):
			self.hideDevices.Append(devices[i].name, devices[i].id)
		if len(devices)>0:
			self.hideDevices.SetCheckedStrings([devices[-1].name])
			self.hideDevices.SetSelection(0)

		processes = [s.Process.name() for s in AudioUtilities.GetAllSessions() if s.Process and s.Process.name]
		# Translators:
		self.hideProcesses = sHelper.addLabeledControl(_("Hide &processes:"), nvdaControls.CustomCheckListBox, choices=processes)
		if len(processes)>0:
			self.hideProcesses.SetCheckedStrings(['nvda.exe'])
			self.hideProcesses.SetSelection(0)

		# Translators:
		self.volumeStep = sHelper.addLabeledControl(_("Step to change the &volume level:"), nvdaControls.SelectOnFocusSpinCtrl,
			value=str(config.conf[addonName]['step']), min=1, max=20)

	def postInit(self):
		"""Set system focus to source language selection dropdown list."""
		#self._customVolumeSlider.SetFocus()
		pass

	def onSave(self):
		"""Update Configuration when clicking OK."""
		# self.hideDevices.GetCheckedStrings()
		# self.hideProcesses.GetCheckedStrings()
		config.conf[addonName]['step'] = self.volumeStep.GetValue()
