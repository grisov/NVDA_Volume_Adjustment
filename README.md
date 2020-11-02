# NVDA Volume Adjustment

* Author: Oleksandr Gryshchenko
* Version: 1.0
* Download [stable version][1]
* Download [development version][2]

Adjust the volume level of all audio devices installed in the system and each running program separately using simple keyboard shortcuts.

## Contributions
We are very grateful to everyone who made the effort to develop, translate and maintain this add-on:
* Dang Manh Cuong - Vietnamese translation;
* Cagri Dogan - Turkish translation;
* Christianlm - Italian translation;
* Cary Rowen - simplified Chinese translation;
* Stefan Banita - Polish translation.

## Change log

### Version 1.0: features of implementation
* This add-on is based on the advanced features of NVDA Unmute add-on, which were removed from the original add-on due to inconsistency with its main task.
* Added the ability to adjust the volume level of all audio devices detected in the system.
* Added keyboard shortcuts to quickly set the maximum and minimum volume levels for the selected audio source.

## Altering NVDA Volume Adjustment
You may clone this repo to make alteration to NVDA Quick Dictionary.

### Third Party dependencies
These can be installed with pip:
- markdown
- scons
- python-gettext

### To package the add-on for distribution:
1. Open a command line, change to the root of this repo
2. Run the **scons** command. The created add-on, if there were no errors, is placed in the current directory.

[1]: https://github.com/grisov/NVDA_Volume_Adjustment
[2]: https://github.com/grisov/NVDA_Volume_Adjustment
