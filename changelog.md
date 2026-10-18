## Version 2.0.0

### Changed

- The list of audio devices (when "Control all available audio devices" is enabled) now contains only active devices. Disabled, unplugged and disconnected devices are no longer shown.
- Detecting audio devices is now much faster, so the add-on settings panel no longer freezes for up to several seconds when it is opened or the list of devices is refreshed.
- When following the focus, the audio session of the focused process itself is now preferred over other processes with the same name.
- All audio sessions of an application are adjusted and muted together; previously only the first session of the application was changed.
- For developers: the add-on uses the pycaw module bundled with NVDA and no longer calls its helpers that read the whole property store of audio devices (GetAllSessions, GetSpeakers, GetAllDevices, CreateDevice) on frequent code paths.
- For developers: updated the add-on build tooling to the latest NV Access addonTemplate.

### Fixed

- NVDA could crash after the list of audio devices was rescanned, e.g. after toggling "Control all available audio devices", pressing "Update" or saving hidden devices in the add-on settings.
- When the application in focus or selected in the list did not play any sound, the add-on silently adjusted the volume of NVDA or of another program. Now it announces that the application is not playing any sound.
- Noticeable delays when adjusting the volume of applications and switching between audio sources in NVDA 2026. Previously each keypress took about 70 ms on average and up to 300 ms; now the volume changes almost instantly.
- Volume control stopped working after an application was restarted, because the add-on kept adjusting the closed session of the previous instance.
- The first audio source muted after installing the add-on was not remembered and therefore was not unmuted when NVDA exited.
- Muted processes that were later hidden in the settings were not unmuted when NVDA exited.
- The "Update" button in the list of audio devices added hidden devices to the list of audio sources until the settings were saved.
- Lowering the volume of a muted audio source rewrote the add-on configuration file on every keypress.
- Unmuting audio sources when NVDA exits ran in a background thread, which could fail.
- An error on NVDA exit when the add-on settings panel had already been removed.
