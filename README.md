# NVDA Volume Adjustment

* Author: Oleksandr Gryshchenko
* Version: 1.1
* Download [stable version][1]
* Download [development version][2]

Adjust the volume level of all audio devices installed in the system and each running program separately using simple keyboard shortcuts.
You can always change the default keyboard shortcuts to your preferred ones through the NVDA input gestures dialog.

## Features
* adjust the volume level of all audio devices in the system;
* volume control for each running program separately;
* quickly switch to the maximum or minimum volume level of any audio source;
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
* set maximum volume level - NVDA+Windows+Home;
* set minimum volume level - NVDA+Windows+End;
* mute audio source - NVDA+Windows+Arrow Down (when the minimum volume level is already set).

Note: The volume changes by one percent per one keypress by default. This value can be changed in the settings panel in the range from 1 to 20.

## Quick switching between audio output devices
To switch the output of all NVDA sounds to the next available audio device, simply press NVDA+Windows+PageUp.
And to return to the previous audio device, use NVDA+Windows+PageDown.

## Add-on settings panel
The following options allows to flexibly adjust the behavior of the add-on and the list of audio resources to switch between them.

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

## Contributions
We are very grateful to everyone who made the effort to develop, translate and maintain this add-on:
* Dang Manh Cuong - Vietnamese translation;
* Cagri Dogan - Turkish translation;
* Christianlm - Italian translation;
* Cary Rowen - simplified Chinese translation;
* Stefan Banita - Polish translation.

## Change log

### Version 1.1
* fixed bug duplication of audio sessions for one running process;
* fixed the method of  detecting current audio session;
* improved the method for determining the name of the current process;
* overriding the default output device in another way if the first attempt was unsuccessful;
* improved add-on settings panel;
* added ability to quickly switch the output to other available audio device.

### Version 1.0: features of implementation
* This add-on is based on the advanced features of NVDA Unmute add-on, which were removed from the original add-on due to inconsistency with its main task.
* Added the ability to adjust the volume level of all audio devices detected in the system.
* Added keyboard shortcuts to quickly set the maximum and minimum volume levels for the selected audio source.
* Added add-on settings panel.

## Altering NVDA Volume Adjustment
You may clone this repo to make alteration to NVDA Volume Adjustment.

### Third Party dependencies
These can be installed with pip:
- markdown
- scons
- python-gettext

### To package the add-on for distribution:
1. Open a command line, change to the root of this repo
2. Run the **scons** command. The created add-on, if there were no errors, is placed in the current directory.

[1]: https://github.com/grisov/NVDA_Volume_Adjustment/releases/download/v1.1/volumeAdjustment-1.1.nvda-addon
[2]: https://github.com/grisov/NVDA_Volume_Adjustment/releases/download/v1.1/volumeAdjustment-1.1.nvda-addon
