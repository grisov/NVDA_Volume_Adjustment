# messages.py
# The messages announced to the user and the names shown in the add-on settings
# A part of the NVDA Volume Adjustment add-on
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.
# Copyright (C) 2020-2026 Oleksandr Gryshchenko <grisov.nvaccess@mailgw.com>

from __future__ import annotations

from collections.abc import Callable

import addonHandler
import ui
from logHandler import log

from .configuration import cfg, getAddonConfig
from .model import Connection, FormFactor, SourceKind
from .sources import AppSource, AudioSource, DeviceSource, OutputDeviceSource

try:
	addonHandler.initTranslation()
except addonHandler.AddonError:
	log.warning("Unable to init translations. This may be because the addon is running from NVDA scratchpad.")
_: Callable[[str], str]
ngettext: Callable[[str, str, int], str]


def getCategoryName(kind: SourceKind) -> str:
	"""Get the name of the category of audio sources to announce.

	:param kind: the category of audio sources
	:return: the translated name of the category
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


def getDeviceDetails(device: DeviceSource) -> list[str]:
	"""Get the attributes of the audio device to announce after its name or volume level:
	its type, how it is connected and whether it is a default device of Windows.
	The internal connection is not announced: it would be misleading e.g. for the speakers of a monitor.

	:param device: the audio device
	:return: the translated attributes, those that are not known are skipped
	"""
	formFactors = {
		# Translators: The type of an audio device announced after its name
		FormFactor.REMOTE_NETWORK_DEVICE: _("network device"),
		# Translators: The type of an audio device announced after its name
		FormFactor.SPEAKERS: _("speakers"),
		# Translators: The type of an audio device announced after its name, e.g. a line input or output
		FormFactor.LINE_LEVEL: _("line"),
		# Translators: The type of an audio device announced after its name
		FormFactor.HEADPHONES: _("headphones"),
		# Translators: The type of an audio device announced after its name
		FormFactor.MICROPHONE: _("microphone"),
		# Translators: The type of an audio device announced after its name: headphones with a microphone
		FormFactor.HEADSET: _("headset"),
		# Translators: The type of an audio device announced after its name: a telephone handset
		FormFactor.HANDSET: _("handset"),
		# Translators: The type of an audio device announced after its name: a digital audio output
		FormFactor.UNKNOWN_DIGITAL_PASSTHROUGH: _("digital output"),
		# Translators: The type of an audio device announced after its name: the S/PDIF digital interface
		FormFactor.SPDIF: _("S/PDIF"),
		# Translators: The type of an audio device announced after its name: the speakers of a monitor or TV (HDMI)
		FormFactor.DIGITAL_AUDIO_DISPLAY_DEVICE: _("digital display"),
	}
	connections = {
		# Translators: How an audio device is connected, announced after its name
		Connection.USB: _("USB"),
		# Translators: How an audio device is connected, announced after its name
		Connection.BLUETOOTH: _("Bluetooth"),
		# Translators: How an audio device is connected: a software device, e.g. a virtual audio cable
		Connection.VIRTUAL: _("virtual"),
	}
	details = [formFactors.get(device.formFactor, ""), connections.get(device.connection, "")]
	if device.isDefaultDevice:
		# Translators: Announced after the name of an audio device that is the default device of Windows
		details.append(_("default"))
	if device.isDefaultCommunicationDevice:
		# Translators: Announced after the name of an audio device that is the default communication device of Windows
		details.append(_("communication"))
	return [detail for detail in details if detail]


def getOnlyVisibleCategoryMessage(category: str, hiding: bool = False) -> str:
	"""Get the message that the category is already the only visible one,
	when it is shown as the only category or the user tries to hide it.

	:param category: the name of the category
	:param hiding: whether the user tries to hide the category
	:return: the message to announce
	"""
	# Translators: {category} is the name of the only visible category, e.g. "Recording apps"
	message = _("{category} is already the only visible category").format(category=category)
	if not hiding:
		return message
	# Translators: The message when the user tries to hide the only visible category of audio sources
	prefix = _("Category cannot be hidden.")
	return f"{prefix} {message}"


def formatLevel(
	volumeLevel: float,
	source: AudioSource | None = None,
	channel: int | None = None,
) -> str:
	"""Get the volume level with its unit, e.g. "29%", "29" or "-12.5 dB".
	Decibels are given if they are selected in the add-on settings and the source provides them,
	otherwise percents. The volume is always adjusted in percents, like the volume slider of Windows.

	:param volumeLevel: value of volume level (from 0.0 to 1.0)
	:param source: the audio source of the level, None to give percents
	:param channel: the number of the channel of the level, None for the master volume level
	:return: the level, also shown alone on a braille display
	"""
	if source is not None and getAddonConfig()["units"] == "decibels":
		decibels = source.getVolumeDecibels(channel)
		if decibels is not None:
			# Translators: The unit of the volume level in decibels, announced after the number, e.g. "Volume -12.5 dB"
			unit = _("dB")
			# Adding 0.0 turns -0.0 (e.g. rounded -0.04 dB) into 0.0, so no minus sign is announced
			return f"{round(decibels, 1) + 0.0:.1f} {unit}"
	# Rounded: Windows stores volume levels as 32-bit floats, 29 % is read back as 28.999999 %
	level = round(volumeLevel * 100.0)
	if getAddonConfig()["units"] == "number":
		# The short form of the earlier versions, e.g. "Volume 29"
		return str(level)
	return f"{level}%"


def formatVolumeLevel(
	volumeLevel: float,
	source: AudioSource | None = None,
	channel: int | None = None,
) -> str:
	"""Get the text of the volume level announcement, e.g. "Volume 29%", "Volume 29" or "Volume -12.5 dB".

	:param volumeLevel: value of volume level (from 0.0 to 1.0)
	:param source: the audio source of the level, None to announce percents
	:param channel: the number of the channel of the level, None for the master volume level
	:return: the text to announce
	"""
	# Translators: The message is announced during volume control
	volume = _("Volume")
	return f"{volume} {formatLevel(volumeLevel, source, channel)}"


def announceVolumeLevel(
	volumeLevel: float,
	source: AudioSource | None = None,
	channel: int | None = None,
) -> None:
	"""Announce the current volume level, a braille display shows only the level, e.g. "29%".

	:param volumeLevel: value of volume level (from 0.0 to 1.0)
	:param source: the audio source of the level, for the announcement in decibels
	:param channel: the number of the channel of the level, None for the master volume level
	"""
	message = formatVolumeLevel(volumeLevel, source, channel)
	ui.message(message, brailleText=formatLevel(volumeLevel, source, channel))


def formatMuted(source: AudioSource) -> tuple[str, str]:
	"""Get the text of the announcement that the sound is muted and its short form for a braille display.
	In the "Volume Down" mute mode the remaining volume level is given as well,
	e.g. "The sound is muted, Volume 5%" and "muted 5%".

	:param source: the muted audio source
	:return: the text to announce and the text to show on a braille display
	"""
	# Translators: The message is announced during volume control
	message: str = _("The sound is muted")
	# Translators: The short braille message when the sound is muted, e.g. "muted 5%"
	brailleText: str = _("muted")
	volume = source.volume
	# The level is announced only when the add-on decreased it: a source muted by Windows or another program is silent
	if (
		not getAddonConfig()["muteCompletely"]
		and source.mutedKey in cfg.muted
		and not (volume is not None and volume.GetMute())
	):
		message = f"{message}, {formatVolumeLevel(source.volumeLevel, source)}"
		brailleText = f"{brailleText} {formatLevel(source.volumeLevel, source)}"
	return message, brailleText


def announceMuted(source: AudioSource) -> None:
	"""Announce that the sound was muted.

	:param source: the muted audio source
	"""
	message, brailleText = formatMuted(source)
	ui.message(message, brailleText=brailleText)


def announceSelection(
	source: AudioSource,
	title: str,
	brailleTitle: str,
	channel: int | None = None,
	details: list[str] | None = None,
) -> None:
	"""Announce the selected audio source or channel with its volume level in one message,
	so a braille display shows them together. The level follows if it is enabled in the add-on settings.
	A braille display usually has few cells, so it shows only the name and the level, e.g.
	"Output devices, USB headphones, Volume 30%, USB" is spoken and "USB headphones: 30%" is shown.

	:param source: the selected audio source
	:param title: the spoken name of the source or the channel
	:param brailleTitle: the short name for a braille display
	:param channel: the number of the selected channel, None for the master volume level
	:param details: the spoken attributes of an audio device, they follow its volume level
	"""
	message, brailleText = title, brailleTitle
	if getAddonConfig()["status"]:
		if source.isMuted:
			status, brailleStatus = formatMuted(source)
		else:
			level = source.volumeLevel if channel is None else source.getChannelVolumeLevel(channel)
			status, brailleStatus = (
				formatVolumeLevel(level, source, channel),
				formatLevel(level, source, channel),
			)
		message = f"{message}, {status}"
		brailleText = f"{brailleText}: {brailleStatus}"
	ui.message(", ".join([message, *(details or [])]), brailleText=brailleText)


def announceChannelVolumeLevel(source: AudioSource, level: float) -> None:
	"""Announce the volume level of the selected channel after it has been changed.

	:param source: the audio source of the channel
	:param level: the new level of the channel, negative if the channels are not supported
	"""
	if level < 0:
		announceNotSupported()
		return
	announceVolumeLevel(level, source, source.channel)


def announceChannel(source: AudioSource) -> None:
	"""Announce the number of the selected audio channel, counted from 1 for the user, with its volume level.

	:param source: the audio source of the selected channel
	"""
	# Translators: Message about the number of the selected audio channel
	title = _("Channel %d") % (source.channel + 1)
	announceSelection(source, title, title, source.channel)


def announceNotPlaying(app: str, kind: SourceKind = SourceKind.PLAYBACK_APP) -> None:
	"""Announce that the application does not play or record any sound, so its volume cannot be adjusted.

	:param app: the name of the application
	:param kind: playback or recording applications
	"""
	if kind == SourceKind.RECORDING_APP:
		# Translators: The message when the selected recording application does not record any sound
		ui.message(_("{app} is not recording any sound.").format(app=app))
		return
	# Translators: The message when the selected application does not play any sound
	ui.message(_("{app} is not playing any sound.").format(app=app))


def announceNotSupported() -> None:
	"""Announce that the feature currently is not supported."""
	# Translators: The message when feature currently is not supported
	ui.message(_("Not supported"))


def getSourceTitle(source: AudioSource) -> str:
	"""Get the name of the audio source to announce.

	:param source: the audio source
	:return: human friendly name of the audio source
	"""
	if isinstance(source, OutputDeviceSource) and source.isDefaultDevice:
		# Translators: Used as the prefix to default audio device name
		return "{default}: {title}".format(default=_("Default audio device"), title=source.name)
	return getSourceName(source)


def getSourceName(source: AudioSource) -> str:
	"""Get the short name of the audio source, without the prefix of the default device, for a braille display.

	:param source: the audio source
	:return: human friendly name of the audio source
	"""
	return source.title if isinstance(source, AppSource) else source.name


def getAnnouncedDeviceDetails(source: AudioSource | None) -> list[str]:
	"""Get the attributes of an audio device to announce, if this is enabled in the add-on settings.

	:param source: the audio source, details are given only for audio devices
	:return: the translated attributes, empty for applications or when the option is disabled
	"""
	if not getAddonConfig()["deviceDetails"] or not isinstance(source, DeviceSource):
		return []
	return getDeviceDetails(source)


def announceCategoryShown(category: str, count: int) -> None:
	"""Announce that a category of audio sources has been shown.

	:param category: the name of the category
	:param count: the number of its audio sources now
	"""
	# Translators: A category of audio sources is shown, {count} is the number of its sources
	message = ngettext("{category} shown, {count} source", "{category} shown, {count} sources", count)
	ui.message(message.format(category=category, count=count))


def announceCategoryHidden(category: str) -> None:
	"""Announce that a category of audio sources has been hidden.

	:param category: the name of the category
	"""
	# Translators: A category of audio sources is hidden, {category} is its name, e.g. "Recording apps"
	ui.message(_("{category} hidden").format(category=category))


def announceOnlyCategory(category: str, count: int) -> None:
	"""Announce that only one category of audio sources is shown.

	:param category: the name of the category
	:param count: the number of its audio sources now
	"""
	# Translators: Only one category of audio sources is shown, {count} is the number of its sources
	message = ngettext("{category} only, {count} source", "{category} only, {count} sources", count)
	ui.message(message.format(category=category, count=count))


def announceChannelsUsedBySoundSplit() -> None:
	"""Announce that the channels of an application cannot be adjusted while NVDA sound split is enabled."""
	# Translators: The channels of an application cannot be adjusted while NVDA sound split is on
	ui.message(_("Channels are used by NVDA sound split"))


def announceUnableToSetDefaultDevice() -> None:
	"""Announce that Windows has not allowed to change its default audio device."""
	# Translators: The message when Windows does not allow to change its default audio device
	ui.message(_("Unable to set the default device"))


def announceDeviceNotAvailable(name: str) -> None:
	"""Announce that an audio device is not available anymore, e.g. a device found when NVDA was started
	or selected in the list of audio sources.

	:param name: the name of the device
	"""
	# Translators: The audio device {name} has been disconnected or disabled
	ui.message(_("{name} is not available").format(name=name))


def announceNoQuickMuteMicrophones() -> None:
	"""Announce that no microphones have been selected for the quick mute."""
	# Translators: The message when no microphones have been selected for the quick mute in the add-on settings
	ui.message(_("No microphones are selected for the quick mute"))


def announceQuickMuteMicrophonesNotConnected() -> None:
	"""Announce that none of the microphones selected for the quick mute is connected."""
	# Translators: The message when none of the microphones selected for the quick mute is connected
	ui.message(_("The microphones selected for the quick mute are not connected"))
