# NVDA Volume Adjustment

* Author: Oleksandr Gryshchenko
* Version: 1.6
* NVDA compatibility: 2026.1 and beyond
* Installation: through the NVDA Add-on Store ([stable version][1])

Adjust the volume level of all audio devices installed in the system and each running program separately using simple keyboard shortcuts.

You can always change the default keyboard shortcuts to your preferred ones through the NVDA input gestures dialog.

## Features
* adjust the volume level of all audio devices in the system;
* volume control for each running program separately;
* the ability to adjust the volume of each channel of the selected audio device or set the average value for all channels;
* quickly switch to the maximum or minimum volume level of any audio source or the selected channel;
* two modes of muting the sound source - full switching off or decrease in volume in percent;
* the ability to restore the volume level of all available muted audio sources when NVDA shuts down;
* flexible settings for announcing the list of detected audio devices and running programs;
* automatically switching to the program in focus;
* the ability to set a custom volume change step;
* quick switching the output to other available audio devices.

## Switch between audio sources
To go to the previous or next audio source you can use the NVDA+Windows+ left or right arrow key combinations. The list consists of two parts - system audio devices and running audio sessions. Switching occurs cyclically, like in the NVDA synth settings ring.

Through the add-on settings panel you can hide any items in this list.

Switching between audio sessions can occur automatically when switching to the window of the corresponding program - this mode can be enabled in the add-on settings panel.

Note: The list of audio sessions changes dynamically and depends on the running programs.

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
For the selected sound source, you can also adjust the volume of its individual channels:

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
The following options allow you to flexibly adjust the behavior of the add-on and the list of audio sources to switch between.

### Announce the state of the sound source when switching
If this checkbox is checked, during the switching between audio sources or between channels, their current status will be announced, namely the volume level or mute indicator.

### Step to change the volume level
The value by which the volume level is changed with one keypress. You can set a value from 1 to 20 points.

### Automatic audio session switching
If this check box is checked, the add-on automatically switches to the audio session that corresponds to the program in focus.

For example, if you are currently browsing a website in Firefox, the add-on will detect this and automatically switch to the Firefox audio session. And you can immediately adjust the volume level for the current process without finding it in the list.

### Hide audio sessions with the same names
Some programs open multiple audio sessions with the same name. This option allows you to hide such duplicate audio sessions.

### Hide processes
In this list of check boxes you can mark the processes that you want to hide from the main list. These can be, for example, service programs.

The "Update" button is used to update the list of all running processes and available audio sessions. All checked elements remain checked.

"Clear" button - uncheck all checked elements and removes obsolete items.

### Control all available audio devices
Enables advanced features of the add-on, namely the ability to adjust the volume of all active audio devices detected in the system.

### Hide audio devices
If you don't use one or more audio devices and do not want them to be present when switching between audio sources, you can easily remove them from the main list by simply checking them in the settings panel.

The "Update" button is used to scan all audio devices on the system and display updated information. All checked elements remain checked.

"Clear" button - uncheck all checked elements and removes obsolete items.

### Mute the volume
The volume mute feature can work in two modes:

1. Completely turn off the audio source. To enable this mode, you must select the appropriate option in the muting mode selection list.
2. Decrease the volume level by the percentage value that can be adjusted with the slider in the add-on settings panel.

Note: It is possible to restore the volume level for all available muted audio sources when NVDA shuts down. Because the list of audio sessions changes dynamically, the volume will only be restored for currently available programs that play audio.

### Using default keyboard shortcuts
If you don't plan to use all the features of the add-on, you can disable the default key combinations for all available functions in the settings panel. Then you can assign your own keyboard shortcuts through the standard NVDA "Input Gestures..." dialog only for those functions that interest you.

## Contributions
We are very grateful to everyone who made the effort to develop, translate and maintain this add-on:

* Dang Manh Cuong - Vietnamese translation;
* Cagri Dogan - Turkish translation and testing of pre-releases;
* Christianlm - Italian translation;
* Cary Rowen - simplified Chinese translation, a lot of good ideas and testing of pre-releases;
* Stefan Banita - Polish translation;
* Wafiqtaher - Arabic translation.

## Change log
The history of changes for each version of the add-on is published on the [Releases page][2] of the add-on repository.

## Altering of add-on source code
You may clone this repo to make alterations to NVDA Volume Adjustment.

Requirements:

* [uv](https://docs.astral.sh/uv/) - manages Python and all development tools of the add-on;
* [GNU Gettext tools](https://mlocati.github.io/articles/gettext-iconv-windows.html) (`msgfmt` and `xgettext` in the `PATH`) - compile translations and generate the template of translatable strings.

Run the following commands from the root of the repository:

1. `uv sync` - install the development dependencies;
2. `uv run prek run --all-files` - run all code checks: linting and formatting with ruff, type checking with pyright and other checks;
3. `uv run python -m unittest discover -s tests -v` - run the unit tests;
4. `uv run scons` - build the add-on, the created `.nvda-addon` file is placed in the root of the repository;
5. `uv run scons pot` - generate the `.pot` file with all translatable strings of the add-on (optional).

[1]: https://addons.nvda-project.org/files/get.php?file=volumeAdjustment
[2]: https://github.com/grisov/NVDA_Volume_Adjustment/releases
