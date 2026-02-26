# RK3588 (8GB) LLM 部署环境配置指南

**文档索引**：完整复现请按顺序参考  
[02_dependencies.md](02_dependencies.md)（依赖清单） → [03_model_acquisition.md](03_model_acquisition.md)（模型获取） → [04_run_text_llm.md](04_run_text_llm.md) / [05_run_multimodal_vlm.md](05_run_multimodal_vlm.md)（运行） → [06_benchmark_guide.md](06_benchmark_guide.md)（性能测试） → [07_feasibility_report.md](07_feasibility_report.md)（可行性报告）。

## 1. 系统基础依赖安装

在 RK3588 开发板上，首先需要安装编译 C++ Demo 所需的基础工具链和依赖库。

```bash
sudo apt update
sudo apt install -y build-essential cmake libopencv-dev
```

- `build-essential`: 包含 gcc, g++, make 等编译工具。
- `cmake`: 用于构建 C++ 工程。
- `libopencv-dev`: 用于多模态模型（如 Qwen-VL, InternVL）的图像读取和预处理。

## 2. 部署 RKLLM 运行时库

从 Rockchip 官方 SDK (rknn-llm) 中获取预编译的动态链接库，并将其放置在系统路径中，以便程序运行时能够找到。

1. 获取 `librkllmrt.so`（大语言模型核心库）与 `librknnrt.so`（视觉编码器，仅多模态需要）。  
   路径：工作区 `third_party/rknn-llm/rkllm-runtime/Linux/librkllm_api/aarch64/` 与 `third_party/rknn-llm/examples/multimodal_model_demo/deploy/3rdparty/librknnrt/Linux/librknn_api/aarch64/`。
2. 复制到系统并更新链接库缓存：

```bash
sudo cp <上述路径>/librkllmrt.so /usr/lib/
sudo cp <上述路径>/librknnrt.so /usr/lib/
sudo ldconfig
```

详细依赖与验证命令见 [02_dependencies.md](02_dependencies.md)。

## 2.1 第三方 VLM Demo（third_party submodule）

**不要直接 clone 第三方仓库到 demos/**。Qengineering 的 VLM demo（InternVL3.5-1B/2B/4B-NPU、Qwen3-VL-2B/4B-NPU）以 **git submodule** 形式放在 **`third_party/`**。

- 克隆本仓库后拉取 submodule：  
  `git submodule update --init --recursive`
- 若 `.gitmodules` 已配置但尚未注册过 submodule，需在仓库根目录执行一次（由维护者执行并提交）：  
  `git submodule add https://github.com/Qengineering/InternVL3.5-1B-NPU third_party/InternVL3.5-1B-NPU`  
  以及 2B/4B、Qwen3-VL-2B/4B 的对应命令（见 [03_model_acquisition.md](03_model_acquisition.md) 与 `third_party/` 目录结构）。  
- 模型文件统一放在工作区 **`models/`**，与 `scripts/run_vlm_benchmark.sh` 一致。

## 3. 性能模式锁定 (非常重要)

RK3588 默认采用动态调频策略（ondemand/schedutil），这会导致 LLM 推理时性能波动极大，TPS 严重下降。
在每次运行 Demo 或进行 Benchmark 测试前，**必须**将 CPU、GPU、NPU 和 DDR 锁定在最高性能模式。

请运行本工作区提供的脚本：
```bash
sudo bash ../scripts/fix_freq_rk3588.sh
```

## 4. 模型转换说明

由于 8GB 内存的限制，**严禁在 RK3588 板端进行模型转换**（极易 OOM 导致死机）。
所有的模型量化和转换（HuggingFace 格式 -> `.rkllm` 格式）必须在拥有 16GB 以上内存的 x86 PC 上，使用 `rkllm-toolkit` 完成。

转换完成后，将 `.rkllm` 文件传输到本工作区的 `models/` 目录下。
