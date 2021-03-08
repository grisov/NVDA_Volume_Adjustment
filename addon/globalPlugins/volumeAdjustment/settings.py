#settings.py
# Add-on settings panel
# A part of the NVDA Volume Adjustment add-on
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.
# Copyright (C) 2020-2021 Olexandr Gryshchenko <grisov.nvaccess@mailnull.com>

from typing import Callable
import addonHandler
from logHandler import log
try:
	addonHandler.initTranslation()
except addonHandler.AddonError:
	log.warning("Unable to initialise translations. This may be because the addon is running from NVDA scratchpad.")
_: Callable[[str], str]

import wx
import config
from gui import SettingsPanel, guiHelper, nvdaControls
from globalPluginHandler import reloadGlobalPlugins
from queueHandler import queueFunction, eventQueue
from . import addonName, addonSummary
from .pycaw import AudioUtilities
from .audiocore import cfg, devices


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
		if not config.conf[addonName]['gestures']:
			# Translators: The warning is displayed before switching on default addon gestures
			sHelper.addItem(wx.StaticText(self, label=_("Warning! Using the feature to set the maximum volume level may damage your hearing.")))

		bHelper = sHelper.addDialogDismissButtons(guiHelper.ButtonHelper(wx.HORIZONTAL))
		# Translators: The label for a button  in the dialog which appears when the user changed addon's default gestures
		reloadNowButton = bHelper.addButton(self, label=_("Reload &now"))
		reloadNowButton.Bind(wx.EVT_BUTTON, self.onReloadNowButton)
		reloadNowButton.SetFocus()

		# Translators: The label for a button  in the dialog which appears when the user changed addon's default gestures
		reloadLaterButton = bHelper.addButton(self, wx.ID_CLOSE, label=_("Reload &later"))
		reloadLaterButton.Bind(wx.EVT_BUTTON, lambda evt: self.Close())
		self.Bind(wx.EVT_CLOSE, lambda evt: self.Destroy())
		self.EscapeId = wx.ID_CLOSE

		mainSizer.Add(sHelper.sizer, border=guiHelper.BORDER_FOR_DIALOGS, flag=wx.ALL)
		self.Sizer = mainSizer
		mainSizer.Fit(self)
		self.CentreOnScreen()

	def onReloadNowButton(self, eventt: wx.PyEvent) -> None:
		"""Executed when the appropriate button in the dialog box is pressed.
		@param event: event that occurs when a wx.Button is pressed
		@type event: wx.PyEvent
		"""
		config.conf[addonName]['gestures'] = self.GetParent().defaultGesturesChk.GetValue()
		self.EndModal(1)
		self.Destroy()
		queueFunction(eventQueue, reloadGlobalPlugins)


class VASettingsPanel(SettingsPanel):
	"""Add-on settings panel object"""
	title: str = addonSummary

	def __init__(self, parent: wx.Window) -> None:
		"""Initializing the add-on settings panel object.
		@param parent: parent top level window
		@type parent: wx.Window
		"""
		super(VASettingsPanel, self).__init__(parent)

	def makeSettings(self, sizer: wx.Sizer) -> None:
		"""Populate the panel with settings controls.
		@param sizer: The sizer to which to add the settings controls.
		@type sizer: wx.Sizer
		"""
		self.sizer = sizer
		addonHelper = guiHelper.BoxSizerHelper(self, sizer=sizer)
		self.reportStatusChk = addonHelper.addItem(
		# Translators: This is the label for a checkbox in the settings panel.
			wx.CheckBox(self, label=_("&Report the status of the sound source while switching"))
		)
		self.reportStatusChk.SetValue(config.conf[addonName]['status'])
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
		self.procs.extend([proc for proc in cfg.processes if proc not in procs])
		# Translators: The label of the Checkable list in the settings panel
		self.hideProcesses = addonHelper.addLabeledControl(_("Hide &processes:"), nvdaControls.CustomCheckListBox, choices=self.procs)
		if len(self.procs)>0:
			self.hideProcesses.SetCheckedStrings(cfg.processes)
			self.hideProcesses.SetSelection(0)

		procButtons = addonHelper.addDialogDismissButtons(guiHelper.ButtonHelper(wx.HORIZONTAL))
		self.updateProcessesButton = procButtons.addButton(self, id=wx.ID_REFRESH)
		self.updateProcessesButton.Bind(wx.EVT_BUTTON, self.onUpdateProcessesButton)
		self.clearProcessesButton = procButtons.addButton(self, id=wx.ID_CLEAR)
		self.clearProcessesButton.Bind(wx.EVT_BUTTON, self.onClearProcessesButton)

		self.advancedChk = addonHelper.addItem(
		# Translators: This is the label for a checkbox in the settings panel.
			wx.CheckBox(self, label=_("C&ontrol all available audio devices (experimental)"))
		)
		self.advancedChk.SetValue(config.conf[addonName]['advanced'])
		self.advancedChk.Bind(wx.EVT_CHECKBOX, self.onAdvancedCheckbox)
		# Translators: The label of the Checkable list in the settings panel
		self.hideDevices = addonHelper.addLabeledControl(_("Hide audio &devices:"), nvdaControls.CustomCheckListBox, choices=[])
		self.devs = dict(cfg.devices)
		self.devs.update({devices[i].id: devices[i].name for i in range(len(devices))})
		for id,name in self.devs.items():
			self.hideDevices.Append(name, id)
		if len(self.devs)>0:
			self.hideDevices.SetCheckedStrings([self.devs[id] for id in cfg.devices])
			self.hideDevices.SetSelection(0)
		self.hideDevices.Show(show=self.advancedChk.GetValue())

		self.devButtons = addonHelper.addDialogDismissButtons(guiHelper.ButtonHelper(wx.HORIZONTAL))
		self.updateDevicesButton = self.devButtons.addButton(self, id=wx.ID_REFRESH)
		self.updateDevicesButton.Bind(wx.EVT_BUTTON, self.onUpdateDevicesButton)
		self.clearDevicesButton = self.devButtons.addButton(self, id=wx.ID_CLEAR)
		self.clearDevicesButton.Bind(wx.EVT_BUTTON, self.onClearDevicesButton)
		sizer.Show(self.devButtons.sizer, show=self.advancedChk.GetValue())

		self.muteMode = addonHelper.addLabeledControl(
			# Translators: This is the label for a choice list in the settings panel.
			labelText=_("&Mute mode:"),
			wxCtrlClass=wx.Choice, choices=[]
		)
		# Translators: An item in the choice list of mute modes in the settings panel
		self.muteMode.Append(_("Complete Mute"), 0)
		# Translators: An item in the choice list of mute modes in the settings panel
		self.muteMode.Append(_("Volume Down"), 1)
		self.muteMode.Select(int(not config.conf[addonName]['muteCompletely']))
		self.muteMode.Bind(wx.EVT_CHOICE, self.onMuteModeChoice)
		self.mutePercentageSlider = addonHelper.addLabeledControl(
			# Translators: This is the label for a slider in the settings panel.
			labelText=_("Decrease the volume &by, %"),
			wxCtrlClass=nvdaControls.EnhancedInputSlider, value=config.conf[addonName]['mutePercentage'],
			minValue=1, maxValue=99, size=(250, -1)
		)
		self.mutePercentageSlider.Show(show=not config.conf[addonName]['muteCompletely'])
		self.unmuteOnExitChk = addonHelper.addItem(
		# Translators: This is the label for a checkbox in the settings panel.
			wx.CheckBox(self, label=_("&Unmute all muted audio resources at NVDA shutdown"))
		)
		self.unmuteOnExitChk.SetValue(config.conf[addonName]['unmuteOnExit'])
		self.defaultGesturesChk = addonHelper.addItem(
		# Translators: This is the label for a checkbox in the settings panel.
			wx.CheckBox(self, label=_("Use default &keyboard shortcuts"))
		)
		self.defaultGesturesChk.SetValue(config.conf[addonName]['gestures'])
		self.defaultGesturesChk.Bind(wx.EVT_CHECKBOX, self.onGesturesCheckbox)

	def onAdvancedCheckbox(self, event: wx.PyEvent) -> None:
		"""Enabling or disabling advanced add-on features.
		Ability to adjust volume level of all detected audio devices (experimental function).
		@param event: event binder object which processes changing of the wx.Checkbox
		@type event: wx.PyEvent
		"""
		config.conf[addonName]['advanced'] = event.IsChecked()
		devices.initialize(cfg.devices)
		self.hideDevices.Clear()
		self.devs = dict(cfg.devices)
		self.devs.update({devices[i].id: devices[i].name for i in range(len(devices))})
		for id,name in self.devs.items():
			self.hideDevices.Append(name, id)
		if event.IsChecked() and len(self.devs)>0:
			self.hideDevices.SetCheckedStrings([self.devs[id] for id in cfg.devices])
			self.hideDevices.SetSelection(0)
		self.hideDevices.Show(show=event.IsChecked())
		self.sizer.Show(self.devButtons.sizer, show=event.IsChecked())
		self.sizer.Fit(self)
		self.hideDevices.GetParent().Layout()

	def onMuteModeChoice(self, event: wx.PyEvent) -> None:
		"""Select the mute mode - completely turn off or partial decrease of the volume level,
		dynamically controls the showing of the volume mute slider.
		@param event: event binder object which processes changing of the wx.Choice
		@type event: wx.PyEvent
		"""
		mode: int = self.muteMode.GetClientData(self.muteMode.GetSelection())
		self.mutePercentageSlider.Show(show=mode)
		self.mutePercentageSlider.GetParent().Layout()
		self.sizer.Fit(self)

	def onGesturesCheckbox(self, event: wx.PyEvent) -> None:
		"""Enabling or disabling default keyboard shortcuts.
		@param event: event binder object which processes changing of the wx.Checkbox
		@type event: wx.PyEvent
		"""
		if not AddonsReloadDialog(self).ShowModal():
			self.defaultGesturesChk.SetValue(not event.IsChecked())
		self.defaultGesturesChk.SetFocus()

	def onUpdateDevicesButton(self, event: wx.PyEvent) -> None:
		"""Update the list of connected audio devices when the appropriate button is pressed.
		@param event: event that occurs when a wx.Button is pressed
		@type event: wx.PyEvent
		"""
		devices.initialize()
		self.hideDevices.Clear()
		self.devs = dict(cfg.devices)
		self.devs.update({devices[i].id: devices[i].name for i in range(len(devices))})
		for id,name in self.devs.items():
			self.hideDevices.Append(name, id)
		if len(self.devs)>0:
			self.hideDevices.SetCheckedStrings([self.devs[id] for id in cfg.devices])
			self.hideDevices.SetSelection(0)
		self.hideDevices.SetFocus()

	def onClearDevicesButton(self, event: wx.PyEvent) -> None:
		"""Uncheck all installed checkboxes and remove unnecessary audio devices.
		@param event: event that occurs when a wx.Button is pressed
		@type event: wx.PyEvent
		"""
		self.hideDevices.Clear()
		for dev in devices:
			self.hideDevices.Append(dev.name, dev.id)
		if len(devices)>0:
			self.hideDevices.SetSelection(0)
		self.hideDevices.SetFocus()

	def onUpdateProcessesButton(self, event: wx.PyEvent) -> None:
		"""Update the list of currently running processes when the appropriate button is pressed.
		@param event: event that occurs when a wx.Button is pressed
		@type event: wx.PyEvent
		"""
		procs = [s.Process.name() for s in AudioUtilities.GetAllSessions() if s.Process and s.Process.name()]
		self.procs = list(set(procs)) if config.conf[addonName]['duplicates'] else procs
		self.procs.extend([proc for proc in cfg.processes if proc not in procs])
		self.hideProcesses.Clear()
		self.hideProcesses.SetItems(self.procs)
		if len(self.procs)>0:
			self.hideProcesses.SetCheckedStrings(cfg.processes)
			self.hideProcesses.SetSelection(0)
		self.hideProcesses.SetFocus()

	def onClearProcessesButton(self, event: wx.PyEvent) -> None:
		"""Uncheck all installed checkboxes and remove unnecessary processes.
		@param event: event that occurs when a wx.Button is pressed
		@type event: wx.PyEvent
		"""
		self.procs = [s.Process.name() for s in AudioUtilities.GetAllSessions() if s.Process and s.Process.name()]
		self.hideProcesses.Clear()
		self.hideProcesses.SetItems(self.procs)
		if len(self.procs)>0:
			self.hideProcesses.SetSelection(0)
		self.hideProcesses.SetFocus()

	def postInit(self) -> None:
		"""Set system focus to the first component in the settings panel."""
		self.reportStatusChk.SetFocus()

	def onSave(self) -> None:
		"""Update Configuration when clicking OK."""
		config.conf[addonName]['status'] = self.reportStatusChk.GetValue()
		config.conf[addonName]['step'] = self.volumeStep.GetValue()
		config.conf[addonName]['focus'] = self.followFocusChk.GetValue()
		config.conf[addonName]['duplicates'] = self.hideDuplicatesChk.GetValue()
		config.conf[addonName]['muteCompletely'] = not self.muteMode.GetClientData(self.muteMode.GetSelection())
		config.conf[addonName]['mutePercentage'] = self.mutePercentageSlider.GetValue()
		config.conf[addonName]['unmuteOnExit'] = self.unmuteOnExitChk.GetValue()
		devs = {}
		for checked in self.hideDevices.GetCheckedItems():
			id = self.hideDevices.GetClientData(checked)
			devs[id] = self.devs[id]
		procs = self.hideProcesses.GetCheckedStrings()
		isChangedDevices = cfg.isChangedDevices(devs)
		if cfg.isChangedProcesses(procs) or isChangedDevices:
			cfg.devices = devs
			cfg.processes = procs
			cfg.save()
			if isChangedDevices:
				# Re-initialize the list of devices for the new settings to take effect
				devices.scan(cfg.devices)
