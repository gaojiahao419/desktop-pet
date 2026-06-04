# Python 桌面宠物

这是一个 Windows Python 桌面宠物第一版。它使用 PyQt5 创建透明、无边框、始终置顶的窗口，使用 Pillow 绘制内置动态宠物。

## 安装依赖

```powershell
python -m pip install -r requirements.txt
```

## 运行

```powershell
python main.py
```

启动后会出现一个桌面宠物窗口。控制台会显示可用命令。

## 控制面板

运行 `python main.py` 后会出现两个窗口：

- 桌面宠物窗口：透明、置顶、可拖拽。
- 控制面板窗口：用于上传 MP4、调整大小、切换动作和输入对话。

控制面板功能：

- 动作素材：待机、高兴、睡觉、生气可以分别上传 MP4 素材。
- 解绑素材：单独恢复某个动作的内置绘制效果。
- 透明设置：选择背景色并调整容差。
- 大小：使用 50% 到 250% 滑块调整宠物显示大小。
- 动作：待机、开心、睡觉、生气、走动、隐藏、显示。
- 对话：输入文字后点击“说话”或“聊天”。

MP4 透明说明：

- 如果 MP4 解码后包含 Alpha 通道，程序直接使用 Alpha。
- 如果没有 Alpha，程序会按控制面板中的背景色和容差做纯色背景透明化。
- 如果透明效果不理想，调低或调高容差，或换成纯色背景更干净的视频。

## 鼠标交互

- 左键点击宠物：切换动作，不显示额外文字。
- 左键拖拽宠物：移动位置。
- 右键点击宠物：打开对话选择菜单。

## 控制台命令

```text
help
idle
happy
sleep
angry
walk
say <文本>
chat <文本>
hide
show
quit
exit
```

## 手动验收

1. 运行 `python main.py`。
2. 确认宠物窗口透明、无边框、置顶。
3. 左键点击宠物，确认动作切换且没有文字反馈。
4. 左键拖拽宠物，确认只移动位置。
5. 右键点击宠物，确认出现对话选择菜单。
6. 在控制台输入 `say 你好`，确认宠物显示文字气泡。
7. 在控制台输入 `chat 今天有点累`，确认宠物本地回复。
8. 输入 `hide` 后宠物隐藏，输入 `show` 后恢复。
9. 输入 `quit` 后程序退出。

## 自动检查

```powershell
python -m pytest -q
python -m compileall .
python -c "from main import main; print('main imports ok')"
```
