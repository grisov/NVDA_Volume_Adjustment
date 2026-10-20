# registry.py
# The registry of the audio sources and the notifications of Windows about audio devices and sessions
# A part of the NVDA Volume Adjustment add-on
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.
# Copyright (C) 2020-2026 Oleksandr Gryshchenko <grisov.nvaccess@mailgw.com>

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, NamedTuple, override

from comtypes import COMError
from pycaw.callbacks import AudioSessionNotification, MMNotificationClient
from pycaw.constants import DEVICE_STATE
from pycaw.utils import EDataFlow, ERole

from .audiocore import (
	getDeviceEnumerator,
	getSessionManager,
	listSessions,
	logDebugWarning,
)
from .audiotypes import DeviceEnumerator, Session, SessionManager
from .devices import getDefaultDeviceIds
from .model import SourceKind
from .sources import (
	AppSource,
	DeviceSource,
	InputDeviceSource,
	OutputDeviceSource,
	PlaybackAppSource,
	RecordingAppSource,
	createDevice,
)


class DeviceNotifications(MMNotificationClient):
	"""Marks the registry outdated when audio devices are added, removed, enabled, disabled
	or the default device is changed.
	Windows calls these methods in its own threads, so they only set flags:
	the lists are rebuilt in the main thread of NVDA when they are used next time.
	"""

	def __init__(self, registry: AudioSourceRegistry) -> None:
		"""Notification handler of the specified registry.

		:param registry: the registry to mark outdated
		"""
		super().__init__()
		self._registry = registry

	@override
	def on_default_device_changed(
		self,
		flow: str,
		flow_id: int,
		role: str,
		role_id: int,
		default_device_id: str,
	) -> None:
		"""The default device for a role has changed."""
		self._registry.markDevicesChanged()

	@override
	def on_device_added(self, added_device_id: str) -> None:
		"""A new audio device has been added."""
		self._registry.markDevicesChanged()

	@override
	def on_device_removed(self, removed_device_id: str) -> None:
		"""An audio device has been removed."""
		self._registry.markDevicesChanged()

	@override
	def on_device_state_changed(self, device_id: str, new_state: str, new_state_id: int) -> None:
		"""An audio device has been enabled, disabled, plugged in or unplugged."""
		self._registry.markDevicesChanged()


class SessionNotifications(AudioSessionNotification):
	"""Marks the applications outdated when a new audio session is created on an audio device.
	Windows calls this method in its own thread, so it only sets a flag.
	"""

	def __init__(self, registry: AudioSourceRegistry) -> None:
		"""Notification handler of the specified registry.

		:param registry: the registry to mark outdated
		"""
		super().__init__()
		self._registry = registry

	@override
	def on_session_created(self, new_session: Any) -> None:
		"""A new audio session has been created, it may belong to an already found application."""
		self._registry.markAppsChanged()


class SessionManagerEntry(NamedTuple):
	"""Session manager of an active audio device and the subscription to its new audio sessions."""

	flow: EDataFlow
	deviceId: str
	manager: SessionManager
	# None if the subscription has failed: the sessions are still listed
	notifications: SessionNotifications | None


class AudioSourceRegistry:
	"""All audio sources whose volume can be adjusted.
	The list of audio devices is kept until it is rescanned, while applications are looked up on demand:
	their audio sessions appear and disappear all the time, and looking them up takes a few milliseconds.
	"""

	def __init__(self) -> None:
		"""Initially no audio devices are known, they are detected by start() or scanDevices()."""
		super().__init__()
		self._devices: list[DeviceSource] = []
		# Devices hidden in the add-on settings, used when the devices are rescanned after a notification
		self._hide: list[str] = []
		# Flags set by the notification handlers in Windows threads and applied in the main thread
		self._devicesChanged: bool = False
		# Incremented whenever the found applications may be outdated
		self._generation: int = 0
		self._enumerator: DeviceEnumerator | None = None
		self._deviceNotifications: DeviceNotifications | None = None
		# Session managers of all active audio devices, the default output device is the first one
		self._sessionManagers: list[SessionManagerEntry] = []

	def start(self, hide: Iterable[str] = ()) -> None:
		"""Detect the audio devices and subscribe to the notifications about audio devices and sessions.
		Must be called in the main thread, stop() must be called when the registry is no longer used.

		:param hide: IDs of the audio devices hidden in the add-on settings
		"""
		self.scanDevices(hide)
		try:
			self._enumerator = getDeviceEnumerator()
			self._deviceNotifications = DeviceNotifications(self)
			self._enumerator.RegisterEndpointNotificationCallback(self._deviceNotifications)
		except COMError:
			logDebugWarning("Unable to subscribe to the notifications about audio devices")
			self._enumerator = self._deviceNotifications = None
		self._subscribeSessions()

	def stop(self) -> None:
		"""Unsubscribe from all notifications. The registry can be started again."""
		self._unsubscribeSessions()
		if self._enumerator is not None and self._deviceNotifications is not None:
			try:
				self._enumerator.UnregisterEndpointNotificationCallback(self._deviceNotifications)
			except COMError:
				logDebugWarning("Unable to unsubscribe from the notifications about audio devices")
		self._enumerator = self._deviceNotifications = None

	def _subscribeSessions(self) -> None:
		"""Get the session managers of all active output and input devices
		and subscribe to the creation of audio sessions on each of them.
		The default output device is the first one, so its applications are listed first.
		"""
		try:
			enumerator = getDeviceEnumerator()
		except COMError:
			logDebugWarning("Unable to get the audio device enumerator")
			return
		defaultIds = getDefaultDeviceIds(enumerator, ERole.eMultimedia)
		entries: list[SessionManagerEntry] = []
		for flow in (EDataFlow.eRender, EDataFlow.eCapture):
			try:
				collection = enumerator.EnumAudioEndpoints(flow.value, DEVICE_STATE.ACTIVE.value)
				count = collection.GetCount()
			except COMError:
				logDebugWarning("Unable to list the active audio devices")
				continue
			for i in range(count):
				try:
					immDevice = collection.Item(i)
					id = immDevice.GetId()
					manager = getSessionManager(immDevice)
				except COMError:
					continue
				notifications: SessionNotifications | None = SessionNotifications(self)
				try:
					manager.RegisterSessionNotification(notifications)
					# Windows sends the notifications only after the session enumerator has been requested
					_ = manager.GetSessionEnumerator()
				except COMError:
					logDebugWarning(f"Unable to subscribe to the notifications about audio sessions of {id}")
					notifications = None
				entries.append(SessionManagerEntry(flow, id, manager, notifications))
		entries.sort(key=lambda entry: entry.deviceId not in defaultIds)
		self._sessionManagers = entries

	def _unsubscribeSessions(self) -> None:
		"""Unsubscribe from the creation of audio sessions on all audio devices."""
		for entry in self._sessionManagers:
			if entry.notifications is None:
				continue
			try:
				entry.manager.UnregisterSessionNotification(entry.notifications)
			except COMError:
				logDebugWarning(
					f"Unable to unsubscribe from the notifications about audio sessions of {entry.deviceId}",
				)
		self._sessionManagers = []

	def markDevicesChanged(self) -> None:
		"""Mark the audio devices outdated. Called by the notification handlers in Windows threads."""
		self._devicesChanged = True
		self._generation += 1

	def markAppsChanged(self) -> None:
		"""Mark the found applications outdated. Called by the notification handler in a Windows thread."""
		self._generation += 1

	def _update(self) -> None:
		"""Apply the changes notified by Windows. Called in the main thread before the lists are used.
		The flags are cleared before rebuilding, so a notification received meanwhile is applied next time.
		"""
		if self._devicesChanged:
			self._devicesChanged = False
			# Devices may have appeared or disappeared, or the default output device whose applications go first has changed
			self._unsubscribeSessions()
			self._subscribeSessions()
			self._devices = self.detectDevices(self._hide)

	def isOutdated(self, app: AppSource) -> bool:
		"""Check whether the previously found application must be looked up again:
		its audio session has expired, a new audio session has been created
		or the audio devices have changed since it was found.

		:param app: previously found application
		:return: whether the application must be looked up again
		"""
		return app.generation != self._generation or app.isExpired

	@property
	def devices(self) -> list[DeviceSource]:
		"""Audio devices found by the last scan, the default output device is the first one.
		The list is rescanned if Windows has notified about changes of the audio devices.

		:return: audio devices whose volume can be adjusted
		"""
		self._update()
		return self._devices

	def scanDevices(self, hide: Iterable[str] = ()) -> None:
		"""Detect the audio devices whose volume can be adjusted and keep them until the next scan.
		It takes a few milliseconds, so it runs in the calling thread, which also uses the created COM objects.

		:param hide: IDs of the audio devices hidden in the add-on settings
		"""
		self._hide = list(hide)
		self._devicesChanged = False
		self._devices = self.detectDevices(self._hide)

	def detectDevices(self, hide: Iterable[str] = ()) -> list[DeviceSource]:
		"""Detect the active audio devices without changing the list of devices kept by the registry.
		The default output device is always the first one, even if it is hidden,
		the other output devices and then the input devices follow.
		Disabled, unplugged and not present devices are skipped. Without a default output device
		(e.g. all output devices are disabled) the other devices, including the input devices, are still detected.

		:param hide: IDs of the audio devices to skip
		:return: detected audio devices
		"""
		try:
			enumerator = getDeviceEnumerator()
		except COMError:
			logDebugWarning("Unable to get the audio device enumerator")
			return []
		defaultIds = getDefaultDeviceIds(enumerator, ERole.eMultimedia)
		communicationIds = getDefaultDeviceIds(enumerator, ERole.eCommunications)
		devices: list[DeviceSource] = []
		try:
			defaultDevice = enumerator.GetDefaultAudioEndpoint(
				EDataFlow.eRender.value,
				ERole.eMultimedia.value,
			)
			devices.append(createDevice(defaultDevice, OutputDeviceSource, defaultIds, communicationIds))
		except COMError:
			logDebugWarning("Unable to get the default output audio device")
		skip = {*(device.id for device in devices), *hide}
		for flow, deviceClass in (
			(EDataFlow.eRender, OutputDeviceSource),
			(EDataFlow.eCapture, InputDeviceSource),
		):
			try:
				collection = enumerator.EnumAudioEndpoints(flow.value, DEVICE_STATE.ACTIVE.value)
				count = collection.GetCount()
			except COMError:
				logDebugWarning(f"Unable to list the active devices of the data flow {flow.name}")
				continue
			for i in range(count):
				try:
					immDevice = collection.Item(i)
					if immDevice.GetId() in skip:
						continue
					devices.append(createDevice(immDevice, deviceClass, defaultIds, communicationIds))
				except COMError:
					# The device has been removed while the devices were detected
					continue
		return devices

	def getSessions(self, flow: EDataFlow) -> list[Session]:
		"""Get the audio sessions of all active devices of the data flow, the default device goes first.
		The caller applies the notified changes with _update() before.

		:param flow: output (eRender) or input (eCapture) devices
		:return: audio sessions of the devices
		"""
		sessions: list[Session] = []
		for entry in self._sessionManagers:
			if entry.flow == flow:
				sessions.extend(listSessions(entry.manager))
		return sessions

	def _getApps[AppT: AppSource](
		self,
		flow: EDataFlow,
		appClass: type[AppT],
		hide: Iterable[str],
	) -> list[AppT]:
		"""Get the applications with audio sessions on the active devices of the data flow.
		There is one audio source per process name, in the order of the audio sessions,
		and all audio sessions of the application on all devices are adjusted together.

		:param flow: output (eRender) or input (eCapture) devices
		:param appClass: class of the created audio sources
		:param hide: names of the processes hidden in the add-on settings
		:return: the applications
		"""
		self._update()
		# Read before the sessions are listed: a notification received meanwhile makes the result outdated
		generation = self._generation
		hidden = set(hide)
		groups: dict[str, list[Session]] = {}
		for session in self.getSessions(flow):
			process = session.Process
			name = process.name() if process else ""
			if name and name not in hidden:
				groups.setdefault(name, []).append(session)
		apps = [appClass(name, sessions) for name, sessions in groups.items()]
		for app in apps:
			app.generation = generation
		return apps

	def getPlaybackApps(self, hide: Iterable[str] = ()) -> list[PlaybackAppSource]:
		"""Get the applications playing sound on any active output device.

		:param hide: names of the processes hidden in the add-on settings
		:return: applications playing sound, those of the default output device go first
		"""
		return self._getApps(EDataFlow.eRender, PlaybackAppSource, hide)

	def getRecordingApps(self, hide: Iterable[str] = ()) -> list[RecordingAppSource]:
		"""Get the applications recording sound from any active input device.

		:param hide: names of the processes hidden in the add-on settings
		:return: applications recording sound, those of the default input device go first
		"""
		return self._getApps(EDataFlow.eCapture, RecordingAppSource, hide)

	def findApp(
		self,
		name: str,
		pid: int = 0,
		kind: SourceKind = SourceKind.PLAYBACK_APP,
	) -> AppSource | None:
		"""Find the application playing or recording sound by its process ID or name.
		The process ID is not enough on its own: e.g. in web browsers the sound is usually played
		by a child process, not by the process of the focused window.
		The exact process name is preferred to a partial match (e.g. "code.exe" is not "vscode.exe").
		There is no fallback to another application: adjusting the volume of NVDA or of an unrelated program
		instead of the requested one would be confusing.

		:param name: full name or part of the process name, empty if it is unknown
		:param pid: ID of the process whose application is preferred, 0 to search by name only
		:param kind: playback or recording applications
		:return: the application, None if it has no audio session in the category
		"""
		apps: list[AppSource] = [
			*(self.getRecordingApps() if kind == SourceKind.RECORDING_APP else self.getPlaybackApps()),
		]
		if pid:
			app = next((app for app in apps if pid in app.processIds), None)
			if app is not None:
				return app
		if not name:
			# An empty name is a part of every name
			return None
		name = name.lower()
		return next((app for app in apps if app.name.lower() == name), None) or next(
			(app for app in apps if name in app.name.lower()),
			None,
		)


# Global instance shared by the global plugin and the settings panel
registry = AudioSourceRegistry()
