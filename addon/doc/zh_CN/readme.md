# NVDA Unmute


* 作者： Oleksandr Gryshchenko
* 版本： 1.3
* 下载[稳定版][1]
* 下载[开发版][2]

当 NVDA 启动时，此插件会检查 Windows 系统声音状态，如果已静音，则将其打开。
该插件还可以检查语音合成器驱动程序的状态。
如果初始化存在问题，则尝试恢复，该合成器是在 NVDA 设置中所指定的合成器。
另一个功能是能够使用便捷的键盘快捷键分别调整主音量和每个正在运行中进程的音量。

## 插件设置对话框
插件设置对话框中提供以下选项：

1. 插件设置对话框中的第一个滑块“恢复到的音量级别”，如果系统音量被静音或低于相应级别，则在 NVDA 启动时恢复到该音量。

2. 如果音量小于或等于以下值，则增大音量，
如果音量小于此处指定的值，则下次启动NVDA时音量将增大。
如果音量大于此处指定的值，则当您重新启动 NVDA 时，不调整系统音量。
当然，如果系统音量被静音，则重新启动 NVDA 时无论如何都会自动恢复。

3. 尝试初始化语音合成器驱动程序。
仅当在 NVDA 启动且检测到语音合成器驱动程序尚未初始化时，才尝试该操作。

4. 尝试次数，在这里，您可以指定尝试重新初始化语音合成器驱动程序的次数。
值为 0 表示无限次尝试，直到完成该过程。

5. 成功恢复音量后播放声音。

## 调整音量
此插件可以分别调整主音量和每个正在运行中进程的音量。
若使用该功能，请使用键盘快捷键 NVDA + Windows + 箭头键。
该功能的作用类似于NVDA的语音设置。使用左右箭头选择设备或应用程序。然后使用向上和向下箭头调整所选音频源的音量。
如果您将某个程序的音量降低到 零后，再次按下向下箭头，则此音频源将被静音。

注意： 音频源列表取决于正在运行的应用程序，是动态更改的。

## 升级日志

### 1.3版
* 增加了控制主音量的功能，还可分别针对每个正在运行的应用程序进行控制；
* 更新了越南语的翻译（感谢 Dang Manh Cuong）；
* 添加了土耳其语的翻译（感谢 Cagri Dogan）；
* 添加了意大利语的翻译（感谢 Christianlm）；
* 更新了乌克兰语的翻译；
* 更新了自述文件。

### 1.2版
* 使用了 **Core Audio Windows API** 以代替 **Windows Sound Manager**；
* 添加了通过插件成功打开音频后播放声音；

### 1.1版
* 添加了插件设置对话框；
* 更新了乌克兰语翻译。

### 1.0.1版
* 在语音合成器初始化失败时，反复尝试恢复语音合成器；
*  Dang Manh Cuong添加了越南语的翻译；
* 增加了乌克兰语的翻译。

### 1.0版
实现插件特性，该插件使用了第三方模块Windows Sound Manager。


## Altering NVDA Unmute
You may clone this repo to make alteration to NVDA Unmute.

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
