# NVDA Volume Adjustment

* Author: Oleksandr Gryshchenko
* Version: 1.3
* NVDA compatibility: 2019.3 and beyond
* Download [stable version][1]

Adjust the volume level of all audio devices installed in the system and each running program separately using simple keyboard shortcuts.  
You can always change the default keyboard shortcuts to your preferred ones through the NVDA input gestures dialog.

## Features
* adjust the volume level of all audio devices in the system;
* volume control for each running program separately;
* the ability to adjust the volume of each channel of the selected audio device or set the average value for all channels;
* quickly switch to the maximum or minimum volume level of any audio source or the selected channel;
* two modes of the sound source mutting - full switching off or decrease in volume in percent;
* the ability to restore the volume level of all available muted audio sources at the NVDA shutdown;
* flexible settings for announcing the list of detected audio devices and running programs;
* automatically switching to the program in focus;
* the ability to set a custom volume change step;
* quick switching the output to other available audio devices.

## Switch between audio sources
To go to the previous or next audio source you can use the NVDA+Windows+ left or right arrow key combinations. The list consists of two parts - system audio devices and running audio sessions. Switching occurs cyclically in a circle like NVDA settings circle.  
Through the add-on settings panel you can hide any items in this list.  
Switching between audio sessions can occur automatically when switching to the window of the corresponding program - this mode can be enabled in the add-on settings panel.

Note: The list of audio sessions changes dinamicly and depends on the running programs.

## Adjust the volume level
When the sound source is selected you can change its volume level using the following commands:

* increase volume - NVDA+Windows+Arrow Up;
* decrease volume - NVDA+Windows+Arrow Down;
* set maximum volume level - NVDA+Windows+Home (be careful, this action can damage your hearing);
* set minimum volume level - NVDA+Windows+End;
* turn off audio source - NVDA+Windows+Arrow Down (when the minimum volume level is already set);
* mute the volume or restore the volume of the previously muted audio source - NVDA+Windows+Escape, mute mode can be selected in the add-on settings panel.

Note: The volume changes by one percent per one keypress by default. This value can be changed in the settings panel in the range from 1 to 20.

## Adjust the volume of the selected channel
For the selected sound source is also available to adjust the volume of its individual channels:

* switch between all available channels of the selected audio source - NVDA+Shift+Windows+ right or left arrows;
* increase or decrease the volume level of the selected channel - NVDA+Shift+Windows+ up or down arrows;
* set the maximum or minimum volume level of the selected channel - NVDA+Shift+Windows+ Home or End;
* set the average volume level for all channels - NVDA+Shift+Windows+Escape.

Note: Channel volume control is currently available only for audio devices.

## Quick switching between audio output devices
To switch the output of all NVDA sounds to the next available audio device, simply press NVDA+Windows+PageUp.  
And to return to the previous audio device, use NVDA+Windows+PageDown.  
In addition, to quickly switch the NVDA audio output to the selected audio device, you can use the NVDA+Windows+ function keys from F1.

Note: The separate switching functions are created for all output audio devices detected in the system. All of these features are displayed in the "Input Gestures" dialog, where you can assign activation commands to each of the detected devices.

## Add-on settings panel
The following options allows to flexibly adjust the behavior of the add-on and the list of audio resources to switch between them.

### Announce the state of the sound source when switching
If this checkbox is checked, during the switching between audio sources or between channels, their current status will be announced, namely the volume level or mute indicator.

### Step to change the volume level
The minimum value to which the volume level will be changed with a one keypress. You can set value from 1 to 20 points.

### Automatic audio session switching
If this check box is checked, the add-on will be automatically switching to the audio session that corresponds to the program in focus.  
For example, if you are currently browsing a website in Firefox, the add-on will detect this and automatically switch to the Firefox audio session. And you can immediately adjust the volume level for the current process without finding it in the list.

### Hide audio sessions with the same names
Sometimes, when runs some programs, there are openning multiple audio sessions with the same names. This option allows to hide such audio sessions.

### Hide processes
In this list of check boxes you can mark the processes that you want to hide from the main list. These can be, for example, service programs.  
The "Update" button is used to update the list of all running processes and available audio sessions. The all checked elements remain as marked.  
"Clear" button - uncheck all checked elements and removes obsolete items.

### Control all available audio devices
Enables advanced features of the add-on, namely the ability to adjust the volume of all audio devices detected in the system.  
For unknown reasons, this feature causes errors on some systems, so it is marked as experimental.

### Hide audio devices
If you don't use one or more audio devices and do not want them to be present when switching between audio sources, you can easily remove them from the main list by simply checking them in the settings panel.  
The "Update" button is used to scan all audio devices on the system and display updated information. And all checked elements are remain as marked.  
"Clear" button - uncheck all checked elements and removes obsolete items.

### Mute the volume
The volume mute feature can work in two modes:

1. Completely turn off the audio source. To enable this mode, you must select the appropriate option in the mutting mode selection list.
2. Decrease the volume level by the percentage value that can be adjusted with the slider in the add-on settings panel.

Note: It is possible to restore the volume level for all available muted audio sources when NVDA shutdown. Because the list of audio sessions changes dynamically, the volume will only be restored for currently available programs that play audio.

### Using default keyboard shortcuts
If you don't planning to use all the features of the add-on. In the settings panel, you can disable the default key combinations for all available functions. Then you can assign your own keyboard shortcuts through the standard NVDA "Input Gestures..." dialog only for those functions that interest you.

## Contributions
We are very grateful to everyone who made the effort to develop, translate and maintain this add-on:

* Dang Manh Cuong - Vietnamese translation;
* Cagri Dogan - Turkish translation and testing of pre-releases;
* Christianlm - Italian translation;
* Cary Rowen - simplified Chinese translation, a lot of good ideas and testing of pre-releases;
* Stefan Banita - Polish translation;
* Wafiqtaher - Arabic translation.

## Known issues
In some systems, the scanning function of all available audio devices causes errors for unknown reasons. This is a known issue with the third-party PyCaw module that has not yet been resolved.

## Change log

### Version 1.3
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

### Version 1.2
* added separate keyboard shortcuts to quickly switch to the selected audio output device;
* added the ability to disable gestures used in the add-on by default.

### Version 1.1
* fixed bug duplication of audio sessions for one running process;
* fixed the method of  detecting current audio session;
* improved the method for determining the name of the current process;
* overriding the default output device in another way if the first attempt was unsuccessful;
* improved add-on settings panel;
* added ability to quickly switch the output to other available audio device.

### Version 1.0: features of implementation
* this add-on is based on the advanced features of NVDA Unmute add-on, which were removed from the original add-on due to inconsistency with its main task;
* added the ability to adjust the volume level of all audio devices detected in the system;
* added keyboard shortcuts to quickly set the maximum and minimum volume levels for the selected audio source;
* added add-on settings panel.

## Altering of add-on source code
You may clone this repo to make alteration to NVDA Volume Adjustment.

### Third Party dependencies
These can be installed with pip:

- markdown
- scons
- python-gettext

### To package the add-on for distribution
1. Open a command line, change to the root of this repo
2. Run the **scons** command. The created add-on, if there were no errors, is placed in the current directory.

[1]: https://github.com/grisov/NVDA_Volume_Adjustment/releases/download/latest/volumeAdjustment-1.3.2.nvda-addon
