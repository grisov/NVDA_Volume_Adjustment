# A part of the NVDA Volume Adjustment add-on
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.
# Copyright (C) 2020-2026 Oleksandr Gryshchenko <grisov.nvaccess@mailgw.com>

"""Loads the add-on outside NVDA for the tests of the add-on.

The modules of NVDA are replaced with small stand-ins that record what the add-on does (spoken messages,
bound gestures, played sounds). comtypes and pycaw are the real ones when they are installed (Windows),
otherwise stand-ins with the same names are used, so the tests also run on other systems.
Set the environment variable VA_TESTS_STUB_WINDOWS=1 to use the stand-ins on Windows too.
The tests never change the volume of real audio devices or programs: they use the fakes of fakes.py.
"""

from __future__ import annotations
import builtins
import enum
import importlib.util
import os
import sys
import tempfile
import types
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

ADDON_DIR = Path(__file__).parents[2] / "addon" / "globalPlugins" / "volumeAdjustment"
PACKAGE = "volumeAdjustment"

# What the add-on did, inspected by the tests
spoken: list[str] = []
# The messages shown on a braille display: NVDA shows the spoken text unless a braille text is given
brailled: list[str] = []
events: list[Any] = []
# The add-on section and the audio section of the NVDA configuration
options: dict[str, Any] = {}
audio: dict[str, Any] = {"outputDevice": "default", "soundSplitState": 0}
# The object in focus: its application name and process ID
focus = types.SimpleNamespace(appModule=types.SimpleNamespace(appName=""), processID=0)
# The answer of the warning dialog about the volume of NVDA: 1 is OK, 0 is Cancel
dialog: dict[str, Any] = {"shown": 0, "result": 1, "dontShow": False}


def _module(name: str, **attributes: Any) -> types.ModuleType:
	module = types.ModuleType(name)
	module.__dict__.update(attributes)
	sys.modules[name] = module
	return module


class _Conf(dict[str, Any]):
	spec: dict[str, Any] = {}

	def __getitem__(self, key: str) -> dict[str, Any]:
		return options if key == PACKAGE else audio


class _Log:
	"""Collects the errors logged by the add-on, so the tests can check them."""

	def __init__(self) -> None:
		self.errors: list[str] = []

	def error(self, message: str, *args: Any, **kwargs: Any) -> None:
		self.errors.append(message)

	def warning(self, message: str, *args: Any, **kwargs: Any) -> None:
		pass

	def debugWarning(self, message: str, *args: Any, **kwargs: Any) -> None:
		pass


log = _Log()


class _GlobalPlugin:
	"""Stands for globalPluginHandler.GlobalPlugin: records the bound gestures."""

	def __init__(self, *args: Any, **kwargs: Any) -> None:
		self.boundGestures: dict[str, str] = {}

	def bindGestures(self, gestures: dict[str, str]) -> None:
		self.boundGestures.update(gestures)

	def bindGesture(self, gesture: str, scriptName: str) -> None:
		self.boundGestures[gesture] = scriptName

	def terminate(self) -> None:
		pass


def _script(description: str = "", **kwargs: Any) -> Any:
	"""Stands for scriptHandler.script: the description becomes the docstring, as in NVDA."""

	def decorate(function: Any) -> Any:
		if description:
			function.__doc__ = description
		return function

	return decorate


def _callLater(delay: int, function: Any, *args: Any, **kwargs: Any) -> None:
	"""Stands for core.callLater: runs at once and records the delay among the events."""
	events.append(("later", delay))
	function(*args, **kwargs)


def _message(text: str, speechPriority: Any = None, brailleText: str | None = None) -> None:
	"""Stands for ui.message: records the spoken text and the text shown on a braille display."""
	spoken.append(text)
	brailled.append(text if brailleText is None else brailleText)


class _MessageDialog:
	"""Stands for gui.message.MessageDialog: keeps the arguments and adds the contents like the real one."""

	def __init__(self, parent: Any, message: str, title: str = "", dialogType: Any = None, *, buttons: Any = None) -> None:
		self.message, self.title, self.dialogType, self.buttons = message, title, dialogType, buttons
		contents = MagicMock()
		contents.addItem.side_effect = lambda item, **kwargs: item
		self._addContents(contents)

	def _addContents(self, contentsSizer: Any) -> None:
		pass


class _SettingsPanel:
	def __init__(self, parent: Any) -> None:
		pass


def _installNvda(configPath: str) -> None:
	"""Replace the modules of NVDA used by the add-on."""
	_module("config", conf=_Conf())
	_module(
		"addonHandler",
		initTranslation=lambda: None,
		AddonError=Exception,
		Addon=lambda path: types.SimpleNamespace(manifest={"name": PACKAGE, "summary": "Volume Adjustment"}),
	)
	_module("globalVars", appArgs=types.SimpleNamespace(secure=False, configPath=configPath))
	_module("logHandler", log=log)
	_module("ui", message=_message)
	_module("api", getFocusObject=lambda: focus)
	_module(
		"tones",
		terminate=lambda: events.append("tones.terminate"),
		initialize=lambda: events.append("tones.initialize"),
		beep=lambda frequency, duration, **kwargs: events.append(("beep", frequency, duration)),
	)
	_module("core", callLater=_callLater)
	_module(
		"nvwave",
		playWaveFile=lambda path, asynchronous=True, **kwargs: events.append(("sound", os.path.basename(path))),
	)
	_module("globalPluginHandler", GlobalPlugin=_GlobalPlugin, reloadGlobalPlugins=lambda: None)
	_module("scriptHandler", script=_script)
	_module("inputCore", InputGesture=object)
	_module("NVDAObjects", NVDAObject=object)
	_module("queueHandler", eventQueue=None, queueFunction=lambda *args: None)
	_module(
		"synthDriverHandler",
		getSynth=lambda: types.SimpleNamespace(name="espeak"),
		setSynth=lambda name: events.append(("setSynth", name)) or True,
	)
	_module("utils")
	_module(
		"utils.mmdevice",
		getOutputDevices=lambda includeDefault=False, **kwargs: iter(
			[types.SimpleNamespace(id="default", friendlyName="Default output device")] if includeDefault else [],
		),
	)
	settingsDialogs = _module(
		"gui.settingsDialogs",
		SettingsPanel=_SettingsPanel,
		NVDASettingsDialog=types.SimpleNamespace(categoryClasses=[]),
	)
	_module(
		"gui",
		guiHelper=MagicMock(),
		nvdaControls=MagicMock(),
		settingsDialogs=settingsDialogs,
		mainFrame=None,
	)
	_module(
		"gui.message",
		MessageDialog=_MessageDialog,
		ReturnCode=types.SimpleNamespace(OK=1, CANCEL=0),
		DialogType=types.SimpleNamespace(WARNING="WARNING"),
		DefaultButtonSet=types.SimpleNamespace(OK_CANCEL="OK_CANCEL"),
	)
	_module(
		"wx",
		CallAfter=lambda function, *args, **kwargs: function(*args, **kwargs),
		Dialog=object,
		Window=object,
		Sizer=object,
		BoxSizer=MagicMock,
		CheckBox=MagicMock,
		Choice=MagicMock,
		StaticText=MagicMock,
		PyEvent=object,
		CommandEvent=object,
		HORIZONTAL=0,
		VERTICAL=1,
		ID_REFRESH=1,
		ID_CLEAR=2,
		ID_CLOSE=3,
		ALL=0,
		EVT_BUTTON=0,
		EVT_CHECKBOX=0,
		EVT_CHOICE=0,
		EVT_CLOSE=0,
		EVT_CHECKLISTBOX=0,
	)
	builtins._ = lambda text: text  # type: ignore[attr-defined]
	builtins.ngettext = lambda one, many, count: one if count == 1 else many  # type: ignore[attr-defined]


class _COMError(Exception):
	"""Stands for comtypes.COMError."""


def _installWindowsStandIns() -> None:
	"""Replace comtypes, pycaw and psutil with stand-ins that have the names used by the add-on."""
	_module("comtypes", COMError=_COMError, CLSCTX_ALL=23, GUID=lambda text: text)
	interface = type("Interface", (), {"_iid_": "iid"})
	_module("pycaw")
	_module("pycaw.api")
	_module("pycaw.api.audiopolicy", IAudioSessionControl2=interface, IAudioSessionManager2=interface)
	_module("pycaw.api.endpointvolume", IAudioEndpointVolume=interface)
	_module("pycaw.api.mmdeviceapi", IMMEndpoint=interface)
	_module("pycaw.api.mmdeviceapi.depend")
	_module("pycaw.api.mmdeviceapi.depend.structures", PROPERTYKEY=types.SimpleNamespace)
	_module(
		"pycaw.constants",
		DEVICE_STATE=enum.IntEnum("DEVICE_STATE", {"ACTIVE": 1, "DISABLED": 2, "NOTPRESENT": 4, "UNPLUGGED": 8}),
		AudioSessionState=enum.IntEnum("AudioSessionState", {"Inactive": 0, "Active": 1, "Expired": 2}),
		STGM=enum.IntEnum("STGM", {"STGM_READ": 0}),
	)
	_module(
		"pycaw.utils",
		AudioSession=lambda control: control,
		AudioUtilities=types.SimpleNamespace(),
		EDataFlow=enum.IntEnum("EDataFlow", {"eRender": 0, "eCapture": 1, "eAll": 2}),
		ERole=enum.IntEnum("ERole", {"eConsole": 0, "eMultimedia": 1, "eCommunications": 2}),
	)
	_module(
		"pycaw.callbacks",
		MMNotificationClient=type("MMNotificationClient", (), {}),
		AudioSessionNotification=type("AudioSessionNotification", (), {}),
	)
	if "psutil" not in sys.modules:
		try:
			import psutil  # noqa: F401
		except ImportError:
			_module("psutil", Process=object)


def _realWindowsLibrariesAvailable() -> bool:
	if os.environ.get("VA_TESTS_STUB_WINDOWS") == "1" or sys.platform != "win32":
		return False
	try:
		import comtypes  # noqa: F401
		import pycaw.utils  # noqa: F401
	except ImportError:
		return False
	return True


def _load() -> types.ModuleType:
	"""Load the add-on package once, with the stand-ins of NVDA."""
	if PACKAGE in sys.modules and getattr(sys.modules[PACKAGE], "__volumeAdjustmentTests__", False):
		return sys.modules[PACKAGE]
	configPath = tempfile.mkdtemp(prefix="va-tests-")
	_installNvda(configPath)
	if not _realWindowsLibrariesAvailable():
		_installWindowsStandIns()
	spec = importlib.util.spec_from_file_location(
		PACKAGE,
		ADDON_DIR / "__init__.py",
		submodule_search_locations=[str(ADDON_DIR)],
	)
	assert spec is not None and spec.loader is not None
	package = importlib.util.module_from_spec(spec)
	sys.modules[PACKAGE] = package
	spec.loader.exec_module(package)
	package.__volumeAdjustmentTests__ = True
	return package


addon = _load()
REAL_WINDOWS = _realWindowsLibrariesAvailable()


def module(name: str) -> types.ModuleType:
	"""A module of the add-on, e.g. module("navigation")."""
	return sys.modules[f"{PACKAGE}.{name}"]
