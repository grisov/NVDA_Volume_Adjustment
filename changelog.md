## Version 2.0.0

### Added

- Audio sources are divided into four categories, switched in this order: output devices, input devices, applications playing sound and applications recording sound. All active output and input devices are always available.
- Commands to set the default output device and the default communication device of Windows, by the number of the device or to the next or previous device. (#10)
- Commands to set the default input device and the default communication input device of Windows, by the number of the device found when NVDA starts. (#24)
- Applications are found on all active output devices, not only on the default one, and an application playing on several devices is adjusted on all of them at once. (#23)
- Quick mute: one command mutes and unmutes in Windows the microphones selected in the add-on settings, for all programs at once. A short sound is played after muting and before unmuting.
- The channels of applications can be adjusted too, unless NVDA sound split is enabled. (#11)
- A warning is shown before lowering, minimizing or muting the volume or a channel of NVDA itself: it can silence NVDA speech, and Windows keeps this volume after NVDA restarts. The warning can be turned off in the dialog or in the add-on settings.
- Commands to jump to the first audio source of the next or previous category.
- Commands to show or hide each category of audio sources and to show only one category. The visible categories can also be chosen in the add-on settings.
- The category name is announced when switching to an audio source of another category; this can be turned off in the add-on settings.
- A command to switch NVDA output back to the default output device. (#6)
- A command to open the classic Sound dialog of Windows, or the Sound page of the Windows Settings if the dialog is not available.
- The volume level can be announced in percent, in percent without the percent sign, or in decibels for audio devices (add-on settings).
- In the "Volume Down" mute mode, the remaining volume level is announced after muting, e.g. "The sound is muted, Volume 5%".
- The type, connection and default role of audio devices can be announced when switching between them (add-on settings).

### Changed

- The predefined keyboard shortcuts are turned off after installation. They can be turned on in the add-on settings, or any command can be assigned in the NVDA Input Gestures dialog.
- The commands that switch NVDA output to a single device are created for the output devices found when NVDA starts, and the first of them is no longer the default device. Custom gestures assigned to the previous commands for single output devices need to be assigned again. (#6)
- All audio sessions of an application are adjusted and muted together; previously only the first session of the application was changed. (#5)
- When following the focus, the audio session of the focused process itself is preferred over other processes with the same name.
- The list of audio devices contains only active devices and is updated automatically when devices are connected, disconnected, enabled or disabled. (#7)
- Detecting audio devices is much faster, so the add-on settings panel no longer freezes for up to several seconds when it is opened or the list of devices is refreshed.
- The add-on settings list the output devices, the input devices and the processes to hide separately.
- Channels are numbered from 1.
- The add-on uses the pycaw module bundled with NVDA and no longer calls its helpers that read the whole property store of audio devices (GetAllSessions, GetSpeakers, GetAllDevices, CreateDevice) on frequent code paths.
- Updated the add-on build tooling to the latest NV Access addonTemplate.

### Removed

- The option "Control all available audio devices": all active devices are always available. (#7)
- The option "Hide audio sessions with the same names": the audio sessions of an application are always adjusted together. (#5)

### Fixed

- NVDA could crash after the list of audio devices was rescanned, e.g. after pressing "Refresh" or saving hidden devices in the add-on settings. (#7, #16)
- In NVDA 2026.1 and later, the default output device was missing from the list of audio sources because of the new version of the pycaw module included in NVDA. (#25)
- Noticeable delays when adjusting the volume of applications and switching between audio sources in NVDA 2026. Previously each keypress took about 70 ms on average and up to 300 ms; now the volume changes almost instantly. (#33)
- When the application in focus or selected in the list did not play any sound, the add-on silently adjusted the volume of NVDA or of another program. Now it announces that the application is not playing or not recording any sound.
- Volume control stopped working after an application was restarted, because the add-on kept adjusting the closed session of the previous instance. (#5)
- After the default output device was changed in Windows, the volume of the selected application could still be adjusted on the previous device.
- When the selected audio device was disconnected or hidden, the volume of the default output device was changed instead. Now the add-on announces that the device is not available.
- Input devices were not available when Windows had no active output device.
- The name of the audio source or channel is now shown on a braille display together with its volume level, e.g. "USB headphones: 30%". (#15)
- Volume levels were announced inaccurately: some levels were announced twice and others skipped while stepping. Unmuting in the "Volume Down" mute mode did not restore the exact previous level (e.g. 50% became 48%).
- The first audio source muted after installing the add-on was not remembered and therefore was not unmuted when NVDA exited.
- Muted processes and audio devices that were later hidden in the settings were not unmuted when NVDA exited.
- When NVDA exited, the add-on also unmuted the audio sources muted in Windows or by other programs, not only those muted by the add-on.
- The option to use the default keyboard shortcuts was not saved when the user chose to reload the add-ons later.
- The "Refresh" button in the list of audio devices added hidden devices to the list of audio sources until the settings were saved.
- Lowering the volume of a muted audio source rewrote the add-on configuration file on every keypress.
- Unmuting audio sources when NVDA exits ran in a background thread, which could fail.
- An error on NVDA exit when the add-on settings panel had already been removed.
- The keyboard shortcut of the "Decrease the volume by" slider in the add-on settings did not work. The slider is now unavailable in the "Complete Mute" mode instead of being hidden.
