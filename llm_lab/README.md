# 本地大模型训练环境

`llm_lab` 只用于本地大模型训练实验，不属于桌宠运行时。桌宠继续使用根目录的 `requirements.txt` 和原有 Python 环境；训练代码必须使用项目内独立的 `.venv-llm` 环境，并只从 `requirements-llm.txt` 安装依赖，避免 PyTorch、Transformers 等训练依赖影响桌宠环境。

训练生成的检查点、适配器、JSON/JSONL 报告和原始数据不提交到 Git。需要保留的配置、代码和说明文件应放在对应目录中，并避开这些生成物路径。

在项目根目录使用 PowerShell 7 执行：

```powershell
& "D:\Anaconda3\Scripts\conda.exe" create --prefix ".\.venv-llm" python=3.11 -y
& ".\.venv-llm\python.exe" -m pip install --upgrade pip
& ".\.venv-llm\python.exe" -m pip install -r requirements-llm.txt
& ".\.venv-llm\python.exe" -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0))"
```

开始训练前，最后一条命令必须打印 `True` 和 NVIDIA GPU 名称；否则不要开始训练，应先修复 CUDA、驱动或 PyTorch 安装问题。
