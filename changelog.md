## Version 2.0.0

### Changed

- The list of audio devices (when "Control all available audio devices" is enabled) now contains only active devices. Disabled, unplugged and disconnected devices are no longer shown.
- The list of audio devices is updated automatically when devices are connected, disconnected, enabled or disabled, without opening the add-on settings.
- Detecting audio devices is now much faster, so the add-on settings panel no longer freezes for up to several seconds when it is opened or the list of devices is refreshed.
- When following the focus, the audio session of the focused process itself is now preferred over other processes with the same name.
- All audio sessions of an application are adjusted and muted together; previously only the first session of the application was changed.
- Applications are now found on all active output devices, not only on the default one, and an application playing on several devices is adjusted on all of them at once.
- The volume of the left and right channels can now be adjusted for applications too, unless NVDA sound split is enabled.
- Applications recording sound can now be selected and adjusted as well; the audio sources are switched in the order: output devices, input devices, applications playing sound, applications recording sound.
- When switching to an audio source of another category, the category name is announced before the source name; this can be turned off in the add-on settings.
- Categories of audio sources can be shown or hidden with NVDA+Windows+O, I, P and R, and NVDA+Shift+Windows with the same letters shows only that category.
- The visible categories of audio sources can also be chosen in the add-on settings.
- NVDA+Control+Windows+Right Arrow and Left Arrow jump to the first audio source of the next or previous category.
- Before lowering, minimizing or muting the volume of NVDA itself, a warning is shown: it can silence NVDA speech, and Windows keeps this volume after NVDA restarts. The warning can be turned off in the dialog or in the add-on settings.
- In the "Volume Down" mute mode, the remaining volume level is announced after muting, e.g. "The sound is muted, volume 5%".
- The default output device and the default communication device of Windows can be set with NVDA+Shift+Windows and NVDA+Control+Windows with F1-F12, PageUp and PageDown.
- NVDA+Windows+F1-F12 switch NVDA output to the output devices found when NVDA starts, and NVDA+Windows+D switches it to the default output device.
- NVDA+Windows+S opens the classic Sound dialog of Windows, or the Sound page of the Windows Settings if the dialog is not available.
- All active output and input devices are always available, the option "Control all available audio devices" has been removed from settings panel.
- The add-on uses the pycaw module bundled with NVDA and no longer calls its helpers that read the whole property store of audio devices (GetAllSessions, GetSpeakers, GetAllDevices, CreateDevice) on frequent code paths.
- Updated the add-on build tooling to the latest NV Access addonTemplate.

### Fixed

- NVDA could crash after the list of audio devices was rescanned, e.g. after toggling "Control all available audio devices", pressing "Update" or saving hidden devices in the add-on settings.
- When the application in focus or selected in the list did not play any sound, the add-on silently adjusted the volume of NVDA or of another program. Now it announces that the application is not playing any sound.
- Noticeable delays when adjusting the volume of applications and switching between audio sources in NVDA 2026. Previously each keypress took about 70 ms on average and up to 300 ms; now the volume changes almost instantly.
- Volume control stopped working after an application was restarted, because the add-on kept adjusting the closed session of the previous instance.
- The first audio source muted after installing the add-on was not remembered and therefore was not unmuted when NVDA exited.
- Muted processes that were later hidden in the settings were not unmuted when NVDA exited.
- The "Update" button in the list of audio devices added hidden devices to the list of audio sources until the settings were saved.
- After the default audio output device was changed in Windows, the volume of the selected application could still be adjusted on the previous device.
- Volume levels were announced inaccurately: some levels were announced twice and others skipped while stepping. Unmuting in the "Volume Down" mute mode did not restore the exact previous level (e.g. 50 % became 48 %).
- Lowering the volume of a muted audio source rewrote the add-on configuration file on every keypress.
- Unmuting audio sources when NVDA exits ran in a background thread, which could fail.
- An error on NVDA exit when the add-on settings panel had already been removed.
