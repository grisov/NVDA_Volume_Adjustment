## Version 1.6.0

### Changed

- The list of audio devices (when "Control all available audio devices" is enabled) now contains only active devices. Disabled, unplugged and disconnected devices are no longer shown.
- Detecting audio devices is now much faster, so the add-on settings panel no longer freezes for up to several seconds when it is opened or the list of devices is refreshed.
- When following the focus, the audio session of the focused process itself is now preferred over other processes with the same name.
- For developers: the add-on uses the pycaw module bundled with NVDA and no longer calls its helpers that read the whole property store of audio devices (GetAllSessions, GetSpeakers, GetAllDevices, CreateDevice) on frequent code paths.
- For developers: updated the add-on build tooling to the latest NV Access addonTemplate.

### Fixed

- Noticeable delays when adjusting the volume of applications and switching between audio sources in NVDA 2026. Previously each keypress took about 70 ms on average and up to 300 ms; now the volume changes almost instantly.
- Volume control stopped working after an application was restarted, because the add-on kept adjusting the closed session of the previous instance.
- The first audio source muted after installing the add-on was not remembered and therefore was not unmuted when NVDA exited.
- Lowering the volume of a muted audio source rewrote the add-on configuration file on every keypress.
- Unmuting audio sources when NVDA exits ran in a background thread, which could fail.
- An error on NVDA exit when the add-on settings panel had already been removed.
