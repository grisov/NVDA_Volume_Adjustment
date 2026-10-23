# Changes in the previous versions

## Version 1.5.1
* updated the add-on build tooling to the latest NV Access addonTemplate.

## Version 1.5.0
* the add-on has been tested for compatibility with NVDA 2026.1.

## Version 1.3.5
* the add-on is disabled on secure screens;
* the add-on has been tested for compatibility with NVDA 2023.1.

## Version 1.3.3
* the add-on has been tested for compatibility with NVDA 2022.1;
* added a set of functions to control the volume level of each channel of audio devices;
* added the ability to inform about the status of the sound source or channel when switching between them;
* in the "Input Gestures" dialog displays a separate switching function for each output audio device detected in the system;
* added feature to completely or partially temporarily mute the selected audio source;
* added the ability to restore volume level for all available muted audio sources when NVDA shutdown;
* mute parameters have been added to the settings panel;
* added a warning about possible hearing damage when using the feature to set the maximum volume level;
* the source code is significantly optimized and added MyPy type hints;
* the add-on is adapted to support Python versions 3.7 and 3.8;
* updated third-party module ** psutil **;
* updated translations into Chinese and Ukrainian.

## Version 1.2
* added separate keyboard shortcuts to quickly switch to the selected audio output device;
* added the ability to disable gestures used in the add-on by default.

## Version 1.1
* fixed bug duplication of audio sessions for one running process;
* fixed the method of detecting current audio session;
* improved the method for determining the name of the current process;
* overriding the default output device in another way if the first attempt was unsuccessful;
* improved add-on settings panel;
* added ability to quickly switch the output to other available audio device.

## Version 1.0: features of implementation
* this add-on is based on the advanced features of NVDA Unmute add-on, which were removed from the original add-on due to inconsistency with its main task;
* added the ability to adjust the volume level of all audio devices detected in the system;
* added keyboard shortcuts to quickly set the maximum and minimum volume levels for the selected audio source;
* added add-on settings panel.
