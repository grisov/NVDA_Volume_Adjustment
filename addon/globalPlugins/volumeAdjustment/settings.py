#settings.py
# Add-on settings panel
# A part of the NVDA Volume Adjustment add-on
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.
# Copyright (C) 2020 Olexandr Gryshchenko <grisov.nvaccess@mailnull.com>

import addonHandler
from logHandler import log
try:
	addonHandler.initTranslation()
except addonHandler.AddonError:
	log.warning("Unable to initialise translations. This may be because the addon is running from NVDA scratchpad.")

import wx
from gui import SettingsPanel, guiHelper, nvdaControls
import config
from . import addonName, addonSummary
from .audiocore import devices, hidden, AudioUtilities


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
		self.sizer = sizer
		addonHelper = guiHelper.BoxSizerHelper(self, sizer=sizer)
		# Translators: The label of the component in the settings panel
		self.volumeStep = addonHelper.addLabeledControl(_("Volume level change &step:"), nvdaControls.SelectOnFocusSpinCtrl,
			value=str(config.conf[addonName]['step']), min=1, max=20)
		self.followFocusChk = addonHelper.addItem(
		# Translators: This is the label for a checkbox in the settings panel.
			wx.CheckBox(self, label=_("Change the volume of the current &application"))
		)
		self.followFocusChk.SetValue(config.conf[addonName]['focus'])
		self.hideDuplicatesChk = addonHelper.addItem(
		# Translators: This is the label for a checkbox in the settings panel.
			wx.CheckBox(self, label=_("Hide audio sessions with the same &names"))
		)
		self.hideDuplicatesChk.SetValue(config.conf[addonName]['duplicates'])

		procs = [s.Process.name() for s in AudioUtilities.GetAllSessions() if s.Process and s.Process.name()]
		self.procs = list(set(procs)) if config.conf[addonName]['duplicates'] else procs
		self.procs.extend([proc for proc in hidden.processes if proc not in procs])
		# Translators: The label of the Checkable list in the settings panel
		self.hideProcesses = addonHelper.addLabeledControl(_("Hide &processes:"), nvdaControls.CustomCheckListBox, choices=self.procs)
		if len(self.procs)>0:
			self.hideProcesses.SetCheckedStrings(hidden.processes)
			self.hideProcesses.SetSelection(0)

		procButtons = wx.BoxSizer(wx.HORIZONTAL)
		# Translators: The label of the button in the settings panel
		self.updateProcessesButton = wx.Button(self, label=_("Update"))
		self.updateProcessesButton.Bind(wx.EVT_BUTTON, self.onUpdateProcessesButton)
		procButtons.Add(self.updateProcessesButton)
		# Translators: The label of the button in the settings panel
		self.clearProcessesButton = wx.Button(self, label=_("Clear"))
		self.clearProcessesButton.Bind(wx.EVT_BUTTON, self.onClearProcessesButton)
		procButtons.Add(self.clearProcessesButton)
		sizer.Add(procButtons, flag=wx.RIGHT)

		self.advancedChk = addonHelper.addItem(
		# Translators: This is the label for a checkbox in the settings panel.
			wx.CheckBox(self, label=_("&Control all available audio devices (experimental)"))
		)
		self.advancedChk.SetValue(config.conf[addonName]['advanced'])
		self.advancedChk.Bind(wx.EVT_CHECKBOX, self.onAdvancedCheckbox)
		# Translators: The label of the Checkable list in the settings panel
		self.hideDevices = addonHelper.addLabeledControl(_("Hide audio &devices:"), nvdaControls.CustomCheckListBox, choices=[])
		self.devs = dict(hidden.devices)
		self.devs.update({devices[i].id: devices[i].name for i in range(len(devices))})
		for id,name in self.devs.items():
			self.hideDevices.Append(name, id)
		if len(self.devs)>0:
			self.hideDevices.SetCheckedStrings([self.devs[id] for id in hidden.devices])
			self.hideDevices.SetSelection(0)
		self.hideDevices.Show(show=self.advancedChk.GetValue())

		self.devButtons = wx.BoxSizer(wx.HORIZONTAL)
		# Translators: The label of the button in the settings panel
		self.updateDevicesButton = wx.Button(self, label=_("Update"))
		self.updateDevicesButton.Bind(wx.EVT_BUTTON, self.onUpdateDevicesButton)
		self.devButtons.Add(self.updateDevicesButton)
		# Translators: The label of the button in the settings panel
		self.clearDevicesButton = wx.Button(self, label=_("Clear"))
		self.clearDevicesButton.Bind(wx.EVT_BUTTON, self.onClearDevicesButton)
		self.devButtons.Add(self.clearDevicesButton)
		sizer.Add(self.devButtons, flag=wx.RIGHT)
		sizer.Show(self.devButtons, show=self.advancedChk.GetValue())

	def onAdvancedCheckbox(self, event) -> None:
		"""Enabling or disabling advanced add-on features.
		Ability to adjust volume level of all detected audio devices (experimental function).
		@param event: event binder object which processes changing of the wx.Checkbox
		@type event: wx.core.PyEventBinder
		"""
		config.conf[addonName]['advanced'] = event.IsChecked()
		devices.initialize(hidden.devices)
		self.hideDevices.Clear()
		self.devs = dict(hidden.devices)
		self.devs.update({devices[i].id: devices[i].name for i in range(len(devices))})
		for id,name in self.devs.items():
			self.hideDevices.Append(name, id)
		if len(self.devs)>0:
			self.hideDevices.SetCheckedStrings([self.devs[id] for id in hidden.devices])
			self.hideDevices.SetSelection(0)
		self.hideDevices.Show(show=event.IsChecked())
		self.sizer.Show(self.devButtons, show=event.IsChecked())
		self.sizer.Fit(self)
		self.hideDevices.GetParent().Layout()

	def onUpdateDevicesButton(self, event) -> None:
		"""Update the list of connected audio devices when the appropriate button is pressed.
		@param event: event that occurs when a wx.Button is pressed
		@type event: wx.core.PyEventBinder
		"""
		devices.initialize()
		self.hideDevices.Clear()
		self.devs = dict(hidden.devices)
		self.devs.update({devices[i].id: devices[i].name for i in range(len(devices))})
		for id,name in self.devs.items():
			self.hideDevices.Append(name, id)
		if len(self.devs)>0:
			self.hideDevices.SetCheckedStrings([self.devs[id] for id in hidden.devices])
			self.hideDevices.SetSelection(0)
		self.hideDevices.SetFocus()

	def onClearDevicesButton(self, event) -> None:
		"""Uncheck all installed checkboxes and remove unnecessary audio devices.
		@param event: event that occurs when a wx.Button is pressed
		@type event: wx.core.PyEventBinder
		"""
		self.hideDevices.Clear()
		for dev in devices:
			self.hideDevices.Append(dev.name, dev.id)
		if len(devices)>0:
			self.hideDevices.SetSelection(0)
		self.hideDevices.SetFocus()

	def onUpdateProcessesButton(self, event) -> None:
		"""Update the list of currently running processes when the appropriate button is pressed.
		@param event: event that occurs when a wx.Button is pressed
		@type event: wx.core.PyEventBinder
		"""
		procs = [s.Process.name() for s in AudioUtilities.GetAllSessions() if s.Process and s.Process.name()]
		self.procs = list(set(procs)) if config.conf[addonName]['duplicates'] else procs
		self.procs.extend([proc for proc in hidden.processes if proc not in procs])
		self.hideProcesses.Clear()
		self.hideProcesses.SetItems(self.procs)
		if len(self.procs)>0:
			self.hideProcesses.SetCheckedStrings(hidden.processes)
			self.hideProcesses.SetSelection(0)
		self.hideProcesses.SetFocus()

	def onClearProcessesButton(self, event) -> None:
		"""Uncheck all installed checkboxes and remove unnecessary processes.
		@param event: event that occurs when a wx.Button is pressed
		@type event: wx.core.PyEventBinder
		"""
		self.procs = [s.Process.name() for s in AudioUtilities.GetAllSessions() if s.Process and s.Process.name()]
		self.hideProcesses.Clear()
		self.hideProcesses.SetItems(self.procs)
		if len(self.procs)>0:
			self.hideProcesses.SetSelection(0)
		self.hideProcesses.SetFocus()

	def postInit(self) -> None:
		"""Set system focus to the first component in the settings panel."""
		self.volumeStep.SetFocus()

	def onSave(self) -> None:
		"""Update Configuration when clicking OK."""
		config.conf[addonName]['step'] = self.volumeStep.GetValue()
		config.conf[addonName]['focus'] = self.followFocusChk.GetValue()
		config.conf[addonName]['duplicates'] = self.hideDuplicatesChk.GetValue()
		devs = {}
		for checked in self.hideDevices.GetCheckedItems():
			id = self.hideDevices.GetClientData(checked)
			devs[id] = self.devs[id]
		procs = self.hideProcesses.GetCheckedStrings()
		isChangedDevices = hidden.isChangedDevices(devs)
		if hidden.isChangedProcesses(procs) or isChangedDevices:
			hidden.devices = devs
			hidden.processes = procs
			hidden.save()
			if isChangedDevices:
				# Re-initialize the list of devices for the new settings to take effect
				devices.scan(hidden.devices)
