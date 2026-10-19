# navigation.py
# Switching between audio sources and categories, the application in focus and the selected source
# A part of the NVDA Volume Adjustment add-on
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.
# Copyright (C) 2020-2026 Oleksandr Gryshchenko <grisov.nvaccess@mailgw.com>

from __future__ import annotations
import ui
from api import getFocusObject
from .configuration import cfg, getAddonConfig, getNvdaConfig
from .messages import (
	announceCategoryHidden,
	announceCategoryShown,
	announceChannelsUsedBySoundSplit,
	announceNotPlaying,
	announceNotSupported,
	announceOnlyCategory,
	formatMuted,
	formatVolumeLevel,
	getAnnouncedDeviceDetails,
	getCategoryName,
	getOnlyVisibleCategoryMessage,
	getSourceTitle,
)
from .registry import registry
from .model import SourceKey, SourceKind
from .sources import AppSource, AudioSource, getSourceKey, getVisibleCategories, setVisibleCategories

UNDEFINED_APP: str = "UndefinedCurrentApplicationName"


class SourceNavigator:
	"""The audio source adjusted by the volume commands: the application in focus or the source selected with arrows,
	and the switching between the audio sources and their categories.
	"""

	def __init__(self) -> None:
		"""No audio source is selected: the application in focus is adjusted."""
		super().__init__()
		# Audio source selected with arrows: its category and ID, None to adjust the application in focus
		self._selected: SourceKey | None = None
		# The audio source whose name was announced last, so it is not repeated on every keypress
		self._previous: SourceKey | None = None
		# Application of the selected or focused process, reused between keypresses
		self._session: AppSource | None = None

	def onFocusChanged(self) -> None:
		"""Follow the application in focus: the selection with arrows is dropped."""
		self._selected = None
		# The name of the application in focus is announced on the next keypress
		self._previous = None
		# The application in focus may have changed, so its audio session is looked up again
		self._session = None

	def getFocusedProcess(self) -> tuple[str, int]:
		"""Get the application name and the process ID of the object in system focus.

		:return: the application name and the process ID, 0 if it is unknown
		"""
		obj = getFocusObject()
		try:
			appName = obj.appModule.appName
		except AttributeError:
			appName = UNDEFINED_APP
		return appName, getattr(obj, "processID", 0)

	def selectProcessInFocus(self) -> bool:
		"""Select the application that is in system focus.
		The application found after the last focus change is reused by subsequent keypresses
		until it becomes outdated (see AudioSourceRegistry.isOutdated()).

		:return: whether the application in focus plays any sound
		"""
		if self._session is None or registry.isOutdated(self._session):
			appName, processId = self.getFocusedProcess()
			# The session of the focused process itself is preferred, then the one found by the app name
			session = registry.findApp(appName, processId)
			if session is None:
				announceNotPlaying(appName)
				return False
			self._session = session
		return True

	def getSession(self, kind: SourceKind, name: str) -> AppSource | None:
		"""Get the application of the specified process in the specified category.
		The previously found application is reused while the same process stays selected,
		so repeated keypresses do not enumerate all audio sessions again.
		An outdated application (e.g. the process was restarted or the devices changed) is looked up again.

		:param kind: playback or recording applications
		:param name: the name of the running process
		:return: the application of the specified process, None if it has no audio session
		"""
		if (
			self._session is None
			or getSourceKey(self._session) != (kind, name)
			or registry.isOutdated(self._session)
		):
			self._session = registry.findApp(name, kind=kind)
		return self._session

	def getChannelSource(self) -> AudioSource | None:
		"""Get the selected audio source for a channel command.
		The channels of applications are changed by NVDA sound split too, so they are not changed while
		sound split is enabled: the add-on and NVDA would overwrite each other's levels.
		Announces why the channels cannot be adjusted.

		:return: the audio source whose channels can be adjusted, None otherwise
		"""
		source = self.getSelectedAudioSource()
		if source is None:
			return None
		# Any state except "disabled" (0) applies sound split levels to all audio sessions, even "both channels"
		if isinstance(source, AppSource) and getNvdaConfig("audio")["soundSplitState"] != 0:
			announceChannelsUsedBySoundSplit()
			return None
		if source.channelCount <= 0:
			announceNotSupported()
			return None
		return source

	def getAllSources(self) -> list[AudioSource]:
		"""List of all audio sources available for switching, in the order of the categories:
		output devices, input devices, playback applications, recording applications.
		Hidden categories, devices and processes are skipped.
		Each process name is listed once per category: all its audio sessions are adjusted together.

		:return: the audio sources, the list changes dynamically
		"""
		sources: list[AudioSource] = []
		for kind in getVisibleCategories():
			sources.extend(self.getSources(kind))
		return sources

	def getSources(self, kind: SourceKind) -> list[AudioSource]:
		"""List of the audio sources of one category, hidden devices and processes are skipped.

		:param kind: the category of audio sources
		:return: the audio sources of the category
		"""
		if kind == SourceKind.PLAYBACK_APP:
			return [*registry.getApps(cfg.processes)]
		if kind == SourceKind.RECORDING_APP:
			return [*registry.getRecordingApps(cfg.processes)]
		return [device for device in registry.devices if device.kind == kind]

	def toggleCategory(self, kind: SourceKind) -> None:
		"""Show or hide the category of audio sources and announce the result.
		The last visible category cannot be hidden.

		:param kind: the category of audio sources
		"""
		visible = getVisibleCategories()
		category = getCategoryName(kind)
		if kind not in visible:
			setVisibleCategories([*visible, kind])
			count = len(self.getSources(kind))
			announceCategoryShown(category, count)
		elif visible == [kind]:
			ui.message(getOnlyVisibleCategoryMessage(category, hiding=True))
		else:
			setVisibleCategories([visibleKind for visibleKind in visible if visibleKind != kind])
			announceCategoryHidden(category)

	def showOnlyCategory(self, kind: SourceKind) -> None:
		"""Show only the specified category of audio sources and announce the result.

		:param kind: the category of audio sources
		"""
		category = getCategoryName(kind)
		if getVisibleCategories() == [kind]:
			ui.message(getOnlyVisibleCategoryMessage(category))
			return
		setVisibleCategories([kind])
		count = len(self.getSources(kind))
		announceOnlyCategory(category, count)

	def unmuteAllAudioSources(self) -> None:
		"""Unmute all muted audio devices and audio sessions."""
		for device in registry.devices:
			if device.isMuted:
				device.unmute()
		# Hidden processes are unmuted too: they may have been muted before they were hidden
		for app in [*registry.getApps(), *registry.getRecordingApps()]:
			if app.isMuted:
				app.unmute()

	def getCurrentSourceKey(self, sources: list[AudioSource]) -> SourceKey | None:
		"""Get the key of the audio source that switching starts from.

		:param sources: the audio sources available for switching, not empty
		:return: the selected source, the application in focus or the first source,
			None if the application in focus does not play any sound
		"""
		if self._selected is not None:
			return self._selected
		if getAddonConfig()["focus"]:
			focused = registry.findApp(*self.getFocusedProcess())
			return getSourceKey(focused) if focused is not None else None
		# Without focus tracking the first source is adjusted until another one is selected
		return getSourceKey(sources[0])

	def selectSource(self, source: AudioSource, announceCategory: bool) -> None:
		"""Select the audio source for the volume commands and announce it.

		:param source: the audio source to select
		:param announceCategory: whether the name of its category is announced before its name
		"""
		self._selected = self._previous = getSourceKey(source)
		if isinstance(source, AppSource):
			self._session = source
		title = getSourceTitle(source)
		if announceCategory:
			title = f"{getCategoryName(source.kind)}, {title}"
		details = getAnnouncedDeviceDetails(source)
		if not getAddonConfig()["status"]:
			ui.message(", ".join([title, *details]))
			return
		ui.message(title)
		# The details of an audio device follow its volume level
		status = formatMuted(source) if source.isMuted else formatVolumeLevel(source.volumeLevel, source)
		ui.message(", ".join([status, *details]))

	def switchAudioSource(self, step: int) -> None:
		"""Select the next or previous audio source in the list and announce it.
		Starting from the application in focus, the neighbouring source is selected.

		:param step: offset in the list of audio sources (usually 1 or -1)
		"""
		sources = self.getAllSources()
		if not sources:
			return
		keys = [getSourceKey(source) for source in sources]
		current = self.getCurrentSourceKey(sources)
		if current in keys:
			position = keys.index(current)
		elif step > 0:
			# Unknown position: the next source is the first application, the previous one is the last source
			position = len([source for source in sources if not isinstance(source, AppSource)]) - 1
		else:
			position = 0
		source = sources[(position + step) % len(sources)]
		# The category is announced when it changes, or when the previous source is not known
		self.selectSource(
			source,
			announceCategory=getAddonConfig()["announceCategories"]
			and (current is None or current[0] != source.kind),
		)

	def switchCategory(self, step: int) -> None:
		"""Select the first audio source of the next or previous visible category and announce it
		with the name of the category. Categories without audio sources are skipped.
		With only one such category, its first source is selected.

		:param step: direction in the list of categories (1 or -1)
		"""
		sources = self.getAllSources()
		if not sources:
			return
		current = self.getCurrentSourceKey(sources)
		order = list(SourceKind)
		# The position of the current category, or just before the first/after the last one if it is unknown
		position = order.index(current[0]) if current is not None else (-1 if step > 0 else len(order))
		for offset in range(1, len(order) + 1):
			kind = order[(position + step * offset) % len(order)]
			source = next((source for source in sources if source.kind == kind), None)
			if source is not None:
				# The name of the category is always announced: it is the purpose of the command
				self.selectSource(source, announceCategory=True)
				return

	def announceTitleOnce(self, source: AudioSource) -> AudioSource:
		"""Announce the name of the application when a volume command uses it for the first time.

		:param source: the audio source to adjust
		:return: the same audio source
		"""
		key = getSourceKey(source)
		if key != self._previous:
			ui.message(getSourceTitle(source))
			self._previous = key
		return source

	def getAudioSource(self) -> AudioSource | None:
		"""Get the object of the audio source selected with arrows (device or application),
		this can be instance inherited from the sources.AudioSource class.
		Also announces the name of the application at the first treatment.

		:return: instance of selected audio source, None if the selected application has no audio session
		"""
		if self._selected is None:
			return None
		kind, id = self._selected
		if kind in (SourceKind.OUTPUT_DEVICE, SourceKind.INPUT_DEVICE):
			devices = registry.devices
			device = next((device for device in devices if device.id == id), None)
			if device is None:
				# The selected device has been removed or hidden: the default output device is adjusted instead
				if not devices:
					return None
				device = devices[0]
				self._selected = getSourceKey(device)
				ui.message(getSourceTitle(device))
			# The name of the application is announced again when it is selected after a device
			self._previous = self._selected
			return device
		app = self.getSession(kind, id)
		if app is None:
			announceNotPlaying(id.replace(".exe", ""), kind)
			return None
		return self.announceTitleOnce(app)

	def getSelectedAudioSource(self) -> AudioSource | None:
		"""Get the audio source to adjust: the application in focus or the source selected in the list.
		Announces if the selected application does not play any sound.

		:return: the selected audio source, None if there is nothing to adjust
		"""
		if self._selected is not None and self._selected[0] not in getVisibleCategories():
			# The category of the selected source has been hidden with a gesture or in the add-on settings:
			# the application in focus or the first source is adjusted instead
			self._selected = self._previous = None
			self._session = None
		if self._selected is None:
			if getAddonConfig()["focus"]:
				session = self._session if self.selectProcessInFocus() else None
				if session is None:
					return None
				return self.announceTitleOnce(session)
			# Without focus tracking the first source in the list is adjusted until another one is selected
			sources = self.getAllSources()
			if not sources:
				return None
			self._selected = getSourceKey(sources[0])
		return self.getAudioSource()
