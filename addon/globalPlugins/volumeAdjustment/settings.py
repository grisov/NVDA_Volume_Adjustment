# settings.py
# Add-on settings panel
# A part of the NVDA Volume Adjustment add-on
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.
# Copyright (C) 2020-2026 Oleksandr Gryshchenko <grisov.nvaccess@mailgw.com>

from typing import Callable, Dict, List
import addonHandler
import config
import ui
import wx
from globalPluginHandler import reloadGlobalPlugins
from gui import guiHelper, nvdaControls
from gui.message import DefaultButtonSet, DialogType, MessageDialog
from gui.settingsDialogs import SettingsPanel
from logHandler import log
from queueHandler import eventQueue, queueFunction
from . import addonName, addonSummary
from .audiocore import cfg
from .sources import InputDeviceSource, SourceKind, registry

try:
	addonHandler.initTranslation()
except addonHandler.AddonError:
	log.warning("Unable to init translations. This may be because the addon is running from NVDA scratchpad.")
_: Callable[[str], str]


def getCategoryName(kind: SourceKind) -> str:
	"""Get the name of the category of audio sources to announce.
	@param kind: the category of audio sources
	@type kind: SourceKind
	@return: the translated name of the category
	@rtype: str
	"""
	if kind == SourceKind.OUTPUT_DEVICE:
		# Translators: The name of the category of audio sources announced while switching between them
		return _("Output devices")
	if kind == SourceKind.INPUT_DEVICE:
		# Translators: The name of the category of audio sources announced while switching between them
		return _("Input devices")
	if kind == SourceKind.PLAYBACK_APP:
		# Translators: The name of the category of audio sources announced while switching between them
		return _("Playback apps")
	# Translators: The name of the category of audio sources announced while switching between them
	return _("Recording apps")


def getOnlyVisibleCategoryMessage(category: str, hiding: bool = False) -> str:
	"""Get the message that the category is already the only visible one,
	when it is shown as the only category or the user tries to hide it.
	@param category: the name of the category
	@type category: str
	@param hiding: whether the user tries to hide the category
	@type hiding: bool
	@return: the message to announce
	@rtype: str
	"""
	# Translators: The message when the category of audio sources is already the only visible one,
	# e.g. when the user tries to hide it, {category} is its name, e.g. "Recording apps"
	message = _("{category} is already the only visible category").format(category=category)
	if not hiding:
		return message
	# Translators: The message when the user tries to hide the only visible category of audio sources,
	# followed by the message that it is already the only visible category
	prefix = _("Category cannot be hidden.")
	return f"{prefix} {message}"


def getVisibleCategories() -> List[SourceKind]:
	"""Categories of audio sources available for switching, in their order.
	@return: the visible categories, all of them if the saved value contains none
	@rtype: List[SourceKind]
	"""
	visible: str = config.conf[addonName]["categories"]
	return [kind for kind in SourceKind if kind.value in visible] or list(SourceKind)


def setVisibleCategories(categories: List[SourceKind]) -> None:
	"""Save the visible categories of audio sources, always in the order of the categories.
	@param categories: the categories to show
	@type categories: List[SourceKind]
	"""
	config.conf[addonName]["categories"] = "".join(kind.value for kind in SourceKind if kind in categories)


def getProcessNames() -> List[str]:
	"""Names of the processes playing or recording sound, each listed once.
	@return: names of the processes with audio sessions, the playing ones first
	@rtype: List[str]
	"""
	names = [app.name for app in [*registry.getApps(), *registry.getRecordingApps()]]
	return list(dict.fromkeys(names))


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
		sHelper.addItem(
			# Translators: The message displayed when addon gestures has been changed.
			wx.StaticText(
				self,
				label=_("NVDA add-ons must be reloaded for the new gestures to take effect."),
			),
		)
		if not config.conf[addonName]["gestures"]:
			sHelper.addItem(
				# Translators: The warning is displayed before switching on default addon gestures
				wx.StaticText(
					self,
					label=_(
						"Warning! Using the feature to set the maximum volume level may damage your hearing.",
					),
				),  # noqa E501
			)

		bHelper = sHelper.addDialogDismissButtons(guiHelper.ButtonHelper(wx.HORIZONTAL))
		# Translators: The button in the dialog which appears when the user changed addon's default gestures
		reloadNowButton = bHelper.addButton(self, label=_("Reload &now"))
		reloadNowButton.Bind(wx.EVT_BUTTON, self.onReloadNowButton)
		reloadNowButton.SetFocus()

		# Translators: The button  in the dialog which appears when the user changed addon's default gestures
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
		config.conf[addonName]["gestures"] = self.GetParent().defaultGesturesChk.GetValue()
		self.EndModal(1)
		self.Destroy()
		queueFunction(eventQueue, reloadGlobalPlugins)


class NvdaVolumeWarningDialog(MessageDialog):
	"""Warning shown before the volume of the audio session of NVDA itself is lowered or muted."""

	def __init__(self, parent: wx.Window) -> None:
		"""Create the warning dialog.
		@param parent: parent top level window
		@type parent: wx.Window
		"""
		super(NvdaVolumeWarningDialog, self).__init__(
			parent,
			# Translators: The warning shown before the volume of NVDA itself is lowered or muted
			_(
				"This is the audio session of NVDA itself. "
				"Lowering or muting its volume also lowers or silences NVDA speech, "
				"and Windows keeps this volume even after NVDA is restarted. "
				"Do you want to continue?",
			),
			addonSummary,
			DialogType.WARNING,
			buttons=DefaultButtonSet.OK_CANCEL,
		)

	def _addContents(self, contentsSizer: guiHelper.BoxSizerHelper) -> None:
		"""Add the checkbox that disables the warning.
		@param contentsSizer: the sizer of the dialog contents
		@type contentsSizer: guiHelper.BoxSizerHelper
		"""
		self.dontShowAgainChk = contentsSizer.addItem(
			# Translators: The label of a checkbox in the warning about lowering the volume of NVDA itself
			wx.CheckBox(self, label=_("&Do not show this warning again")),
		)


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
			wx.CheckBox(self, label=_("&Report the status of the sound source while switching")),
		)
		self.reportStatusChk.SetValue(config.conf[addonName]["status"])
		self.announceCategoriesChk = addonHelper.addItem(
			# Translators: This is the label for a checkbox in the settings panel.
			wx.CheckBox(self, label=_("Announce &category names while switching")),
		)
		self.announceCategoriesChk.SetValue(config.conf[addonName]["announceCategories"])
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
			value=str(config.conf[addonName]["step"]),
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
		# only audio devices provide their volume levels in decibels
		self.units.Append(_("Decibels, if the source supports it"), "decibels")
		self.units.Select(int(config.conf[addonName]["units"] == "decibels"))
		self.followFocusChk = addonHelper.addItem(
			# Translators: This is the label for a checkbox in the settings panel.
			wx.CheckBox(self, label=_("Change the volume of the current &application")),
		)
		self.followFocusChk.SetValue(config.conf[addonName]["focus"])

		procs: List[str] = getProcessNames()
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

		# Names of all audio devices shown in the lists of hidden devices, by their IDs
		self.devs: Dict[str, str] = {}
		self.hideOutputDevices = addonHelper.addLabeledControl(
			# Translators: The label of the Checkable list in the settings panel
			_("Hide &output devices:"),
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
		self.muteMode.Select(int(not config.conf[addonName]["muteCompletely"]))
		self.muteMode.Bind(wx.EVT_CHOICE, self.onMuteModeChoice)
		self.mutePercentageSlider = addonHelper.addLabeledControl(
			# Translators: This is the label for a slider in the settings panel.
			labelText=_("Decrease the volume &by, %"),
			wxCtrlClass=nvdaControls.EnhancedInputSlider,
			value=config.conf[addonName]["mutePercentage"],
			minValue=1,
			maxValue=99,
			size=(250, -1),
		)
		self.mutePercentageSlider.Show(show=not config.conf[addonName]["muteCompletely"])
		self.unmuteOnExitChk = addonHelper.addItem(
			# Translators: This is the label for a checkbox in the settings panel.
			wx.CheckBox(self, label=_("&Unmute all muted audio resources at NVDA shutdown")),
		)
		self.unmuteOnExitChk.SetValue(config.conf[addonName]["unmuteOnExit"])
		self.warnNvdaVolumeChk = addonHelper.addItem(
			# Translators: This is the label for a checkbox in the settings panel.
			wx.CheckBox(self, label=_("&Warn before lowering or muting the volume of NVDA itself")),
		)
		self.warnNvdaVolumeChk.SetValue(config.conf[addonName]["warnNvdaVolume"])
		self.defaultGesturesChk = addonHelper.addItem(
			# Translators: This is the label for a checkbox in the settings panel.
			wx.CheckBox(self, label=_("Use default &keyboard shortcuts")),
		)
		self.defaultGesturesChk.SetValue(config.conf[addonName]["gestures"])
		self.defaultGesturesChk.Bind(wx.EVT_CHECKBOX, self.onGesturesCheckbox)

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

	def fillDeviceList(
		self, control: nvdaControls.CustomCheckListBox, isInput: bool, includeHidden: bool
	) -> None:
		"""Fill the list of output or input devices that can be hidden.
		@param control: the checkable list of output or input devices
		@type control: nvdaControls.CustomCheckListBox
		@param isInput: whether the list contains input devices
		@type isInput: bool
		@param includeHidden: whether the hidden devices are listed and checked, also those not connected now
		@type includeHidden: bool
		"""
		items: Dict[str, str] = {}
		if includeHidden:
			items.update(
				(id, name) for id, name in cfg.devices.items() if registry.isInputDevice(id) == isInput
			)
		for device in registry.getAllDevices():
			if isinstance(device, InputDeviceSource) == isInput:
				items.setdefault(device.id, device.name)
		self.devs.update(items)
		control.Clear()
		for id, name in items.items():
			control.Append(name, id)
		if includeHidden:
			control.SetCheckedItems([i for i, id in enumerate(items) if id in cfg.devices])
		if items:
			control.SetSelection(0)

	def onUpdateDevicesButton(self, control: nvdaControls.CustomCheckListBox, isInput: bool) -> None:
		"""Update the list of connected audio devices when the appropriate button is pressed,
		the saved hidden devices are checked again.
		@param control: the checkable list of output or input devices
		@type control: nvdaControls.CustomCheckListBox
		@param isInput: whether the list contains input devices
		@type isInput: bool
		"""
		self.fillDeviceList(control, isInput, includeHidden=True)
		control.SetFocus()

	def onClearDevicesButton(self, control: nvdaControls.CustomCheckListBox, isInput: bool) -> None:
		"""Uncheck all audio devices and remove those that are not connected now.
		@param control: the checkable list of output or input devices
		@type control: nvdaControls.CustomCheckListBox
		@param isInput: whether the list contains input devices
		@type isInput: bool
		"""
		self.fillDeviceList(control, isInput, includeHidden=False)
		control.SetFocus()

	def onUpdateProcessesButton(self, event: wx.PyEvent) -> None:
		"""Update the list of currently running processes when the appropriate button is pressed.
		@param event: event that occurs when a wx.Button is pressed
		@type event: wx.PyEvent
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
		@param event: event that occurs when a wx.Button is pressed
		@type event: wx.PyEvent
		"""
		self.procs = getProcessNames()
		self.hideProcesses.Clear()
		self.hideProcesses.SetItems(self.procs)
		if len(self.procs) > 0:
			self.hideProcesses.SetSelection(0)
		self.hideProcesses.SetFocus()

	def onVisibleCategoriesCheck(self, event: wx.CommandEvent) -> None:
		"""Keep at least one category of audio sources visible.
		@param event: event that occurs when an item of the checkable list is checked or unchecked
		@type event: wx.CommandEvent
		"""
		if self.visibleCategories.GetCheckedItems():
			return
		index = event.GetInt()
		self.visibleCategories.Check(index, True)
		ui.message(getOnlyVisibleCategoryMessage(getCategoryName(list(SourceKind)[index]), hiding=True))

	def postInit(self) -> None:
		"""Set system focus to the first component in the settings panel."""
		self.reportStatusChk.SetFocus()

	def onSave(self) -> None:
		"""Update Configuration when clicking OK."""
		config.conf[addonName]["status"] = self.reportStatusChk.GetValue()
		config.conf[addonName]["announceCategories"] = self.announceCategoriesChk.GetValue()
		checked = self.visibleCategories.GetCheckedItems()
		setVisibleCategories([kind for i, kind in enumerate(SourceKind) if i in checked])
		config.conf[addonName]["step"] = self.volumeStep.GetValue()
		config.conf[addonName]["focus"] = self.followFocusChk.GetValue()
		config.conf[addonName]["units"] = self.units.GetClientData(self.units.GetSelection())
		config.conf[addonName]["muteCompletely"] = not self.muteMode.GetClientData(
			self.muteMode.GetSelection(),
		)
		config.conf[addonName]["mutePercentage"] = self.mutePercentageSlider.GetValue()
		config.conf[addonName]["unmuteOnExit"] = self.unmuteOnExitChk.GetValue()
		config.conf[addonName]["warnNvdaVolume"] = self.warnNvdaVolumeChk.GetValue()
		devs = {}
		for control in (self.hideOutputDevices, self.hideInputDevices):
			for checked in control.GetCheckedItems():
				id = control.GetClientData(checked)
				devs[id] = self.devs[id]
		procs = self.hideProcesses.GetCheckedStrings()
		isChangedDevices = cfg.isChangedDevices(devs)
		if cfg.isChangedProcesses(procs) or isChangedDevices:
			cfg.devices = devs
			cfg.processes = procs
			cfg.save()
			if isChangedDevices:
				# Re-initialize the list of devices for the new settings to take effect
				registry.scanDevices(cfg.devices)
