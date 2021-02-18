#settings.py
# Add-on settings panel
# A part of the NVDA Volume Adjustment add-on
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.
# Copyright (C) 2020-2021 Olexandr Gryshchenko <grisov.nvaccess@mailnull.com>

from __future__ import annotations
import addonHandler
from logHandler import log
try:
	addonHandler.initTranslation()
except addonHandler.AddonError:
	log.warning("Unable to initialise translations. This may be because the addon is running from NVDA scratchpad.")

import wx
import config
from gui import SettingsPanel, guiHelper, nvdaControls
from globalPluginHandler import reloadGlobalPlugins
from queueHandler import queueFunction, eventQueue
from . import addonName, addonSummary
from .audiocore import devices, hidden, AudioUtilities


class AddonsReloadDialog(wx.Dialog):
	"""Global plugins reload request dialog."""

	def __init__(self, parent: wx.Window) -> None:
		"""Layout of dialog box elements to show.
		@param parent: parent top level window
		@type parent: wx.Window
		"""
		# Translators: The title of the dialog which appears when the user enables or disables the default gestures
		super(AddonsReloadDialog, self).__init__(parent, title=_("Gestures Configuration Change"))
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		sHelper = guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)
		# Translators: The message displayed when addon gestures has been changed.
		sHelper.addItem(wx.StaticText(self, label=_("NVDA add-ons must be reloaded for the new gestures to take effect.")))

		bHelper = sHelper.addDialogDismissButtons(guiHelper.ButtonHelper(wx.HORIZONTAL))
		# Translators: The label for a button  in the dialog which appears when the user changed addon's default gestures
		reloadNowButton = bHelper.addButton(self, label=_("Reload &now"))
		reloadNowButton.Bind(wx.EVT_BUTTON, self.onReloadNowButton)
		reloadNowButton.SetFocus()

		# Translators: The label for a button  in the dialog which appears when the user changed NVDA's interface language.
		reloadLaterButton = bHelper.addButton(self, wx.ID_CLOSE, label=_("Reload &later"))
		reloadLaterButton.Bind(wx.EVT_BUTTON, lambda evt: self.Close())
		self.Bind(wx.EVT_CLOSE, lambda evt: self.Destroy())
		self.EscapeId = wx.ID_CLOSE

		mainSizer.Add(sHelper.sizer, border=guiHelper.BORDER_FOR_DIALOGS, flag=wx.ALL)
		self.Sizer = mainSizer
		mainSizer.Fit(self)
		self.CentreOnScreen()

	def onReloadNowButton(self, eventt: wx._core.PyEvent) -> None:
		"""Executed when the appropriate button in the dialog box is pressed.
		@param event: event that occurs when a wx.Button is pressed
		@type event: wx._core.PyEvent
		"""
		self.Destroy()
		config.conf.save()
		queueFunction(eventQueue, reloadGlobalPlugins)


class VASettingsPanel(SettingsPanel):
	"""Add-on settings panel object"""
	title = addonSummary

	def __init__(self, parent: wx.Window) -> None:
		"""Initializing the add-on settings panel object.
		@param parent: parent top level window
		@type parent: wx.Window
		"""
		super(VASettingsPanel, self).__init__(parent)

	def makeSettings(self, sizer: wx._core.Sizer) -> None:
		"""Populate the panel with settings controls.
		@param sizer: The sizer to which to add the settings controls.
		@type sizer: wx._core.Sizer
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
		self.updateProcessesButton = wx.Button(self, id=wx.ID_REFRESH)
		self.updateProcessesButton.Bind(wx.EVT_BUTTON, self.onUpdateProcessesButton)
		procButtons.Add(self.updateProcessesButton)
		self.clearProcessesButton = wx.Button(self, id=wx.ID_CLEAR)
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
		self.updateDevicesButton = wx.Button(self, id=wx.ID_REFRESH)
		self.updateDevicesButton.Bind(wx.EVT_BUTTON, self.onUpdateDevicesButton)
		self.devButtons.Add(self.updateDevicesButton)
		self.clearDevicesButton = wx.Button(self, id=wx.ID_CLEAR)
		self.clearDevicesButton.Bind(wx.EVT_BUTTON, self.onClearDevicesButton)
		self.devButtons.Add(self.clearDevicesButton)
		sizer.Add(self.devButtons, flag=wx.RIGHT)
		sizer.Show(self.devButtons, show=self.advancedChk.GetValue())

		self.defaultGesturesChk = addonHelper.addItem(
		# Translators: This is the label for a checkbox in the settings panel.
			wx.CheckBox(self, label=_("Use default &keyboard shortcuts"))
		)
		self.defaultGesturesChk.SetValue(config.conf[addonName]['gestures'])
		self.defaultGesturesChk.Bind(wx.EVT_CHECKBOX, self.onGesturesCheckbox)

	def onAdvancedCheckbox(self, event: wx._core.PyEvent) -> None:
		"""Enabling or disabling advanced add-on features.
		Ability to adjust volume level of all detected audio devices (experimental function).
		@param event: event binder object which processes changing of the wx.Checkbox
		@type event: wx._core.PyEvent
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

	def onGesturesCheckbox(self, event: wx._core.PyEvent) -> None:
		"""Enabling or disabling default keyboard shortcuts.
		@param event: event binder object which processes changing of the wx.Checkbox
		@type event: wx._core.PyEvent
		"""
		config.conf[addonName]['gestures'] = event.IsChecked()
		AddonsReloadDialog(self).ShowModal()

	def onUpdateDevicesButton(self, event: wx._core.PyEvent) -> None:
		"""Update the list of connected audio devices when the appropriate button is pressed.
		@param event: event that occurs when a wx.Button is pressed
		@type event: wx._core.PyEvent
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

	def onClearDevicesButton(self, event: wx._core.PyEvent) -> None:
		"""Uncheck all installed checkboxes and remove unnecessary audio devices.
		@param event: event that occurs when a wx.Button is pressed
		@type event: wx._core.PyEvent
		"""
		self.hideDevices.Clear()
		for dev in devices:
			self.hideDevices.Append(dev.name, dev.id)
		if len(devices)>0:
			self.hideDevices.SetSelection(0)
		self.hideDevices.SetFocus()

	def onUpdateProcessesButton(self, event: wx._core.PyEvent) -> None:
		"""Update the list of currently running processes when the appropriate button is pressed.
		@param event: event that occurs when a wx.Button is pressed
		@type event: wx._core.PyEvent
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

	def onClearProcessesButton(self, event: wx._core.PyEvent) -> None:
		"""Uncheck all installed checkboxes and remove unnecessary processes.
		@param event: event that occurs when a wx.Button is pressed
		@type event: wx._core.PyEvent
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
