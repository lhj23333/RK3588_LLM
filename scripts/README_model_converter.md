# RK3588 LLM 模型自动下载与转换工具

本工具用于自动下载和转换大语言模型，使其可以在 RK3588 NPU 上运行。

## 功能特性

- ✅ 自动从 ModelScope / HuggingFace 下载模型
- ✅ 自动转换为 RKLLM 格式 (`.rkllm`)
- ✅ 支持多种量化方式 (W8A8, W4A16)
- ✅ 支持模型列表管理

## 支持的模型

| 模型名称 | 参数量 | 推荐量化 | 内存占用 (约) | RK3588 8GB 可行性 |
|:---|:---|:---|:---|:---|
| Qwen3-0.6B | 0.6B | W8A8 | ~1GB | ✅ 推荐 |
| Qwen3-1.7B | 1.7B | W8A8 | ~2GB | ✅ 推荐 |
| Qwen3-4B | 4B | W8A8 | ~4GB | ✅ 可行 |
| Qwen3-8B | 8B | W4A16 | ~5GB | ⚠️ 极限 |

## 环境准备

### 1. 安装依赖

```bash
# 基础依赖
pip install torch transformers modelscope

# RKLLM Toolkit (需要从 rknn-llm 安装)
pip install third_party/rknn-llm/rkllm-toolkit/packages/rkllm_toolkit-1.2.3-cp310-cp310-linux_x86_64.whl
```

### 2. 验证环境

```bash
cd scripts
python model_converter.py --list
```

## 使用方法

### 列出支持的模型

```bash
python model_converter.py --list
```

### 下载模型（不转换）

```bash
# 从 ModelScope 下载（国内推荐）
python model_converter.py --model qwen3-0.6b --download-only

# 从 HuggingFace 下载
python model_converter.py --model qwen3-0.6b --source huggingface --download-only
```

### 下载并转换模型

```bash
# 使用默认配置
python model_converter.py --model qwen3-0.6b --convert

# 指定量化类型
python model_converter.py --model qwen3-4b --quant w8a8 --convert

# 使用 CPU 转换（如果 GPU 内存不足）
python model_converter.py --model qwen3-0.6b --device cpu --convert
```

### 转换已下载的模型

如果模型已经下载，可以直接指定路径：

```bash
python model_converter.py \
  --model-path ~/.cache/modelscope/hub/Qwen/Qwen3-0.6B \
  --output ../models/qwen3-0.6b_w8a8.rkllm \
  --convert
```

## 参数说明

| 参数 | 说明 | 默认值 |
|:---|:---|:---|
| `--model` | 模型名称 | - |
| `--model-path` | 已下载的模型路径 | - |
| `--source` | 下载源 | modelscope |
| `--cache-dir` | 模型缓存目录 | ~/.cache/modelscope |
| `--convert` | 转换为 RKLLM | False |
| `--download-only` | 仅下载 | False |
| `--quant` | 量化类型 | 自动选择 |
| `--npu-cores` | NPU 核心数 | 3 |
| `--max-context` | 最大上下文 | 4096 |
| `--device` | 转换设备 | cuda |
| `--output` | 输出路径 | ../models/ |

## 部署到 RK3588

转换完成后，将 `.rkllm` 文件复制到开发板：

```bash
# 在开发板上
export LD_LIBRARY_PATH=./lib

# 运行推理
./llm_demo models/qwen3-0.6b_w8a8.rkllm 2048 4096
```

## 常见问题

### Q: 转换时内存不足？

A: 尝试使用 `--device cpu` 参数，或者增加系统交换空间：

```bash
# 创建 16GB 交换空间
sudo fallocate -l 16G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

### Q: 下载速度慢？

A: 使用 ModelScope 作为下载源（国内用户）：

```bash
python model_converter.py --model qwen3-0.6b --source modelscope --convert
```

### Q: RKLLM Toolkit 安装失败？

A: 确保 Python 版本为 3.10 或 3.11，并安装正确的 wheel 包：

```bash
# 查看 Python 版本
python --version

# 安装对应版本
pip install rkllm_toolkit-1.2.3-cp310-cp310-linux_x86_64.whl  # Python 3.10
pip install rkllm_toolkit-1.2.3-cp311-cp311-linux_x86_64.whl  # Python 3.11
```

### Q: 转换后的模型精度下降？

A: 这是量化带来的正常现象。可以尝试：
1. 使用更高的量化精度 (W8A8 比 W4A16 精度更高)
2. 提供更多校准数据
3. 调整 `optimization_level` 参数

## 文件结构

```
scripts/
├── model_converter.py      # 主脚本
├── calibration/            # 校准数据目录
│   └── data_quant.json
└── README_model_converter.md

models/                     # 输出目录
├── *.rkllm                 # 转换后的模型
└── ...
```

## 参考资料

- [RKNN-LLM 官方仓库](https://github.com/airockchip/rknn-llm)
- [Qwen3 官方文档](https://github.com/QwenLM/Qwen3)
- [RKLLM SDK 文档](../third_party/rknn-llm/doc/Rockchip_RKLLM_SDK_CN_1.2.3.pdf)