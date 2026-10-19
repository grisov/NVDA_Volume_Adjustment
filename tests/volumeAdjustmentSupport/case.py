# A part of the NVDA Volume Adjustment add-on
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.
# Copyright (C) 2020-2026 Oleksandr Gryshchenko <grisov.nvaccess@mailgw.com>

"""The base class of the tests: a fresh global plugin in a fake audio world for every test."""

from __future__ import annotations
import unittest
from typing import Any

from . import addon, audio, brailled, dialog, events, focus, log, module, options, spoken
from .fakes import FakeSession, FakeWarningDialog, comError

# Options of the tests: the defaults of the add-on, with gestures and every announcement under control of the tests
TEST_OPTIONS: dict[str, Any] = {
	"status": True,
	"step": 1,
	"units": "percent",
	"focus": True,
	"categories": "OIPR",
	"announceCategories": False,
	"deviceDetails": False,
	"muteCompletely": False,
	"mutePercentage": 75,
	"unmuteOnExit": True,
	"warnNvdaVolume": True,
	"gestures": False,
}


class AddonTestCase(unittest.TestCase):
	"""Every test gets a new global plugin and an audio world it controls:

	- self.outputs, self.inputs: the active audio devices, the default output device first;
	- self.playing, self.recording: the audio sessions of programs on output and input devices;
	- self.windowsOutputs, self.windows: the output devices and default devices of Windows for outputs.py;
	- support.spoken: the messages announced by the add-on, support.brailled: the same on a braille display;
	- support.events: sounds, mute changes and delays.
	"""

	def setUp(self) -> None:
		self._patches: list[tuple[Any, str, Any]] = []
		options.clear()
		options.update(TEST_OPTIONS)
		audio.clear()
		audio.update({"outputDevice": "default", "soundSplitState": 0})
		spoken.clear()
		brailled.clear()
		events.clear()
		log.errors.clear()
		dialog.update(shown=0, result=1, dontShow=False)
		focus.appModule.appName, focus.processID = "", 0
		self.cfg = module("configuration").cfg
		self.patch(self.cfg, "save", lambda: None)
		self.cfg._data = {"version": 0}
		self.outputs: list[Any] = []
		self.inputs: list[Any] = []
		self.playing: list[FakeSession] = []
		self.recording: list[FakeSession] = []
		self.windowsOutputs: list[tuple[str, str]] = []
		self.windows: dict[str, Any] = {"default": "", "communication": "", "fail": False, "set": []}
		self.registry = module("registry").registry
		self._installWorld()
		self.patch(module("protection"), "NvdaVolumeWarningDialog", FakeWarningDialog)
		self.plugin = addon.GlobalPlugin()
		spoken.clear()
		brailled.clear()

	def tearDown(self) -> None:
		self.plugin.terminate()
		for target, name, original in reversed(self._patches):
			setattr(target, name, original)

	def patch(self, target: Any, name: str, value: Any) -> None:
		"""Replace an attribute for this test only."""
		self._patches.append((target, name, getattr(target, name)))
		setattr(target, name, value)

	def _installWorld(self) -> None:
		registryModule = module("registry")
		sources = module("sources")

		def noEnumerator() -> Any:
			# No real Windows audio in the tests: the registry runs without notifications of Windows
			raise comError()

		self.patch(registryModule, "getDeviceEnumerator", noEnumerator)
		self.patch(
			self.registry,
			"getSessions",
			lambda flow: list(self.playing if flow == registryModule.EDataFlow.eRender else self.recording),
		)

		def getAllDevices(hide: Any = ()) -> list[Any]:
			devices = [*self.outputs, *self.inputs]
			if not devices:
				return []
			hidden = set(hide)
			# Like the real registry: the default output device is always the first one, even if it is hidden
			return [devices[0], *(device for device in devices[1:] if device.id not in hidden)]

		self.patch(self.registry, "getAllDevices", getAllDevices)
		self.registry._devices = []
		self.registry._hide = []
		self.registry._generation = 0
		self.registry._devicesChanged = False
		self.registry._sessionManagers = []

		def setDefaultOutput(id: str, roles: list[Any]) -> bool:
			self.windows["set"].append((id, [role.name for role in roles]))
			if self.windows["fail"]:
				return False
			for role in roles:
				self.windows["communication" if role.name == "eCommunications" else "default"] = id
			return True

		def getDefaultOutputId(role: Any) -> str:
			return self.windows["communication" if role.name == "eCommunications" else "default"]

		def getDevice(id: str) -> Any:
			return next((device for device in [*self.outputs, *self.inputs] if device.id == id), None)

		replacements = {
			"getOutputDevices": lambda: list(self.windowsOutputs),
			"getDefaultOutputId": getDefaultOutputId,
			"setDefaultOutput": setDefaultOutput,
			"getDevice": getDevice,
		}
		for name, function in replacements.items():
			self.patch(module("devices"), name, function)
			self.patch(module("outputs"), name, function)
		self.patch(module("settings"), "isInputDevice", lambda id: id.startswith("{0.0.1."))
		self.sources = sources

	def refresh(self) -> None:
		"""Apply the changes of the fake world, as the notifications of Windows would."""
		self.registry.markDevicesChanged()

	def focusOn(self, appName: str, pid: int) -> None:
		"""Move the focus to a window of the program."""
		focus.appModule.appName, focus.processID = appName, pid
		self.plugin.event_gainFocus(focus, lambda: None)

	def press(self, scriptName: str) -> list[str]:
		"""Run a script of the plugin and return what it announced."""
		start = len(spoken)
		getattr(self.plugin, f"script_{scriptName}")(None)
		return spoken[start:]

	@property
	def navigator(self) -> Any:
		return self.plugin.navigator
