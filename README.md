# RK3588 LLM & VLM Workspace

本仓库旨在探索与记录在 **Rockchip RK3588 (8GB 内存)** 平台上，利用 RKLLM 与 RKNN 运行时部署纯文本大语言模型 (LLM) 和视觉语言多模态大模型 (VLM) 的完整流程。项目中包含了底层的 C++ 推理 Demo，模型导出转换工具，以及自动化的 Benchmark 性能评估框架。

---

## 1. 项目结构 (Project Structure)

```text
rk3588_llm_workspace/
├── README.md                 # 项目介绍与快速开始指南
├── run_benchmark.py          # 自动化性能测试的主入口脚本
├── benchmark/                # Python 编写的 Benchmark 调度、测试与内存统计引擎
├── conf/
│   └── models_config.yaml    # Benchmark 所用的模型测试用例配置文件
├── demos/                    # 纯 C++ 的 LLM/VLM 推理 Demo 源码与编译产物
│   └── build/                # 存放编译好的各种 Demo 可执行文件
├── docs/                     # 核心文档与技术细节指引
│   ├── benchmark_guide.md    # 自动化跑分框架使用说明
│   ├── dependencies.md       # 系统级极简部署与底层 `.so` 库依赖分析
│   ├── export.md             # 模型转换与导出说明
│   └── final_report.md       # 最终生成的性能、显存综合报告 (含 OOM 分析)
├── export/                   # 模型转换工具包 (HuggingFace -> RKLLM/RKNN)
│   ├── rkllm/                # 文本模型转换脚本
│   └── vlm/                  # 视觉语言模型转换脚本
├── models/                   # 用户放置转换后权重文件 (.rkllm / .rknn) 的目录
├── results/                  # 测试结果生成输出目录
│   └── benchmark_report.md   # 自动生成的 Benchmark 分数表
├── scripts/                  # 辅助 Shell 脚本
│   ├── build_text_llm_demo.sh # 编译文本 LLM C++ Demo
│   ├── build_vlm_demo.sh      # 编译多模态 VLM C++ Demo
│   └── fix_freq_rk3588.sh     # 锁定 CPU/NPU 高性能模式 (测试前必跑)
└── third_party/              # Git 外部依赖子模块 (RKLLM SDK 与 VLM 源码)
    ├── rknn-llm              
    └── (InternVL / Qwen-VL NPU Repos)
```

---

## 2. 硬件测试环境 (Test Environment)

*   **设备 (Board)**: Rockchip RK3588 开发板
*   **物理内存 (RAM)**: 8 GB LPDDR4x/5
*   **操作系统 (OS)**: Ubuntu 20.04 (aarch64) 或兼容 Linux 
*   **核心算力**: 6.0 TOPS (NPU 三核并发)
*   **性能保障**: 执行测试前必须通过 `sudo bash scripts/fix_freq_rk3588.sh` 将设备锁定为最高性能定频模式。

---

## 3. 测试结果快速预览 (Benchmark Preview)

以下数据来源于 `run_benchmark.py` 在 RK3588 (8GB) 真实开发板上的运行结果，摘录了 3核心 NPU 多核调度下的最佳性能。

*注：受限于 8GB 物理内存，目前安全运行上限在 **4B 参数级别**，7B及以上模型均存在 OOM。详细内容与单核对比分析请查阅 [docs/final_report.md](docs/final_report.md)*。

### 3.1 纯文本大模型 (Text-only LLM)

| 模型名称 (Model) | 显存初始占用 (Weights+KV) | 运行峰值显存 (Peak DRAM) | 生成速度 (Generate TPS) |
| :--- | :--- | :--- | :--- |
| **Qwen3-0.6B** | ~1.23 GB | ~1.24 GB | **26.78** tokens/s |
| **Qwen3-1B**   | ~1.52 GB | ~1.53 GB | **17.65** tokens/s |
| **Qwen2-1.5B** | ~1.76 GB | ~1.77 GB | **14.11** tokens/s |
| **Qwen3-4B**   | ~4.71 GB | ~4.72 GB | **6.29** tokens/s |

### 3.2 视觉语言大模型 (Vision-Language VLM)

| 模型名称 (Model) | 显存初始占用 (Weights+KV) | 运行峰值显存 (Peak DRAM) | 生成速度 (Generate TPS) |
| :--- | :--- | :--- | :--- |
| **InternVL3.5-1B** | ~1.84 GB | ~1.89 GB | **27.39** tokens/s |
| **Qwen3-VL-2B**    | ~2.28 GB | ~3.13 GB | **13.17** tokens/s |
| **InternVL3.5-2B** | ~2.93 GB | ~2.95 GB | **12.79** tokens/s |
| **InternVL3.5-4B** | ~4.56 GB | ~5.27 GB | **6.33** tokens/s |
| **Qwen3-VL-4B**    | ~4.56 GB | ~5.44 GB | **6.30** tokens/s |

---

## 4. 快速开始 (Quick Start)

### 第一步：克隆仓库与拉取子模块
由于依赖 Rockchip 的 SDK 和第三方代码，请务必递归克隆：
```bash
git clone --recurse-submodules <repository_url> RK3588_LLM
cd RK3588_LLM
```
*(如果已经 clone 但忘记加参数，可执行：`git submodule update --init --recursive`)*

### 第二步：安装基础依赖并设置环境变量
确保拥有 C++ 构建环境与 OpenCV (VLM 必须)：
```bash
sudo apt update
sudo apt install -y build-essential cmake libopencv-dev
```
本框架自动接管 Python 环境库链接，但如果您需要单独运行二进制，可执行：
```bash
export LD_LIBRARY_PATH="third_party/rknn-llm/rkllm-runtime/Linux/librkllm_api/aarch64:$LD_LIBRARY_PATH"
```

### 第三步：编译 C++ 推理 Demo
构建纯文本 LLM 推理程序：
```bash
bash scripts/llm/build_text_llm_demo.sh
# 产物输出于: demos/build/text_llm_demo
```
构建视觉语言 VLM 程序：
```bash
bash scripts/vlm/build_vlm_demo.sh all
# 产物输出于: demos/build/*_VLM_NPU
```

### 第四步：准备模型
请勿在 8GB 的板端直接转换模型（必 OOM）。请在 PC 上完成转换，或下载已转换的 `.rkllm` / `.rknn` 文件，并将它们统一放入项目根目录下的 `models/` 文件夹中。

### 第五步：运行自动化基准测试 (Benchmark)
**这是本项目最核心的入口！**
它会自动开启定频模式，加载 YAML 配置，拉起对应的底层 C++ 程序进行压力测试与内存探测：

```bash
# 启动所有模型的一键测试
sudo python3 run_benchmark.py --model all

# 或者只测试指定的几个模型
sudo python3 run_benchmark.py --model qwen3-0.6b-text internvl3.5-1b-npu
```
跑分完成后，报告将自动保存在 `results/benchmark_report.md` 中。

---

## 5. 核心文档指引 (Documentation Index)

如果您需要进行深度定制或遇到问题，请查阅 `docs/` 目录下的详细指南：

| 文档名称 | 详细说明 |
| :--- | :--- |
| 📖 [**benchmark_guide.md**](docs/benchmark_guide.md) | **基准测试指南**。教你如何修改配置 `models_config.yaml`，添加自定义模型到测试队列，以及排查自动化测试失败的问题。 |
| 🗜️ [**dependencies.md**](docs/dependencies.md) | **底层系统依赖剖析**。极其详细地记录了 C++ 链接库 (.so) 与系统要求。如果您想在 **无 OS (裸机)** 或精简 Docker 中运行模型，请看这里。 |
| 📊 [**final_report.md**](docs/final_report.md) | **最终跑分大报告**。详细归纳了所有单核/多核 NPU 性能数据，并包含了几十个 7B/14B 大模型的内存溢出 (OOM) 失败情况分析。 |
| 🔄 [**export.md**](docs/export.md) | **模型转换导出**。*(如果文档存在)* 教您如何在 PC 端环境利用深度学习框架将 HuggingFace 模型转换为 RKNN/RKLLM 格式。 |

---

## 声明 (License & Disclaimer)

*   底层的 `librkllmrt.so` 和 `librknnrt.so` 闭源组件版权及使用许可归 Rockchip 所有。
*   本项目仅用于在 RK3588 平台进行大语言模型推理性能的基准测试、研究与学习交流。