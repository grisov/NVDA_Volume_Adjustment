# A part of the NVDA Volume Adjustment add-on
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.
# Copyright (C) 2020-2026 Oleksandr Gryshchenko <grisov.nvaccess@mailgw.com>

from __future__ import annotations
from typing import Any, cast, override
from collections.abc import Callable
import addonHandler
import config
import globalPluginHandler
from globalVars import appArgs
from gui import settingsDialogs
from inputCore import InputGesture
from logHandler import log
from NVDAObjects import NVDAObject
from scriptHandler import script
from . import devices
from .configuration import addonName, addonSummary, cfg, confspec, getAddonConfig
from .messages import (
	announceChannel,
	announceChannelVolumeLevel,
	announceMuted,
	announceNotSupported,
	announceVolumeLevel,
)
from .microphones import QuickMute
from .navigation import SourceNavigator
from .outputs import OutputSwitcher, OutputTarget
from .protection import NvdaVolumeGuard
from .registry import registry
from .model import LEVEL_TOLERANCE, SourceKind

try:
	addonHandler.initTranslation()
except addonHandler.AddonError:
	log.warning("Unable to init translations. This may be because the addon is running from NVDA scratchpad.")
_: Callable[[str], str]

from .settings import VASettingsPanel  # noqa E402


# Number of the function keys F1..F12 bound to the output devices
FUNCTION_KEYS = 12
# Prefixes of the names of the scripts created for each output device, see bindSwitchingMethods()
OUTPUT_DEVICE_SCRIPTS = ("switchNvdaOutputToDevice", "setDefaultOutputDevice", "setCommunicationDevice")


def disableInSecureMode[PluginT: type[globalPluginHandler.GlobalPlugin]](decoratedCls: PluginT) -> PluginT:
	"""Replace the global plugin with an empty one in the secure mode of NVDA (e.g. on the logon screen).

	:param decoratedCls: the global plugin of the add-on
	:return: the global plugin to use, the empty base class in the secure mode
	"""
	# appArgs of NVDA has no type annotations
	if cast(Any, appArgs).secure:
		# The empty base class stands for the plugin: NVDA only creates it and calls its methods
		return cast(PluginT, globalPluginHandler.GlobalPlugin)
	return decoratedCls


@disableInSecureMode
class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	"""Implementation global commands of NVDA Volume Adjustment add-on."""

	scriptCategory: str = addonSummary

	def __init__(self, *args: Any, **kwargs: Any) -> None:
		"""Initializing initial configuration values and other fields."""
		super().__init__(*args, **kwargs)
		cast(Any, config.conf).spec[addonName] = confspec
		settingsDialogs.NVDASettingsDialog.categoryClasses.append(VASettingsPanel)
		# The selected audio source and the switching between sources and categories
		self.navigator = SourceNavigator()
		# The warning before the volume of NVDA itself is lowered or muted
		self.guard = NvdaVolumeGuard()
		# Switching the output devices of NVDA and Windows
		self.outputs = OutputSwitcher()
		# The quick mute of the selected microphones
		self.quickMute = QuickMute()
		# Bind default gestures if necessary
		if getAddonConfig()["gestures"]:
			# ScriptableObject.bindGestures of NVDA has no type annotations
			self.bindGestures(self.__defaultGestures)  # pyright: ignore[reportUnknownMemberType]
		# Creating the switching methods for the output devices found when NVDA starts
		self.bindSwitchingMethods()
		registry.start(cfg.devices)

	@override
	def terminate(self, *args: Any, **kwargs: Any) -> None:
		"""This will be called when NVDA is finished with this global plugin."""
		if getAddonConfig()["unmuteOnExit"]:
			# It takes a few milliseconds and uses the COM objects of audio devices created in this thread
			try:
				self.navigator.unmuteAllAudioSources()
			except Exception:
				log.error("Unable to unmute audio sources on exit", exc_info=True)
		registry.stop()
		try:
			settingsDialogs.NVDASettingsDialog.categoryClasses.remove(VASettingsPanel)
		except ValueError:
			log.warning("Can't remove %s Settings panel from NVDA settings dialogs", addonSummary)
		super().terminate(*args, **kwargs)

	def event_gainFocus(self, obj: NVDAObject, NextHandler: Callable[[], None]) -> None:
		"""Track the application in focus if the corresponding option is enabled.

		:param obj: the object to track if focused
		:param nextHandler: next event handler
		"""
		if getAddonConfig()["focus"]:
			self.navigator.onFocusChanged()
		NextHandler()

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Increase the volume"))
	def script_volumeUp(self, gesture: InputGesture) -> None:
		"""Increase the volume of the selected audio source."""
		source = self.navigator.getSelectedAudioSource()
		if source is None:
			return
		announceVolumeLevel(source.volumeUp(), source)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Decrease the volume"))
	def script_volumeDown(self, gesture: InputGesture) -> None:
		"""Decrease the volume of the selected audio source."""
		source = self.navigator.getSelectedAudioSource()
		if source is None:
			return

		def volumeDown() -> None:
			volumeLevel = source.volumeDown()
			if volumeLevel > 0.0:
				announceVolumeLevel(volumeLevel, source)
				return
			source.mute()
			announceMuted(source)

		self.guard.runWithNvdaWarning(source, volumeDown)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Set the maximum volume level"))
	def script_volumeMax(self, gesture: InputGesture) -> None:
		"""Set the maximum volume level for the selected audio source."""
		source = self.navigator.getSelectedAudioSource()
		if source is None:
			return
		announceVolumeLevel(source.volumeMax(), source)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Set the minimum volume level"))
	def script_volumeMin(self, gesture: InputGesture) -> None:
		"""Set the minimum volume level for the selected audio source."""
		source = self.navigator.getSelectedAudioSource()
		if source is None:
			return
		self.guard.runWithNvdaWarning(source, lambda: announceVolumeLevel(source.volumeMin(), source))

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Mute selected audio source"))
	def script_mute(self, gesture: InputGesture) -> None:
		"""Mute or unmute the selected audio source."""
		source = self.navigator.getSelectedAudioSource()
		if source is None:
			return
		if source.isMuted:
			source.unmute()
			announceVolumeLevel(source.volumeLevel, source)
			return

		def mute() -> None:
			source.mute()
			announceMuted(source)

		self.guard.runWithNvdaWarning(source, mute)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Switch to the next audio source"))
	def script_next(self, gesture: InputGesture) -> None:
		"""Switch to the next audio source (audio device or process)."""
		self.navigator.switchAudioSource(step=1)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Switch to the previous audio source"))
	def script_prev(self, gesture: InputGesture) -> None:
		"""Switch to the previous audio source (audio device or process)."""
		self.navigator.switchAudioSource(step=-1)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Switch to the first audio source of the next category"))
	def script_nextCategory(self, gesture: InputGesture) -> None:
		"""Switch to the first audio source of the next visible category."""
		self.navigator.switchCategory(step=1)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Switch to the first audio source of the previous category"))
	def script_prevCategory(self, gesture: InputGesture) -> None:
		"""Switch to the first audio source of the previous visible category."""
		self.navigator.switchCategory(step=-1)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Show or hide output devices"))
	def script_toggleOutputDevices(self, gesture: InputGesture) -> None:
		"""Show or hide the output devices in the list of audio sources."""
		self.navigator.toggleCategory(SourceKind.OUTPUT_DEVICE)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Show or hide input devices"))
	def script_toggleInputDevices(self, gesture: InputGesture) -> None:
		"""Show or hide the input devices in the list of audio sources."""
		self.navigator.toggleCategory(SourceKind.INPUT_DEVICE)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Show or hide applications playing sound"))
	def script_togglePlaybackApps(self, gesture: InputGesture) -> None:
		"""Show or hide the applications playing sound in the list of audio sources."""
		self.navigator.toggleCategory(SourceKind.PLAYBACK_APP)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Show or hide applications recording sound"))
	def script_toggleRecordingApps(self, gesture: InputGesture) -> None:
		"""Show or hide the applications recording sound in the list of audio sources."""
		self.navigator.toggleCategory(SourceKind.RECORDING_APP)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Show only output devices"))
	def script_showOnlyOutputDevices(self, gesture: InputGesture) -> None:
		"""Show only the output devices in the list of audio sources."""
		self.navigator.showOnlyCategory(SourceKind.OUTPUT_DEVICE)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Show only input devices"))
	def script_showOnlyInputDevices(self, gesture: InputGesture) -> None:
		"""Show only the input devices in the list of audio sources."""
		self.navigator.showOnlyCategory(SourceKind.INPUT_DEVICE)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Show only applications playing sound"))
	def script_showOnlyPlaybackApps(self, gesture: InputGesture) -> None:
		"""Show only the applications playing sound in the list of audio sources."""
		self.navigator.showOnlyCategory(SourceKind.PLAYBACK_APP)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Show only applications recording sound"))
	def script_showOnlyRecordingApps(self, gesture: InputGesture) -> None:
		"""Show only the applications recording sound in the list of audio sources."""
		self.navigator.showOnlyCategory(SourceKind.RECORDING_APP)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Switch NVDA output to the next device"))
	def script_nextOutputDevice(self, gesture: InputGesture) -> None:
		"""Switch NVDA output to the next active output device."""
		self.outputs.selectOutputDeviceByStep(OutputTarget.NVDA, step=1)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Switch NVDA output to the previous device"))
	def script_prevOutputDevice(self, gesture: InputGesture) -> None:
		"""Switch NVDA output to the previous active output device."""
		self.outputs.selectOutputDeviceByStep(OutputTarget.NVDA, step=-1)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Switch NVDA output to the default device"))
	def script_switchNvdaOutputToDefault(self, gesture: InputGesture) -> None:
		"""Switch NVDA output to the default output device of Windows, so NVDA follows its changes."""
		self.outputs.switchNvdaOutputToDefault()

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Set the next device as the default output device"))
	def script_nextDefaultOutputDevice(self, gesture: InputGesture) -> None:
		"""Make the next active output device the default output device of Windows."""
		self.outputs.selectOutputDeviceByStep(OutputTarget.DEFAULT, step=1)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Set the previous device as the default output device"))
	def script_prevDefaultOutputDevice(self, gesture: InputGesture) -> None:
		"""Make the previous active output device the default output device of Windows."""
		self.outputs.selectOutputDeviceByStep(OutputTarget.DEFAULT, step=-1)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Set the next device as the default communication device"))
	def script_nextCommunicationDevice(self, gesture: InputGesture) -> None:
		"""Make the next active output device the default communication device of Windows."""
		self.outputs.selectOutputDeviceByStep(OutputTarget.COMMUNICATION, step=1)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Set the previous device as the default communication device"))
	def script_prevCommunicationDevice(self, gesture: InputGesture) -> None:
		"""Make the previous active output device the default communication device of Windows."""
		self.outputs.selectOutputDeviceByStep(OutputTarget.COMMUNICATION, step=-1)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Mute or unmute the microphones selected for the quick mute"))
	def script_toggleQuickMute(self, gesture: InputGesture) -> None:
		"""Mute all microphones selected in the add-on settings if any of them is on, otherwise unmute them all.
		Only a sound is played: after muting and before unmuting, so the microphones do not record it.
		"""
		self.quickMute.toggle()

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Open the Sound dialog of Windows"))
	def script_openSoundDialog(self, gesture: InputGesture) -> None:
		"""Open the classic Sound dialog of the Windows Control Panel (mmsys.cpl),
		which lists all playback and recording devices with their properties.
		If it is missing (e.g. removed in a future or customized Windows), the Sound page of the Windows Settings is opened.
		"""
		devices.openSoundDialog()

	def outputDeviceScriptFactory(
		self,
		target: OutputTarget,
		id: str,
		name: str,
		description: str,
	) -> Callable[[GlobalPlugin, InputGesture], None]:
		"""Create the script that switches to the specified output device.

		:param target: NVDA output or a default device of Windows
		:param id: the device ID
		:param name: the name of the device
		:param description: the name of the script in the NVDA input gestures dialog
		:return: the script
		"""

		def script_selectOutputDevice(self: GlobalPlugin, gesture: InputGesture) -> None:
			"""Switch to the output device of the script."""
			self.outputs.selectOutputDeviceById(target, id, name)

		return script(description=description)(script_selectOutputDevice)

	def bindSwitchingMethods(self) -> None:
		"""Create the scripts that switch NVDA output and the default devices of Windows to each output device
		found when NVDA is started, and bind the first 12 of them to F1-F12 with the modifiers of each target
		if the default gestures are enabled. Devices connected later are available after NVDA is restarted.
		Should be called in the class constructor.
		"""
		# The scripts of the devices found the previous time the plugin was created, e.g. before the add-ons were reloaded
		for scriptName in [name for name in vars(self.__class__) if name.startswith("script_")]:
			if scriptName[len("script_") :].rstrip("0123456789") in OUTPUT_DEVICE_SCRIPTS:
				delattr(self.__class__, scriptName)
		# Translators: The name of the method that displayed in the NVDA input gestures dialog,
		# {number} is the number of the output device in the order of Windows, e.g. 1 for F1, {name} is its name
		nvdaDescription = _("Switch NVDA output to the device {number} ({name})")
		# Translators: The name of the method that displayed in the NVDA input gestures dialog,
		# {number} is the number of the output device in the order of Windows, e.g. 1 for F1, {name} is its name
		defaultDescription = _("Set the device {number} ({name}) as the default output device")
		# Translators: The name of the method that displayed in the NVDA input gestures dialog,
		# {number} is the number of the output device in the order of Windows, e.g. 1 for F1, {name} is its name
		communicationDescription = _("Set the device {number} ({name}) as the default communication device")
		targets = (
			(OutputTarget.NVDA, "", nvdaDescription),
			(OutputTarget.DEFAULT, "shift+", defaultDescription),
			(OutputTarget.COMMUNICATION, "control+", communicationDescription),
		)
		outputDevices = devices.getOutputDevices()
		for scriptPrefix, (target, modifiers, description) in zip(OUTPUT_DEVICE_SCRIPTS, targets):
			for number, (id, name) in enumerate(outputDevices, 1):
				scriptName = f"{scriptPrefix}{number}"
				setattr(
					self.__class__,
					f"script_{scriptName}",
					self.outputDeviceScriptFactory(
						target,
						id,
						name,
						description.format(number=number, name=name),
					),
				)
				if getAddonConfig()["gestures"] and number <= FUNCTION_KEYS:
					# ScriptableObject.bindGesture of NVDA has no type annotations
					self.bindGesture(  # pyright: ignore[reportUnknownMemberType]
						f"kb:NVDA+windows+{modifiers}f{number}",
						scriptName,
					)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Select next channel"))
	def script_nextChannel(self, gesture: InputGesture) -> None:
		"""Select the next channel of the current audio source."""
		source = self.navigator.getChannelSource()
		if source is None:
			return
		source.channel += 1
		announceChannel(source.channel)
		if getAddonConfig()["status"]:
			announceMuted(source) if source.isMuted else announceVolumeLevel(
				source.getChannelVolumeLevel(),
				source,
				source.channel,
			)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Select previous channel"))
	def script_prevChannel(self, gesture: InputGesture) -> None:
		"""Select the previous channel of the current audio source."""
		source = self.navigator.getChannelSource()
		if source is None:
			return
		source.channel -= 1
		announceChannel(source.channel)
		if getAddonConfig()["status"]:
			announceMuted(source) if source.isMuted else announceVolumeLevel(
				source.getChannelVolumeLevel(),
				source,
				source.channel,
			)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Increase the volume of the selected channel"))
	def script_channelVolumeUp(self, gesture: InputGesture) -> None:
		"""Increase the volume level of the selected audio channel."""
		source = self.navigator.getChannelSource()
		if source is None:
			return
		level: float = source.channelVolumeUp()
		if level < 0:
			announceNotSupported()
			return
		announceVolumeLevel(level, source, source.channel)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Decrease the volume of the selected channel"))
	def script_channelVolumeDown(self, gesture: InputGesture) -> None:
		"""Decrease the volume level of the selected audio channel."""
		source = self.navigator.getChannelSource()
		if source is None:
			return
		# Lowering a channel of NVDA itself may silence its speech, so the user is warned first
		self.guard.runWithNvdaWarning(
			source,
			lambda: announceChannelVolumeLevel(source, source.channelVolumeDown()),
		)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Set the maximum volume level for the selected channel"))
	def script_channelVolumeMax(self, gesture: InputGesture) -> None:
		"""Set the maximum volume level for the selected audio channel."""
		source = self.navigator.getChannelSource()
		if source is None:
			return
		level: float = source.channelVolumeMax()
		if level < 0:
			announceNotSupported()
			return
		announceVolumeLevel(level, source, source.channel)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Set the minimum volume level for the selected channel"))
	def script_channelVolumeMin(self, gesture: InputGesture) -> None:
		"""Set the minimum volume level for the selected audio channel."""
		source = self.navigator.getChannelSource()
		if source is None:
			return
		# Lowering a channel of NVDA itself may silence its speech, so the user is warned first
		self.guard.runWithNvdaWarning(
			source,
			lambda: announceChannelVolumeLevel(source, source.channelVolumeMin()),
		)

	# Translators: The name of the method that displayed in the NVDA input gestures dialog
	@script(description=_("Set the average volume level for all channels"))
	def script_channelVolumeAverage(self, gesture: InputGesture) -> None:
		"""Set the average volume level for all audio channels."""
		source = self.navigator.getChannelSource()
		if source is None:
			return
		# The average lowers the louder channels, which may silence NVDA speech on one side
		levels = [source.getChannelVolumeLevel(channel) for channel in range(source.channelCount)]
		if max(levels) - min(levels) > LEVEL_TOLERANCE / 100.0:
			self.guard.runWithNvdaWarning(
				source,
				lambda: announceChannelVolumeLevel(source, source.channelVolumeAverage()),
			)
		else:
			announceChannelVolumeLevel(source, source.channelVolumeAverage())

	__defaultGestures = {
		# Volume level
		"kb:NVDA+windows+upArrow": "volumeUp",
		"kb:NVDA+windows+downArrow": "volumeDown",
		"kb:NVDA+windows+home": "volumeMax",
		"kb:NVDA+windows+end": "volumeMin",
		"kb:NVDA+windows+escape": "mute",
		# Switching between audio sources
		"kb:NVDA+windows+rightArrow": "next",
		"kb:NVDA+windows+leftArrow": "prev",
		"kb:NVDA+windows+control+rightArrow": "nextCategory",
		"kb:NVDA+windows+control+leftArrow": "prevCategory",
		# Categories of audio sources
		"kb:NVDA+windows+o": "toggleOutputDevices",
		"kb:NVDA+windows+i": "toggleInputDevices",
		"kb:NVDA+windows+p": "togglePlaybackApps",
		"kb:NVDA+windows+r": "toggleRecordingApps",
		"kb:NVDA+windows+shift+o": "showOnlyOutputDevices",
		"kb:NVDA+windows+shift+i": "showOnlyInputDevices",
		"kb:NVDA+windows+shift+p": "showOnlyPlaybackApps",
		"kb:NVDA+windows+shift+r": "showOnlyRecordingApps",
		# Output audio devices
		"kb:NVDA+windows+pageUp": "nextOutputDevice",
		"kb:NVDA+windows+pageDown": "prevOutputDevice",
		"kb:NVDA+windows+d": "switchNvdaOutputToDefault",
		"kb:NVDA+windows+s": "openSoundDialog",
		"kb:NVDA+windows+shift+pageUp": "nextDefaultOutputDevice",
		"kb:NVDA+windows+shift+pageDown": "prevDefaultOutputDevice",
		"kb:NVDA+windows+control+pageUp": "nextCommunicationDevice",
		"kb:NVDA+windows+control+pageDown": "prevCommunicationDevice",
		# Microphones
		"kb:NVDA+windows+space": "toggleQuickMute",
		# Customize channels volume
		"kb:NVDA+windows+shift+rightArrow": "nextChannel",
		"kb:NVDA+windows+shift+leftArrow": "prevChannel",
		"kb:NVDA+windows+shift+upArrow": "channelVolumeUp",
		"kb:NVDA+windows+shift+downArrow": "channelVolumeDown",
		"kb:NVDA+windows+shift+home": "channelVolumeMax",
		"kb:NVDA+windows+shift+end": "channelVolumeMin",
		"kb:NVDA+windows+shift+escape": "channelVolumeAverage",
	}
