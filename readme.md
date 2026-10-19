# NVDA Volume Adjustment

* Author: Oleksandr Gryshchenko
* Version: 2.0
* NVDA compatibility: 2026.1 and beyond
* Installation: through the NVDA Add-on Store ([stable version][1])

Adjust the volume of every audio device and every running program separately, switch the output and default audio devices, and mute your microphones in all programs at once - all from the keyboard.

## Keyboard shortcuts
After installation, the add-on has no keyboard shortcuts. You can either:

* turn on the predefined shortcuts with the "Use default keyboard shortcuts" option in the add-on settings, or
* assign your own shortcuts to any command in the NVDA "Input gestures" dialog, in the "Volume Adjustment" category.

This document mentions the predefined shortcuts. All of them start with NVDA+Windows, so they are easy to remember and do not conflict with other commands.

## Audio sources
The add-on works with four categories of audio sources, always in this order:

1. output devices (speakers, headphones);
2. input devices (microphones, line inputs);
3. playback apps - programs that play sound;
4. recording apps - programs that record sound.

All audio sessions of a program are adjusted together, even if the program plays on several devices at once. A program that both plays and records, for example a video call, appears in both app categories.

* NVDA+Windows+Right Arrow or Left Arrow - select the next or previous audio source. The list is cyclic.
* NVDA+Windows+Control+Right Arrow or Left Arrow - jump to the first audio source of the next or previous category.
* NVDA+Windows+O, I, P or R - show or hide output devices, input devices, playback apps or recording apps. When a category is shown, the number of its sources is announced.
* NVDA+Windows+Shift+O, I, P or R - show only that category.

The last visible category cannot be hidden. The name of a category is announced when you move into it; this can be turned off in the add-on settings.

By default, the volume commands adjust the program in focus. When you select another source with the arrows, it stays selected until the focus moves to another window.

## Adjust the volume
* NVDA+Windows+Up Arrow or Down Arrow - increase or decrease the volume.
* NVDA+Windows+Home - set the maximum volume. Be careful, a sudden loud sound can damage your hearing.
* NVDA+Windows+End - set the minimum volume.
* NVDA+Windows+Escape - mute the source or restore its volume.

Lowering the volume to zero mutes the source. Muting can turn the sound off completely or only decrease the volume by a percentage; the mode is chosen in the add-on settings.

## Channels
* NVDA+Windows+Shift+Right Arrow or Left Arrow - select the next or previous channel of the selected source. Channels are numbered from 1.
* NVDA+Windows+Shift+Up Arrow or Down Arrow - increase or decrease the volume of the selected channel.
* NVDA+Windows+Shift+Home or End - set the maximum or minimum volume of the selected channel.
* NVDA+Windows+Shift+Escape - set all channels to their average volume.

The channels of programs can be adjusted only while NVDA sound split is turned off, because sound split uses the same channels. Otherwise the add-on tells you that the channels are used by sound split.

## Protecting the volume of NVDA
NVDA itself is also a playback app. Before you lower or mute its volume or one of its channels, the add-on asks for confirmation, because NVDA could become silent and Windows remembers its volume even after NVDA restarts. The warning can be turned off in the dialog itself or in the add-on settings.

## Output devices
Three groups of commands use the same keys, F1-F12, PageUp and PageDown:

* NVDA+Windows - the output device of NVDA speech and sounds;
* NVDA+Windows+Shift - the default output device of Windows;
* NVDA+Windows+Control - the default communication device of Windows.

With each group:

* F1-F12 - switch to the 1st to 12th output device. These commands are created for the output devices found when NVDA starts: a device connected later gets its own command after NVDA is restarted. A command for a device that has been disconnected announces that the device is not available.
* PageUp or PageDown - switch to the next or previous output device. These commands always use the devices available at the moment, including the ones connected later.

The commands for every single device are listed in the NVDA "Input gestures" dialog with the device names, so you can assign other shortcuts to them.

* NVDA+Windows+D - switch NVDA back to the default output device, so it follows the default device of Windows.
* NVDA+Windows+S - open the Sound dialog of Windows.

## Quick mute of microphones
NVDA+Windows+Space mutes or unmutes in Windows all microphones selected in the add-on settings, so every program gets silence: video calls, messengers, recorders and others. You do not need to remember a different shortcut in each program.

If any of the selected microphones is on, all of them are muted; otherwise all of them are unmuted. A short sound is played after muting and before unmuting, so the microphones do not record it. The microphones are never unmuted automatically when NVDA exits.

## Add-on settings
* Report the status of the sound source while switching - announce the volume or the muted state of a source or channel when it is selected.
* Announce category names while switching - announce the category when you move into it with the arrows.
* Visible categories of audio sources - the categories you switch between, the same as with NVDA+Windows+O, I, P and R.
* Volume level change step, % - how much one keypress changes the volume, from 1 to 20 percent.
* Announce the volume level in - percent, percent without the percent sign, or decibels for audio devices. Programs are always announced in percent. Decibel values come from the device and its driver, so they may sometimes look unusual, for example a narrow range or values far below zero.
* Change the volume of the current application - the volume commands adjust the program in focus.
* Hide output devices, Hide input devices, Hide processes - the items you do not want in the list of audio sources. The "Refresh" button updates the list and keeps the checked items; the "Clear" button unchecks all items and removes the ones that are no longer present.
* Mute mode - "Complete Mute" turns the sound off; "Volume Down" decreases the volume by the percentage set with the "Decrease the volume by, %" slider.
* Unmute all muted audio resources at NVDA shutdown - restore the volume of the sources muted by the add-on when NVDA exits. Only the programs running at that moment can be restored.
* Warn before lowering or muting the volume of NVDA itself - see "Protecting the volume of NVDA".
* Microphones of the quick mute - the microphones muted and unmuted with NVDA+Windows+Space.
* Use default keyboard shortcuts - turn the predefined shortcuts on or off. NVDA asks to reload the add-ons for the change to take effect.

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
