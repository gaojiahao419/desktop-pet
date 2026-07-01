# Python 桌面宠物

这是一个 Windows 桌面宠物项目。主程序使用 PyQt5 绘制透明、无边框、始终置顶的宠物窗口；控制台使用 Electron 窗口管理 MP4 宠物素材；聊天功能可以接入本地部署的 Qwen 小模型服务，也可以在模型服务不可用时回退到内置本地回复。

## 当前功能

- 透明置顶宠物窗口，支持拖拽移动。
- 左键点击宠物：在待机、开心、生气、睡觉状态之间切换。
- 右键点击宠物：打开蓝白风格菜单，目前保留“打开对话”和“打开控制台”。
- 对话窗口跟随宠物移动，消息按用户右侧、宠物左侧的气泡形式展示。
- 聊天请求通过 `pet_ai_client.py` 调用本地模型服务；服务没开或报错时，会自动使用 `dialogue.py` 的本地预设回复。
- Electron 控制台支持上传 MP4 素材、预览素材、调整大小、调整播放速度、设置循环方式和黑底透明。
- 运行配置会保存到本地 `pet_settings.json`，方便下次启动恢复素材和参数。

## 目录说明

| 路径 | 作用 |
| --- | --- |
| `main.py` | 程序入口，负责启动 PyQt 应用、宠物窗口、控制台和聊天请求线程。 |
| `pet_window.py` | 宠物窗口、右键菜单、聊天对话框和桌面交互逻辑。 |
| `pet_ai_client.py` | 本地大模型服务客户端，负责向 `127.0.0.1:8765` 的 `/chat` 接口发送消息。 |
| `dialogue.py` | 模型服务不可用时使用的本地预设回复。 |
| `pet_animator.py` | 宠物状态和动作切换逻辑。 |
| `pet_renderer.py` | 内置宠物绘制逻辑。 |
| `video_pet_source.py` | MP4 素材加载、逐帧播放和黑底透明处理。 |
| `pet_settings.py` | 本地配置读写。 |
| `control_api.py` | 控制台和主程序之间的本地控制接口。 |
| `electron_control.py` | 启动和管理 Electron 控制台。 |
| `web_control_panel/` | 控制台前端页面。 |
| `electron_app/` | Electron 外壳。 |
| `tests/` | 自动化测试。 |

## 环境准备

建议在普通 Python 环境里运行桌面宠物，在单独的 Conda 环境里运行本地大模型服务。

桌面宠物依赖：

```powershell
python -m pip install -r requirements.txt
npm install
```

本地模型服务是另一个项目，建议继续放在：

```text
C:\ai\pet_model_lab
```

这个宠物项目不保存模型权重，也不负责训练模型。模型下载、测试、微调和 FastAPI 服务建议都放在 `C:\ai\pet_model_lab` 里维护。

## 启动顺序

先启动本地模型服务。下面命令里的 `app:app` 要和你模型项目里的 FastAPI 文件名和变量名一致：

```powershell
conda activate pet-llm
Set-Location 'C:\ai\pet_model_lab'
python -m uvicorn app:app --host 127.0.0.1 --port 8765
```

然后启动桌面宠物：

```powershell
Set-Location '<你的桌面宠物项目目录>'
python main.py
```

如果只想测试宠物界面，不启动模型服务也可以。此时聊天会走本地预设回复。

## 使用方式

- 右键宠物，点“打开对话”：打开聊天窗口。
- 在聊天窗口输入内容并发送：如果模型服务正常运行，会返回 Qwen 的回复；否则返回本地预设回复。
- 右键宠物，点“打开控制台”：打开素材和参数控制台。
- 控制台里可以为不同状态上传 MP4，调整大小、速度、循环方式和黑底透明。
- 左键拖动宠物：移动宠物位置，聊天窗口会跟随宠物重新定位。

## MP4 透明说明

- 如果 MP4 解码后自带 Alpha 通道，程序会直接使用 Alpha。
- 如果 MP4 没有 Alpha 通道，默认按普通不透明视频显示。
- 打开“黑底透明”后，接近纯黑的外部背景会在播放时变透明。
- 黑底透明不会导出新视频，只在桌面宠物播放时处理。
- 高帧率素材会按较合适的桌面显示速度播放，避免窗口明显卡顿。

## 本地配置

`pet_settings.json` 是运行时自动生成的本机配置文件，保存素材路径、大小、播放速度、循环方式和黑底透明开关。

这个文件已经加入 `.gitignore`。如果想恢复默认设置，可以关闭程序后删除它，下一次启动会重新生成。

## 自动检查

修改代码后建议先跑：

```powershell
python -m compileall main.py pet_window.py pet_ai_client.py
python -m pytest -q
```

## GitHub 上传说明

仓库只保存源码、测试和前端控制台文件，不保存本机运行数据、模型权重、用户素材和构建产物。

已经通过 `.gitignore` 排除：

- `node_modules/`：Electron 依赖目录，克隆后重新执行 `npm install`。
- `pet_settings.json`：本机宠物素材和参数配置。
- `.vscode/`：本机编辑器配置。
- `__pycache__/`、`.pytest_cache/`、`build/`、`dist/`、`artifacts/`：缓存和构建产物。
- `models/`、`data/`、`datasets/`、`checkpoints/` 和常见模型权重格式：模型相关文件建议放在独立的模型项目中。
- `*.mp4`、`*.mov`、`*.avi`、`*.mkv`、`*.webm`：本机宠物素材默认不上传。

如果以后确实要提交示例素材，建议单独放到 `examples/` 并确认授权后再上传。

## 开源协议

本项目使用 MIT License，详见 `LICENSE`。
