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
```
