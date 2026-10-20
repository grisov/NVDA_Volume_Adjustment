# A part of the NVDA Volume Adjustment add-on
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.
# Copyright (C) 2020-2026 Oleksandr Gryshchenko <grisov.nvaccess@mailgw.com>

"""The registry of audio sources: applications from all devices, lookups and the notifications of Windows."""

from volumeAdjustmentSupport import module
from volumeAdjustmentSupport.case import AddonTestCase
from volumeAdjustmentSupport.fakes import FakeSession, comError, makeDevice

sources = module("sources")


class TestApplications(AddonTestCase):
	def setUp(self):
		super().setUp()
		self.nvda, self.firefox, self.zoom = (
			FakeSession(1, "nvda.exe"),
			FakeSession(2, "firefox.exe"),
			FakeSession(7, "Zoom.exe"),
		)
		self.playing[:] = [self.nvda, self.firefox, self.zoom, FakeSession(3, "firefox.exe")]

	def test_one_source_per_process_in_the_order_of_sessions(self):
		apps = self.registry.getPlaybackApps()
		self.assertEqual([app.name for app in apps], ["nvda.exe", "firefox.exe", "Zoom.exe"])
		self.assertEqual(apps[1].processIds, [2, 3])
		self.assertTrue(all(app.kind == sources.SourceKind.PLAYBACK_APP for app in apps))

	def test_hidden_processes_and_sessions_without_a_process(self):
		self.playing.append(FakeSession(0, ""))
		self.assertEqual([app.name for app in self.registry.getPlaybackApps(["Zoom.exe"])], ["nvda.exe", "firefox.exe"])

	def test_recording_applications_are_separate(self):
		self.recording[:] = [FakeSession(7, "Zoom.exe"), FakeSession(9, "obs64.exe")]
		recording = self.registry.getRecordingApps()
		self.assertEqual([app.name for app in recording], ["Zoom.exe", "obs64.exe"])
		self.assertTrue(all(isinstance(app, sources.RecordingAppSource) for app in recording))
		self.assertNotIn("obs64.exe", [app.name for app in self.registry.getPlaybackApps()])

	def test_find_by_process_then_exact_then_partial_name(self):
		self.playing.append(FakeSession(8, "vscode.exe"))
		self.playing.append(FakeSession(9, "code.exe"))
		self.assertEqual(self.registry.findApp("anything", 7).name, "Zoom.exe")
		self.assertEqual(self.registry.findApp("code.exe").name, "code.exe")
		self.assertEqual(self.registry.findApp("fire").name, "firefox.exe")
		self.assertIsNone(self.registry.findApp("notepad"))

	def test_find_recording_application(self):
		self.recording[:] = [FakeSession(7, "Zoom.exe")]
		app = self.registry.findApp("Zoom.exe", kind=sources.SourceKind.RECORDING_APP)
		self.assertIsInstance(app, sources.RecordingAppSource)


class TestNotifications(AddonTestCase):
	def test_found_application_is_reused_until_a_notification(self):
		self.playing[:] = [FakeSession(2, "firefox.exe")]
		app = self.registry.findApp("firefox")
		self.assertFalse(self.registry.isOutdated(app))
		self.registry.markAppsChanged()
		self.assertTrue(self.registry.isOutdated(app))
		self.assertFalse(self.registry.isOutdated(self.registry.findApp("firefox")))

	def test_expired_session_makes_the_application_outdated(self):
		session = FakeSession(2, "firefox.exe")
		self.playing[:] = [session]
		app = self.registry.findApp("firefox")
		session.State = 2
		self.assertTrue(self.registry.isOutdated(app))

	def test_devices_are_rescanned_once_when_used(self):
		scans = []
		original = self.registry.detectDevices
		self.patch(self.registry, "detectDevices", lambda hide=(): scans.append(1) or original(hide))
		self.outputs[:] = [makeDevice("output", "{a}", "Speakers", isDefaultDevice=True)]
		self.registry.markDevicesChanged()
		self.registry.markDevicesChanged()
		self.assertEqual(scans, [])
		self.assertEqual([device.name for device in self.registry.devices], ["Speakers"])
		self.registry.devices
		self.assertEqual(scans, [1])

	def test_hidden_devices_stay_hidden_after_a_notification(self):
		self.outputs[:] = [makeDevice("output", "{a}", "Speakers"), makeDevice("output", "{b}", "Headphones")]
		self.registry.scanDevices(["{b}"])
		self.registry.markDevicesChanged()
		self.assertEqual([device.id for device in self.registry.devices], ["{a}"])

	def test_default_output_device_is_kept_even_if_hidden(self):
		self.outputs[:] = [makeDevice("output", "{a}", "Speakers"), makeDevice("output", "{b}", "Headphones")]
		self.registry.scanDevices(["{a}"])
		self.assertEqual([device.id for device in self.registry.devices], ["{a}", "{b}"])

	def test_notification_handlers_mark_the_registry(self):
		registryModule = module("registry")
		devices = registryModule.DeviceNotifications(self.registry)
		sessions = registryModule.SessionNotifications(self.registry)
		generation = self.registry._generation
		devices.on_device_added("{x}")
		sessions.on_session_created(None)
		devices.on_default_device_changed("eRender", 0, "eMultimedia", 1, "{x}")
		self.assertEqual(self.registry._generation, generation + 3)
		self.assertTrue(self.registry._devicesChanged)

	def test_start_and_stop_without_windows_audio(self):
		self.registry.stop()
		self.registry.start()
		self.assertIsNone(self.registry._enumerator)
		self.registry.stop()


class FakeImmDevice:
	"""Stands for IMMDevice: only its ID, or COMError if the device has been removed."""

	def __init__(self, id: str | None) -> None:
		self.id = id

	def GetId(self) -> str:
		if self.id is None:
			raise comError()
		return self.id


class FakeCollection:
	def __init__(self, devices):
		self.devices = devices

	def GetCount(self):
		return len(self.devices)

	def Item(self, index):
		return self.devices[index]


class FakeEnumerator:
	def __init__(self, default, outputs, inputs, failingFlow=None):
		self.default, self.outputs, self.inputs, self.failingFlow = default, outputs, inputs, failingFlow

	def GetDefaultAudioEndpoint(self, flow, role):
		if self.default is None:
			raise comError()
		return FakeImmDevice(self.default)

	def EnumAudioEndpoints(self, flow, state):
		if flow == self.failingFlow:
			raise comError()
		return FakeCollection([FakeImmDevice(id) for id in (self.outputs if flow == 0 else self.inputs)])


class TestDeviceDetection(AddonTestCase):
	"""The real detection of the registry with a fake device enumerator of Windows."""

	def detect(self, enumerator, hide=()):
		registryModule = module("registry")
		self.patch(registryModule, "getDeviceEnumerator", lambda: enumerator)
		self.patch(registryModule, "getDefaultDeviceIds", lambda enumerator, role: [])
		self.patch(
			registryModule,
			"createDevice",
			lambda immDevice, deviceClass, defaultIds, communicationIds: makeDevice(
				"output" if deviceClass is sources.OutputDeviceSource else "input",
				immDevice.GetId(),
				immDevice.GetId(),
			),
		)
		return [device.id for device in type(self.registry).detectDevices(self.registry, hide)]

	def test_default_output_device_first_then_outputs_then_inputs(self):
		enumerator = FakeEnumerator("{b}", ["{a}", "{b}"], ["{mic}"])
		self.assertEqual(self.detect(enumerator, hide=["{a}"]), ["{b}", "{mic}"])

	def test_input_devices_without_a_default_output_device(self):
		self.assertEqual(self.detect(FakeEnumerator(None, [], ["{mic}"])), ["{mic}"])

	def test_device_removed_while_detecting(self):
		self.assertEqual(self.detect(FakeEnumerator("{a}", ["{a}", None], [None, "{mic}"])), ["{a}", "{mic}"])

	def test_input_devices_when_the_outputs_cannot_be_listed(self):
		self.assertEqual(self.detect(FakeEnumerator(None, ["{a}"], ["{mic}"], failingFlow=0)), ["{mic}"])
