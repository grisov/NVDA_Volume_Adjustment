# settings.py
# Add-on settings panel
# A part of the NVDA Volume Adjustment add-on
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.
# Copyright (C) 2020-2026 Oleksandr Gryshchenko <grisov.nvaccess@mailgw.com>

# wxPython has incomplete type annotations and the GUI helpers of NVDA have none, so the types returned
# by most GUI calls in this file are unknown to the type checker, and many wx methods return values
# that are not needed here (e.g. the index of an appended item). A long translatable message is split
# into adjacent literals, which xgettext joins. Only these rules are relaxed for this file.
# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false
# pyright: reportUnknownLambdaType=false, reportUnusedCallResult=false, reportImplicitStringConcatenation=false

from collections.abc import Callable
from typing import cast, override

import addonHandler
import ui
import wx
from globalPluginHandler import reloadGlobalPlugins
from gui import guiHelper, nvdaControls
from gui.message import DefaultButtonSet, DialogType, MessageDialog
from gui.settingsDialogs import SettingsPanel
from logHandler import log
from queueHandler import eventQueue, queueFunction

from .configuration import addonSummary, cfg, getAddonConfig
from .devices import isInputDevice
from .messages import getCategoryName, getOnlyVisibleCategoryMessage
from .model import SourceKind
from .registry import registry
from .sources import (
	InputDeviceSource,
	getVisibleCategories,
	setVisibleCategories,
)

try:
	addonHandler.initTranslation()
except addonHandler.AddonError:
	log.warning("Unable to init translations. This may be because the addon is running from NVDA scratchpad.")
_: Callable[[str], str]


def getProcessNames() -> list[str]:
	"""Names of the processes playing or recording sound, each listed once.

	:return: names of the processes with audio sessions, the playing ones first
	"""
	names = [app.name for app in [*registry.getPlaybackApps(), *registry.getRecordingApps()]]
	return list(dict.fromkeys(names))


class AddonsReloadDialog(wx.Dialog):
	"""Global plugins reload request dialog."""

	def __init__(self, parent: wx.Window) -> None:
		"""Layout of dialog box elements to show.

		:param parent: parent top level window
		"""
		# Translators: The title of the dialog which appears when the user enables or disables the default gestures
		super().__init__(parent, title=_("Gestures Configuration Change"))
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		sHelper = guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)
		# Translators: The message displayed when addon gestures has been changed.
		message = _("NVDA add-ons must be reloaded for the new gestures to take effect.")
		sHelper.addItem(wx.StaticText(self, label=message))
		if not getAddonConfig()["gestures"]:
			sHelper.addItem(
				wx.StaticText(
					self,
					label=_(
						# Translators: The warning is displayed before switching on default addon gestures
						"Warning! Using the feature to set the maximum volume level may damage your hearing.",
					),
				),
			)

		bHelper = sHelper.addDialogDismissButtons(guiHelper.ButtonHelper(wx.HORIZONTAL))
		# Translators: The button in the dialog which appears when the user changed addon's default gestures
		reloadNowButton = bHelper.addButton(self, label=_("Reload &now"))
		reloadNowButton.Bind(wx.EVT_BUTTON, self.onReloadNowButton)
		reloadNowButton.SetFocus()

		# Translators: The button  in the dialog which appears when the user changed addon's default gestures
		reloadLaterButton = bHelper.addButton(self, wx.ID_CLOSE, label=_("Reload &later"))
		# The option is saved with the other settings, the gestures take effect after the add-ons are reloaded
		reloadLaterButton.Bind(wx.EVT_BUTTON, lambda evt: self.EndModal(wx.ID_CLOSE))
		self.EscapeId = wx.ID_CLOSE

		mainSizer.Add(sHelper.sizer, border=guiHelper.BORDER_FOR_DIALOGS, flag=wx.ALL)
		self.Sizer = mainSizer
		mainSizer.Fit(self)
		self.CentreOnScreen()

	def onReloadNowButton(self, event: wx.PyEvent) -> None:
		"""Executed when the appropriate button in the dialog box is pressed.

		:param event: event that occurs when a wx.Button is pressed
		"""
		panel = cast("VASettingsPanel", self.GetParent())
		getAddonConfig()["gestures"] = panel.defaultGesturesChk.GetValue()
		self.EndModal(wx.ID_OK)
		queueFunction(eventQueue, reloadGlobalPlugins)


class NvdaVolumeWarningDialog(MessageDialog):
	"""Warning shown before the volume of the audio session of NVDA itself is lowered or muted."""

	def __init__(self, parent: wx.Window) -> None:
		"""Create the warning dialog.

		:param parent: parent top level window
		"""
		super().__init__(
			parent,
			_(
				# Translators: The warning shown before the volume of NVDA itself is lowered or muted
				"This is the audio session of NVDA itself. "
				"Lowering or muting its volume also lowers or silences NVDA speech, "
				"and Windows keeps this volume even after NVDA is restarted. "
				"Do you want to continue?",
			),
			addonSummary,
			DialogType.WARNING,
			buttons=DefaultButtonSet.OK_CANCEL,
		)

	@override
	def _addContents(self, contentsSizer: guiHelper.BoxSizerHelper) -> None:
		"""Add the checkbox that disables the warning.

		:param contentsSizer: the sizer of the dialog contents
		"""
		self.dontShowAgainChk = contentsSizer.addItem(
			# Translators: The label of a checkbox in the warning about lowering the volume of NVDA itself
			wx.CheckBox(self, label=_("&Do not show this warning again")),
		)


class VASettingsPanel(SettingsPanel):
	"""Add-on settings panel object"""

	title: str = addonSummary

	@override
	def makeSettings(self, sizer: wx.BoxSizer) -> None:
		"""Populate the panel with settings controls.

		:param sizer: The sizer to which to add the settings controls.
		"""
		# BoxSizerHelper works with any window, NVDA annotates its parent as a dialog
		addonHelper = guiHelper.BoxSizerHelper(self, sizer=sizer)  # pyright: ignore[reportArgumentType]
		self.reportStatusChk = addonHelper.addItem(
			# Translators: This is the label for a checkbox in the settings panel.
			wx.CheckBox(self, label=_("Report the s&tatus of the sound source while switching")),
		)
		self.reportStatusChk.SetValue(getAddonConfig()["status"])
		self.announceCategoriesChk = addonHelper.addItem(
			# Translators: This is the label for a checkbox in the settings panel.
			wx.CheckBox(self, label=_("Announce category &names while switching")),
		)
		self.announceCategoriesChk.SetValue(getAddonConfig()["announceCategories"])
		self.deviceDetailsChk = addonHelper.addItem(
			# Translators: This is the label for a checkbox in the settings panel: the type, connection and
			# default role of an audio device are announced after its volume level or name
			wx.CheckBox(self, label=_("Announce audio device &details")),
		)
		self.deviceDetailsChk.SetValue(getAddonConfig()["deviceDetails"])
		self.visibleCategories = addonHelper.addLabeledControl(
			# Translators: The label of the Checkable list in the settings panel
			_("&Visible categories of audio sources:"),
			nvdaControls.CustomCheckListBox,
			choices=[getCategoryName(kind) for kind in SourceKind],
		)
		# Shown as changed with the gestures, which save the categories immediately
		visible = getVisibleCategories()
		self.visibleCategories.SetCheckedItems([i for i, kind in enumerate(SourceKind) if kind in visible])
		self.visibleCategories.SetSelection(0)
		self.visibleCategories.Bind(wx.EVT_CHECKLISTBOX, self.onVisibleCategoriesCheck)
		# Translators: The label of the component in the settings panel
		stepLabel = _("Volume level change &step:")
		self.volumeStep = addonHelper.addLabeledControl(
			# The step is in percents: the sign is added to the translated label, which is not changed
			f"{stepLabel[:-1]}, %:" if stepLabel.endswith(":") else f"{stepLabel}, %",
			nvdaControls.SelectOnFocusSpinCtrl,
			value=str(getAddonConfig()["step"]),
			min=1,
			max=20,
		)
		self.units = addonHelper.addLabeledControl(
			# Translators: The label of the choice list of the units of the announced volume level in the settings panel
			labelText=_("Announce the volume &level in:"),
			wxCtrlClass=wx.Choice,
			choices=[],
		)
		# Translators: An item in the choice list of the units of the announced volume level
		self.units.Append(_("Percent"), "percent")
		# Translators: An item in the choice list of the units of the announced volume level,
		# the level in percent is announced without the percent sign, e.g. "Volume 29"
		self.units.Append(_("Percent, number only"), "number")
		# Translators: An item in the choice list of the units of the announced volume level,
		# only audio devices provide their volume levels in decibels
		self.units.Append(_("Decibels, if the source supports it"), "decibels")
		self.units.Select(["percent", "number", "decibels"].index(getAddonConfig()["units"]))
		self.followFocusChk = addonHelper.addItem(
			# Translators: This is the label for a checkbox in the settings panel.
			wx.CheckBox(self, label=_("Chan&ge the volume of the current application")),
		)
		self.followFocusChk.SetValue(getAddonConfig()["focus"])

		# Names of all audio devices shown in the lists of hidden devices, by their IDs
		self.devs: dict[str, str] = {}
		self.hideOutputDevices = addonHelper.addLabeledControl(
			# Translators: The label of the Checkable list in the settings panel
			_("Hide output d&evices:"),
			nvdaControls.CustomCheckListBox,
			choices=[],
		)
		self.fillDeviceList(self.hideOutputDevices, isInput=False, includeHidden=True)
		outputButtons = guiHelper.ButtonHelper(orientation=wx.HORIZONTAL)
		self.updateOutputDevicesButton = outputButtons.addButton(self, id=wx.ID_REFRESH)
		self.clearOutputDevicesButton = outputButtons.addButton(self, id=wx.ID_CLEAR)
		addonHelper.addItem(outputButtons)
		self.updateOutputDevicesButton.Bind(
			wx.EVT_BUTTON,
			lambda event: self.onUpdateDevicesButton(self.hideOutputDevices, isInput=False),
		)
		self.clearOutputDevicesButton.Bind(
			wx.EVT_BUTTON,
			lambda event: self.onClearDevicesButton(self.hideOutputDevices, isInput=False),
		)
		self.hideInputDevices = addonHelper.addLabeledControl(
			# Translators: The label of the Checkable list in the settings panel
			_("Hide &input devices:"),
			nvdaControls.CustomCheckListBox,
			choices=[],
		)
		self.fillDeviceList(self.hideInputDevices, isInput=True, includeHidden=True)
		inputButtons = guiHelper.ButtonHelper(orientation=wx.HORIZONTAL)
		self.updateInputDevicesButton = inputButtons.addButton(self, id=wx.ID_REFRESH)
		self.clearInputDevicesButton = inputButtons.addButton(self, id=wx.ID_CLEAR)
		addonHelper.addItem(inputButtons)
		self.updateInputDevicesButton.Bind(
			wx.EVT_BUTTON,
			lambda event: self.onUpdateDevicesButton(self.hideInputDevices, isInput=True),
		)
		self.clearInputDevicesButton.Bind(
			wx.EVT_BUTTON,
			lambda event: self.onClearDevicesButton(self.hideInputDevices, isInput=True),
		)

		procs: list[str] = getProcessNames()
		self.procs = procs + [proc for proc in cfg.processes if proc not in procs]
		self.hideProcesses = addonHelper.addLabeledControl(
			# Translators: The label of the Checkable list in the settings panel
			_("Hide &processes:"),
			nvdaControls.CustomCheckListBox,
			choices=self.procs,
		)
		if len(self.procs) > 0:
			self.hideProcesses.SetCheckedStrings(cfg.processes)
			self.hideProcesses.SetSelection(0)

		procButtons = guiHelper.ButtonHelper(orientation=wx.HORIZONTAL)
		self.updateProcessesButton = procButtons.addButton(self, id=wx.ID_REFRESH)
		self.clearProcessesButton = procButtons.addButton(self, id=wx.ID_CLEAR)
		addonHelper.addItem(procButtons)
		self.updateProcessesButton.Bind(wx.EVT_BUTTON, self.onUpdateProcessesButton)
		self.clearProcessesButton.Bind(wx.EVT_BUTTON, self.onClearProcessesButton)

		self.muteMode = addonHelper.addLabeledControl(
			# Translators: This is the label for a choice list in the settings panel.
			labelText=_("&Mute mode:"),
			wxCtrlClass=wx.Choice,
			choices=[],
		)
		# Translators: An item in the choice list of mute modes in the settings panel
		self.muteMode.Append(_("Complete Mute"), 0)
		# Translators: An item in the choice list of mute modes in the settings panel
		self.muteMode.Append(_("Volume Down"), 1)
		self.muteMode.Select(int(not getAddonConfig()["muteCompletely"]))
		self.muteMode.Bind(wx.EVT_CHOICE, self.onMuteModeChoice)
		self.mutePercentageSlider = addonHelper.addLabeledControl(
			# Translators: This is the label for a slider in the settings panel.
			labelText=_("Decrease the volume &by, %"),
			wxCtrlClass=nvdaControls.EnhancedInputSlider,
			value=getAddonConfig()["mutePercentage"],
			minValue=1,
			maxValue=99,
			size=(250, -1),
		)
		# Disabled instead of hidden: when a labeled control is shown or hidden, NVDA sets the text of its label
		# without the "&" sign, so the shortcut of the label stops working
		self.mutePercentageSlider.Enable(not getAddonConfig()["muteCompletely"])
		self.unmuteOnExitChk = addonHelper.addItem(
			# Translators: This is the label for a checkbox in the settings panel.
			wx.CheckBox(self, label=_("&Unmute all muted audio resources at NVDA shutdown")),
		)
		self.unmuteOnExitChk.SetValue(getAddonConfig()["unmuteOnExit"])
		self.warnNvdaVolumeChk = addonHelper.addItem(
			# Translators: This is the label for a checkbox in the settings panel.
			wx.CheckBox(self, label=_("&Warn before lowering or muting the volume of NVDA itself")),
		)
		self.warnNvdaVolumeChk.SetValue(getAddonConfig()["warnNvdaVolume"])
		self.quickMuteDevices = addonHelper.addLabeledControl(
			# Translators: The label of the Checkable list in the settings panel: the input devices
			# muted and unmuted together by one command
			_("Microphones of the &quick mute:"),
			nvdaControls.CustomCheckListBox,
			choices=[],
		)
		self.fillDeviceList(self.quickMuteDevices, isInput=True, includeHidden=True, saved=cfg.quickMute)
		quickMuteButtons = guiHelper.ButtonHelper(orientation=wx.HORIZONTAL)
		self.updateQuickMuteButton = quickMuteButtons.addButton(self, id=wx.ID_REFRESH)
		self.clearQuickMuteButton = quickMuteButtons.addButton(self, id=wx.ID_CLEAR)
		addonHelper.addItem(quickMuteButtons)
		self.updateQuickMuteButton.Bind(
			wx.EVT_BUTTON,
			lambda event: self.onUpdateDevicesButton(
				self.quickMuteDevices,
				isInput=True,
				saved=cfg.quickMute,
			),
		)
		self.clearQuickMuteButton.Bind(
			wx.EVT_BUTTON,
			lambda event: self.onClearDevicesButton(self.quickMuteDevices, isInput=True),
		)
		self.defaultGesturesChk = addonHelper.addItem(
			# Translators: This is the label for a checkbox in the settings panel.
			wx.CheckBox(self, label=_("Use default &keyboard shortcuts")),
		)
		self.defaultGesturesChk.SetValue(getAddonConfig()["gestures"])
		self.defaultGesturesChk.Bind(wx.EVT_CHECKBOX, self.onGesturesCheckbox)

	def onMuteModeChoice(self, event: wx.PyEvent) -> None:
		"""Select the mute mode - completely turn off or partial decrease of the volume level,
		the slider of the percentage is available only for the decrease.

		:param event: event binder object which processes changing of the wx.Choice
		"""
		mode: int = self.muteMode.GetClientData(self.muteMode.GetSelection())
		self.mutePercentageSlider.Enable(bool(mode))

	def onGesturesCheckbox(self, event: wx.PyEvent) -> None:
		"""Enabling or disabling default keyboard shortcuts: the add-ons are reloaded now or later.

		:param event: event binder object which processes changing of the wx.Checkbox
		"""
		# The dialog is destroyed when it is closed with any of its buttons
		with AddonsReloadDialog(self) as dialog:
			dialog.ShowModal()
		self.defaultGesturesChk.SetFocus()

	def fillDeviceList(
		self,
		control: nvdaControls.CustomCheckListBox,
		isInput: bool,
		includeHidden: bool,
		saved: dict[str, str] | None = None,
	) -> None:
		"""Fill a checkable list of output or input devices: the devices to hide or the microphones of the quick mute.

		:param control: the checkable list of output or input devices
		:param isInput: whether the list contains input devices
		:param includeHidden: whether the saved devices are listed and checked, also those not connected now
		:param saved: the saved devices of the list, the hidden devices by default
		"""
		if saved is None:
			saved = cfg.devices
		items: dict[str, str] = {}
		if includeHidden:
			items.update((id, name) for id, name in saved.items() if isInputDevice(id) == isInput)
		for device in registry.detectDevices():
			if isinstance(device, InputDeviceSource) == isInput:
				items.setdefault(device.id, device.name)
		self.devs.update(items)
		control.Clear()
		for id, name in items.items():
			control.Append(name, id)
		if includeHidden:
			control.SetCheckedItems([i for i, id in enumerate(items) if id in saved])
		if items:
			control.SetSelection(0)

	def onUpdateDevicesButton(
		self,
		control: nvdaControls.CustomCheckListBox,
		isInput: bool,
		saved: dict[str, str] | None = None,
	) -> None:
		"""Update the list of connected audio devices when the appropriate button is pressed,
		the saved devices are checked again.

		:param control: the checkable list of output or input devices
		:param isInput: whether the list contains input devices
		:param saved: the saved devices of the list, the hidden devices by default
		"""
		self.fillDeviceList(control, isInput, includeHidden=True, saved=saved)
		control.SetFocus()

	def onClearDevicesButton(self, control: nvdaControls.CustomCheckListBox, isInput: bool) -> None:
		"""Uncheck all audio devices and remove those that are not connected now.

		:param control: the checkable list of output or input devices
		:param isInput: whether the list contains input devices
		"""
		self.fillDeviceList(control, isInput, includeHidden=False)
		control.SetFocus()

	def onUpdateProcessesButton(self, event: wx.PyEvent) -> None:
		"""Update the list of currently running processes when the appropriate button is pressed.

		:param event: event that occurs when a wx.Button is pressed
		"""
		procs = getProcessNames()
		self.procs = procs + [proc for proc in cfg.processes if proc not in procs]
		self.hideProcesses.Clear()
		self.hideProcesses.SetItems(self.procs)
		if len(self.procs) > 0:
			self.hideProcesses.SetCheckedStrings(cfg.processes)
			self.hideProcesses.SetSelection(0)
		self.hideProcesses.SetFocus()

	def onClearProcessesButton(self, event: wx.PyEvent) -> None:
		"""Uncheck all installed checkboxes and remove unnecessary processes.

		:param event: event that occurs when a wx.Button is pressed
		"""
		self.procs = getProcessNames()
		self.hideProcesses.Clear()
		self.hideProcesses.SetItems(self.procs)
		if len(self.procs) > 0:
			self.hideProcesses.SetSelection(0)
		self.hideProcesses.SetFocus()

	def onVisibleCategoriesCheck(self, event: wx.CommandEvent) -> None:
		"""Keep at least one category of audio sources visible.

		:param event: event that occurs when an item of the checkable list is checked or unchecked
		"""
		if self.visibleCategories.GetCheckedItems():
			return
		index = event.GetInt()
		self.visibleCategories.Check(index, True)
		ui.message(getOnlyVisibleCategoryMessage(getCategoryName(list(SourceKind)[index]), hiding=True))

	@override
	def onSave(self) -> None:
		"""Update Configuration when clicking OK."""
		getAddonConfig()["status"] = self.reportStatusChk.GetValue()
		getAddonConfig()["announceCategories"] = self.announceCategoriesChk.GetValue()
		getAddonConfig()["deviceDetails"] = self.deviceDetailsChk.GetValue()
		checked = self.visibleCategories.GetCheckedItems()
		setVisibleCategories([kind for i, kind in enumerate(SourceKind) if i in checked])
		getAddonConfig()["step"] = self.volumeStep.GetValue()
		getAddonConfig()["focus"] = self.followFocusChk.GetValue()
		getAddonConfig()["units"] = self.units.GetClientData(self.units.GetSelection())
		getAddonConfig()["muteCompletely"] = not self.muteMode.GetClientData(
			self.muteMode.GetSelection(),
		)
		getAddonConfig()["mutePercentage"] = self.mutePercentageSlider.GetValue()
		getAddonConfig()["unmuteOnExit"] = self.unmuteOnExitChk.GetValue()
		getAddonConfig()["warnNvdaVolume"] = self.warnNvdaVolumeChk.GetValue()
		# Saved here when the add-ons are reloaded later, e.g. when NVDA is restarted
		getAddonConfig()["gestures"] = self.defaultGesturesChk.GetValue()
		devs = {}
		for control in (self.hideOutputDevices, self.hideInputDevices):
			for checked in control.GetCheckedItems():
				id = control.GetClientData(checked)
				devs[id] = self.devs[id]
		procs = self.hideProcesses.GetCheckedStrings()
		quickMute = {
			self.quickMuteDevices.GetClientData(checked): self.devs[
				self.quickMuteDevices.GetClientData(checked)
			]
			for checked in self.quickMuteDevices.GetCheckedItems()
		}
		isChangedDevices = cfg.isChangedDevices(devs)
		isChangedQuickMute = set(quickMute) != set(cfg.quickMute)
		if cfg.isChangedProcesses(procs) or isChangedDevices or isChangedQuickMute:
			cfg.devices = devs
			cfg.processes = procs
			cfg.quickMute = quickMute
			cfg.save()
			if isChangedDevices:
				# Re-initialize the list of devices for the new settings to take effect
				registry.scanDevices(cfg.devices)
