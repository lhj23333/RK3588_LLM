# 模型转换与导出模块 (Export Module)

此模块是从 `third_party/rknn-llm/rkllm-toolkit/examples` 迁移而来的模型转换工具集合，已针对当前项目进行了环境配置、路径及调用参数适配。主要用于将 Hugging Face 格式的 LLM 和 VLM (Vision-Language Model) 模型转换为能够在 Rockchip NPU (如 RK3588) 上运行的 `.rkllm` 格式文件。

## 环境准备

在开始转换之前，请确保您的系统中已安装了 Rockchip 的 `rkllm-toolkit` Python 工具包。
详细的依赖安装步骤请参考项目根目录下的文档：`docs/02_dependencies.md` 或者 RKNN 官方文档。

> ⚠️ 注意: 模型转换过程强烈建议在 x86 架构的 PC 宿主机（带内存 > 32GB）上执行，因为转换过程需要加载完整的模型权重和占用较多内存，RK3588 开发板可能内存不足。

## 目录结构

*   `rkllm/`: 包含用于纯文本大语言模型 (Text LLM) 转换及量化数据生成的脚本。
*   `vlm/`: 包含用于视觉-语言大模型 (Vision-Language Model, VLM) 转换及图像特征抽取的脚本。

## 1. 纯文本模型 (Text LLM) 转换流程

### 步骤一：准备量化校准数据集

量化过程需要一个小规模的数据集进行校准，以减少量化带来的精度损失。

```bash
cd export/rkllm
python generate_data_quant.py -m /path/to/huggingface/model/dir -o ./data_quant.json
```

**参数说明:**
*   `-m, --model-dir`: 下载到本地的 Hugging Face 模型目录路径。
*   `-o, --output-file`: 输出的量化数据集 JSON 文件路径（默认为 `./data_quant.json`）。

你可以根据模型特点修改 `generate_data_quant.py` 内部的 `input_text`，提供更贴合您使用场景的校准样本。

### 步骤二：转换为 RKLLM 格式

在拥有校准数据集之后，可以执行转换并量化：

```bash
python export_file.py -m /path/to/huggingface/model/dir -d ./data_quant.json -t RK3588 -q w8a8
```

**核心参数说明:**
*   `-m, --model_path`: 本地 Hugging Face 格式模型目录路径（必填）。
*   `-d, --dataset`: 用于量化校准的 JSON 文件（默认为 `data_quant.json`）。
*   `-t, --target_platform`: 目标平台，如 `RK3588`, `RK3576`（默认为 `RK3588`）。
*   `-q, --quantized_dtype`: 量化数据类型，可选 `w8a8`（普通量化）或 `w4a16`（默认为 `w8a8`）。
*   `-o, --output_path`: （可选）自定义输出模型路径。默认在当前目录生成对应的 `.rkllm` 文件。

转换成功后，将在当前目录或指定输出路径生成如 `Qwen3-0.6B_w8a8_RK3588.rkllm` 的模型文件。

## 2. 视觉-语言模型 (VLM) 转换流程

视觉-语言大模型 (VLM) 的转换流程比纯文本模型更为复杂，需要分别处理视觉编码器和语言模型部分。整个转换流程分为以下 **三个步骤**：

### 步骤一：将 Vision 视觉模型部分导出为 ONNX

视觉模型本质上是一个传统的图像编码器 (如 ViT)，需要先从 Hugging Face 的完整多模态模型中剥离出来，并转换为 ONNX 格式。

**相关文件:** `export_vision.py` (以及特定模型的 `export_vision_qwen2.py` 等)

**过程说明:**
- 代码中定义了类似 `qwen2_5_vl_3b_vision`、`minicpm_v_2_6_vision` 等包装类 (Wrapper Class)。这些类提取了原模型中的 visual/vpm (视觉编码器) 以及图像特征投影层 (Projector/Connector)。
- 脚本会随机生成对应 height 和 width 的 Tensor 作为假输入，然后通过 `torch.onnx.export` 剥离出计算图，最终导出保存为 `onnx/xxx_vision.onnx` 文件。

```bash
cd export/vlm
python export_vision.py --path /path/to/vlm/model/dir --model_name qwen2_5-vl-3b --batch_size 1 --height 448 --width 448
```

**核心参数说明:**
*   `--path`: Hugging Face 模型本地路径。
*   `--model_name`: 模型名称 (如 `qwen2_5-vl-3b`, `qwen2-vl-2b` 等)。
*   `--batch_size`: 批处理大小 (默认 1)。
*   `--height`, `--width`: 输入图像分辨率 (如 448x448)。

### 步骤二：将 Vision ONNX 模型转换为 RKNN 格式

得到视觉模型的 ONNX 后，使用 Rockchip 的 `rknn-toolkit2` 将其编译为能在 NPU 上运行的 `.rknn` 模型。

**相关文件:** `export_vision_rknn.py`

**过程说明:**
1. 引入 `from rknn.api import RKNN`。
2. 根据不同模型 (如 qwen2, internvl3) 配置特定的图像归一化参数 (mean_value, std_value)。
3. 配置目标平台 (`target_platform='rk3588'`) 并加载刚才的 ONNX (`rknn.load_onnx`)。
4. 调用 `rknn.build(do_quantization=False)`（视觉通常以 FP16 运行，默认不开启整型量化）并最终通过 `rknn.export_rknn` 导出 `.rknn` 格式文件。

```bash
python export_vision_rknn.py --path ./onnx/qwen2_5-vl-3b_vision.onnx --model_name qwen2_5-vl-3b --target-platform rk3588 --batch_size 1 --height 448 --width 448
```

**核心参数说明:**
*   `--path`: 上一步生成的 ONNX 文件路径。
*   `--model_name`: 模型名称 (需与步骤一一致)。
*   `--target-platform`: 目标平台 (`rk3588`)。
*   `--batch_size`, `--height`, `--width`: 与步骤一保持一致。

### 步骤三：将 Text LLM 模型转换为 RKLLM 格式

这部分处理语言模型部分，通过 `rkllm-toolkit` 直接将 Hugging Face 权重转化为 `.rkllm`。

**相关文件:** `export_rkllm.py`

**过程说明:**
1. 引入 `from rkllm.api import RKLLM`。
2. 使用 `llm.load_huggingface(model=modelpath)` 直接加载原始的 Hugging Face 模型目录。RKLLM 内部已经针对主流 VLM 做了结构解析，会自动提取其中的语言模型部分。
3. 通过 `llm.build(...)` 设置目标平台、NPU 核心数、量化类型 (如 w8a8)。为了量化效果，还需要传入一个较小的校准数据集 (`dataset='data_quant.json'`)。
4. 编译完成后，调用 `llm.export_rkllm(...)` 保存为 `.rkllm` 文件。

```bash
python export_rkllm.py --path /path/to/vlm/model/dir --target-platform rk3588 --quantized_dtype w8a8 --dataset ./data_quant.json
```

**核心参数说明:**
*   `--path`: Hugging Face 模型本地路径 (同步骤一)。
*   `--target-platform`: 目标平台 (`rk3588`)。
*   `--quantized_dtype`: 量化类型 (`w8a8`, `w4a16` 等)。
*   `--dataset`: 用于量化校准的 JSON 文件。

### 完整转换示例 (以 Qwen2.5-VL 为例)

假设目标平台为 RK3588，完整的三步转换命令如下：

```bash
# Step A: 转换视觉部分 (Vision -> ONNX -> RKNN)
python export_vision.py --path /path/to/Qwen2.5-VL-3B-Instruct --model_name qwen2_5-vl-3b --batch_size 1 --height 448 --width 448
python export_vision_rknn.py --path ./onnx/qwen2_5-vl-3b_vision.onnx --model_name qwen2_5-vl-3b --target-platform rk3588 --batch_size 1 --height 448 --width 448

# Step B: 转换语言模型部分 (Text LLM -> RKLLM)
python export_rkllm.py --path /path/to/Qwen2.5-VL-3B-Instruct --target-platform rk3588 --quantized_dtype w8a8 --dataset ./data_quant.json
```

转换成功后，你将得到以下文件：
- `xxx_vision.rknn`: 视觉编码器模型 (用于 NPU 推理)
- `xxx.rkllm`: 语言模型 (用于 NPU 推理)

> ⚠️ **注意**: 部分 VLM 的转换可能还需要额外准备图像预处理相关的配置文件 (如 `export_vision_qwen2.py` 中针对特定模型的包装类实现)。请根据实际使用的模型参考对应脚本内的实现细节。

## 模型使用

导出的 `.rkllm` 文件可放置在项目根目录的 `models/` 文件夹下，然后使用项目提供的 C++ demo 脚本或 `run_benchmark.py` 进行运行和基准测试。
