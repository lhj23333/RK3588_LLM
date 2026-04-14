# RK3588 LLM/VLM 项目完整系统依赖与组件库分析

本文档详细拆解了当前项目（包括大模型 C++ 推理 Demo、自动化 Benchmark 框架以及模型转换 Export 工具）对底层操作系统、编译工具链、动态链接库 (.so) 以及 Python 依赖的具体要求。

本指南可用于排查环境配置错误，也专为**精简环境（Minimal OS）**或**无操作系统/极简容器（Bare-metal / Scratch Container）**的未来离线部署测试提供最底层的指导。

---

## 1. 操作系统与系统级工具链 (OS & System Toolchain)

本项目主要针对 ARM64 (aarch64) 架构的 Rockchip RK3588 平台进行开发与验证。在常规的 Linux 发行版（如 Ubuntu 20.04/22.04、Debian 11/12）下需要以下系统级支持；

### 1.1 系统核心依赖
*   **指令集架构**: `aarch64` (ARM64)
*   **内核驱动**: 必须存在 `/dev/rknn` 节点（Rockchip NPU Kernel Driver），用于调度底层 NPU 算力。
*   **Root 权限（可选）**: 若您在跑分前手动执行 `fix_freq_rk3588.sh` 开启定频/性能模式，需要 `sudo` 权限与对应的 `/sys/devices/system/cpu/.../cpufreq/` 读写权限。

### 1.2 C++ 编译工具链
对于部署或二次开发 `demos/build/` 下的推理程序，必须安装：
*   **GCC / G++**: 要求支持 C++17 标准（建议版本 GCC 8.0+，常见为 GCC 9 / 11）。
*   **CMake**: 构建引擎，要求版本 `3.14+`。
*   **Make 或 Ninja**: 用于执行 Makefile 构建。
*   **pkg-config**: 解决依赖路径（用于寻找 OpenCV 等系统库）。

---

## 2. 核心运行时依赖 (Native Shared Libraries)

项目最底层依赖于 Rockchip 提供的 NPU 推理库，这些闭源共享库 (`.so`) 在运行时对系统的 glibc 和基础 POSIX 接口有硬性需求。

### 2.1 Rockchip NPU 核心动态库
部署时必须将这些文件存在于系统的动态库搜索路径中（或配置 `LD_LIBRARY_PATH`）：
*   **`librkllmrt.so`**: RKLLM 核心运行时，负责加载 `.rkllm` 模型，调度 CPU/NPU 进行 Transformer 算子的切分执行。
*   **`librknnrt.so`**: RKNN 核心运行时，用于处理 VLM 模型中 `.rknn` 格式的视觉特征提取模块 (Vision Encoder)。

### 2.2 操作系统基础库 (OS/glibc Dependencies)
通过对官方 SDK 进行 `ldd` 分析，纯净目标环境中（包括精简 Docker 或 Buildroot 系统）**必须存在**以下基础 aarch64 动态库：

| 库名称 (.so) | 功能说明 | 常见系统包/提供者 |
| :--- | :--- | :--- |
| `libc.so.6` | 基础 C 标准库 (包含各类系统调用接口抽象) | `libc6` (GNU C Library) |
| `libm.so.6` | 数学计算库核心 (浮点、矩阵底层基础) | `libc6` (GNU C Library) |
| `libpthread.so.0` | POSIX 多线程库 (极其关键，用于 NPU 异步调度与 CPU 并发) | `libc6` (GNU C Library) |
| `libdl.so.2` | 动态加载器接口 (运行时动态挂载特定底层驱动) | `libc6` (GNU C Library) |
| `libstdc++.so.6` | C++ 标准库 (STL 容器、异常控制等) | `libstdc++6` (GCC) |
| `libgcc_s.so.1` | GCC 底层运行时环境支撑 | `libgcc1` (GCC) |
| `ld-linux-aarch64.so.1`| ELF 动态链接器入口 | 系统内核 / glibc |

> **⚠️ 构建极简系统注意**:
> 如果您使用 Alpine Linux 或 Buildroot 裸机环境，**请务必注意 C 标准库的兼容性**。`librkllmrt.so` 等闭源 SDK 通常是基于 glibc 编译的。如果系统采用 `musl libc` (如 Alpine 默认)，大概率会出现 ABI 不兼容或符号找不到的严重错误。目标系统的 glibc 版本通常需要 $\ge 2.27$。

### 2.3 并行计算与第三方 C++ 库
*   **`libgomp.so.1`**: GNU OpenMP 运行时库。`librkllmrt.so` 强依赖此库进行 CPU 侧的多核并发加速（如计算未被 NPU 支持的 Softmax、RoPE 等算子）。
*   **OpenCV 4.x (仅 VLM 需求)**: 视觉语言混合模型在图像前处理（加载图片、Resize、Normalize）时依赖 OpenCV 库：
    *   `libopencv_core.so`
    *   `libopencv_imgproc.so`
    *   `libopencv_imgcodecs.so`
    *(💡 裸机优化建议：如果您在无 OS 的极简环境下难以交叉编译庞大的 OpenCV，建议修改 C++ Demo 源码，将图片读取替换为更轻量的 `stb_image` 仅头文件库。)*

---

## 3. 按模块划分的 Python 层依赖

针对项目的各个环节，Python 依赖各不相同。您可以根据实际只执行的任务，挑选需要安装的依赖：

### 3.1 自动化基准测试层 (Benchmark Framework)
如果您只打算在开发板上运行 `run_benchmark.py` 来收集性能数据，Python 环境依赖非常轻量：
*   **核心引擎**: Python 3.8+ (依赖标准库 `os`, `sys`, `subprocess`, `argparse`, `re`, `json`)
*   **解析配置包**: `PyYAML` (用于读取 `conf/models_config.yaml`)
*(💡 裸机优化建议：在严格的无操作系统环境中，可以舍弃这套 Python 测试框架，直接编写 Shell 脚本执行 `demos/build/text_llm_demo` 获取测速结果。)*

### 3.2 模型转换与导出层 (Export & Model Converter)
位于 `export/` 目录下的转换脚本（用于将 HuggingFace 模型转换为 `.rkllm` 和 `.rknn` 格式），通常可以在 **x86_64 PC / 服务器**上执行，无需在 RK3588 本地运行。其庞大的依赖如下：
*   **深度学习框架**: `torch` $\ge$ 2.0.0 (支持模型图捕捉与结构分析)
*   **基础计算**: `numpy`
*   **HuggingFace 生态**: `transformers`, `huggingface_hub` (用于加载并解析原始大模型源码与配置)
*   **张量操作**: `einops` (部分复杂 Vision 架构所需)
*   **Rockchip 专有 SDK**: `rkllm` (包含 `rkllm.api`), `rknn-toolkit2` (包含 `rknn.api`)

---

## 4. 极简环境/裸机部署核对清单 (Minimal Deployment Checklist)

当您准备脱离标准的 Ubuntu 环境，将项目移植到定制的精简嵌入式系统时，请参考以下自检流：

1.  **内核节点检查**: 确保挂载了设备树 (Device Tree) 并成功暴露了 `/dev/rknn` 接口设备，以供底层的 ioctl 调用 NPU。
2.  **构建 Sysroot 依赖包**: 从您的交叉编译工具链 (`/lib/aarch64-linux-gnu/`) 中，将上文提到的所有 `.so` 库 (特别是 `libgomp.so.1` 和 glibc 系列) 完整打包至目标文件系统。
3.  **提取静默可执行文件**: 将本项目 `demos/build/` 下编译出的纯 C++ 产物 `text_llm_demo` 提取出来，它不依赖任何 Python 环境，非常适合打进基础固件。
4.  **运行前环境变量注入**: 
    ```bash
    # 手动指定动态链接库搜索路径，确保不会缺少符号
    export LD_LIBRARY_PATH=/system/lib:/custom_path/rkllm_and_rknn_libs
    # 裸机环境建议打开日志，以应对缺少某些 VmHWM 统计接口的情况
    export RKLLM_LOG_LEVEL=1 
    
    # 彻底脱离高级框架，直接启动裸进程
    ./text_llm_demo models/Qwen-xxx.rkllm 512 4096
    ```
