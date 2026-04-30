# RK3588 LLM & VLM Workspace

本仓库旨在探索与记录在 **Rockchip RK3588** 平台上，利用 RKLLM 与 RKNN 运行时部署纯文本大语言模型 (LLM) 和视觉语言多模态大模型 (VLM) 的完整流程。项目中包含底层 C++ 推理 Demo 与自动化 Benchmark 框架。

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
│   ├── final_report.md       # 最终生成的性能、显存综合报告 (含 OOM 分析)
│   └── videos/               # Benchmark / Demo 运行录屏 (MP4)
├── models/                   # 用户放置转换后权重文件 (.rkllm / .rknn) 的目录
├── results/                  # 测试结果生成输出目录
│   └── benchmark_report.md   # 自动生成的 Benchmark 分数表
├── scripts/                  # 辅助 Shell 脚本
│   ├── llm/build_text_llm_demo.sh  # 编译文本 LLM C++ Demo
│   ├── vlm/build_vlm_demo.sh       # 编译多模态 VLM C++ Demo
│   ├── fix_freq_rk3588.sh          # 锁定 CPU/DDR/NPU/GPU 高性能模式（测试前建议执行）
│   └── monitor_perf.sh             # 可选性能监控辅助脚本
└── third_party/              # Git 外部依赖子模块 (RKLLM SDK 与 VLM 源码)
    ├── rknn-llm              
    └── (InternVL / Qwen-VL NPU Repos)
```

---

## 2. 硬件测试环境 (Test Environment)

*   **设备 (Board)**: Rockchip **RK3588** 开发板
*   **物理内存 (RAM)**: **16 GB** LDDR5x
*   **操作系统 (OS)**: **Debian GNU/Linux 12 (bookworm)**，aarch64
*   **内核**: Linux **6.1.84-8-rk2410**
*   **核心算力**: NPU **6.0 TOPS**（NPU 三核并发）
*   **性能保障**: 执行测试前建议运行 `sudo bash scripts/fix_freq_rk3588.sh`，将 CPU、DDR、NPU、GPU 置于 `performance` governor。

---

## 3. 测试结果快速预览 (Benchmark Preview)

以下数据来源于 `run_benchmark.py` 在 **上述 RK3588（16GB）** 环境上的运行结果，涵盖 **三核 (3-Core)** 与 **单核 (1-Core)** NPU 调度的性能对比。完整表格与说明见 [docs/final_report.md](docs/final_report.md) 与 [results/benchmark_report.md](results/benchmark_report.md)。

### 3.1 多核 NPU 性能 (3-Core)

#### 纯文本大模型 (Text-only LLM)

| 模型名称 (Model) | Context | 初始显存 (Weights+KV) | Runtime Buffer | 峰值显存 (Peak DRAM) | 生成速度 (TPS) |
| :--- | :---: | :--- | :--- | :--- | :---: |
| **Qwen1.5-7B** | 4096 | ~7.94 GB | ~10 MB | ~7.95 GB | **3.81** |
| **Qwen1.5-14B** | 4096 | ~14.76 GB | ~128 MB | ~14.83 GB | **2.04** |
| **Qwen2-1.5B** | 4096 | ~1.76 GB | ~4.8 MB | ~1.77 GB | **14.11** |
| **Qwen2-7B** | 4096 | ~7.04 GB | ~9 MB | ~7.05 GB | **4.05** |
| **Qwen2.5-7B** | 4096 | ~7.04 GB | ~19 MB | ~7.06 GB | **4.07** |
| **Qwen3-0.6B** | 4096 | ~1.24 GB | ~2.5 MB | ~1.24 GB | **26.78** |
| **Qwen3-1.7B**   | 4096 | ~1.52 GB | ~10.4 MB | ~1.53 GB | **17.65** |
| **Qwen3-4B**   | 4096 | ~4.71 GB | ~8.4 MB | ~4.72 GB | **6.29** |
| **Qwen3-8B** | 4096 | ~7.67 GB | ~9 MB | ~7.68 GB | **3.77** |
| **Qwen3-14B** | 4096 | ~14.78 GB | ~125 MB | ~14.85 GB | **2.01** |
| **Llama2-7B** | 4096 | ~7.32 GB | ~10 MB | ~7.33 GB | **3.93** |
| **Llama2-13B** | 4096 | ~14.65 GB | ~90 MB | ~14.70 GB | **2.09** |
| **Llama3-8B** | 4096 | ~7.57 GB | ~12 MB | ~7.57 GB | **3.80** |
| **InternLM2-7B** | 4096 | ~7.35 GB | ~13 MB | ~7.36 GB | **3.82** |

#### 视觉语言大模型 (Vision-Language VLM)

| 模型名称 (Model) | Context | 初始显存 (Weights+KV) | Runtime Buffer | 峰值显存 (Peak DRAM) | 生成速度 (TPS) |
| :--- | :---: | :--- | :--- | :--- | :---: |
| **Qwen3-VL-8B** | 4096 | ~7.71 GB | ~0.94 GB | ~8.65 GB | **3.61** |
| **Qwen3-VL-2B**    | 4096 | ~2.28 GB | ~0.85 GB | ~3.13 GB | **13.17** |
| **Qwen3-VL-4B**    | 4096 | ~4.56 GB | ~0.88 GB | ~5.44 GB | **6.30** |
| **Qwen2.5-VL-7B** | 4096 | ~7.08 GB | ~1.51 GB | ~8.58 GB | **3.90** |
| **InternVL3.5-1B** | 4096 | ~1.84 GB | ~0.65 GB | ~1.89 GB | **27.39** |
| **InternVL3.5-2B** | 4096 | ~2.93 GB | ~0.67 GB | ~2.95 GB | **12.79** |
| **InternVL3.5-4B** | 4096 | ~4.56 GB | ~0.70 GB | ~5.27 GB | **6.33** |
| **InternVL3.5-8B** | 4096 | ~7.50 GB | ~0.88 GB | ~8.40 GB | **3.56** |

### 3.2 单核 NPU 性能 (1-Core)

#### 纯文本大模型 (Text-only LLM)

| 模型名称 (Model) | Context | 初始显存 (Weights+KV) | Runtime Buffer | 峰值显存 (Peak DRAM) | 生成速度 (TPS) |
| :--- | :---: | :--- | :--- | :--- | :---: |
| **Qwen1.5-7B** | 4096 | ~7.90 GB | ~14 MB | ~7.91 GB | **1.49** |
| **Qwen1.5-14B** | 4096 | ~14.80 GB | ~133 MB | ~14.87 GB | **0.80** |
| **Qwen2-1.5B** | 4096 | ~1.74 GB | ~1.3 MB | ~1.74 GB | **6.42** |
| **Qwen2-7B** | 4096 | ~6.99 GB | ~15 MB | ~7.00 GB | **1.52** |
| **Qwen2.5-7B** | 4096 | ~6.99 GB | ~16 MB | ~7.00 GB | **1.53** |
| **Qwen3-0.6B** | 4096 | ~1.17 GB | ~4.2 MB | ~1.18 GB | **13.87** |
| **Qwen3-1.7B**   | 4096 | ~1.49 GB | ~6.0 MB | ~1.50 GB | **7.61** |
| **Qwen3-4B**   | 4096 | ~4.59 GB | ~7.2 MB | ~4.60 GB | **2.57** |
| **Qwen3-8B** | 4096 | ~7.62 GB | ~11 MB | ~7.63 GB | **1.42** |
| **Qwen3-14B** | 4096 | ~14.81 GB | ~132 MB | ~14.89 GB | **0.76** |
| **Llama2-7B** | 4096 | ~7.28 GB | ~14 MB | ~7.29 GB | **1.59** |
| **Llama2-13B** | 4096 | ~14.65 GB | ~84 MB | ~14.71 GB | **0.82** |
| **Llama3-8B** | 4096 | ~7.52 GB | ~15 MB | ~7.53 GB | **1.44** |
| **InternLM2-7B** | 4096 | ~7.30 GB | ~11 MB | ~7.31 GB | **1.46** |

#### 视觉语言大模型 (Vision-Language VLM)

| 模型名称 (Model) | Context | 初始显存 (Weights+KV) | Runtime Buffer | 峰值显存 (Peak DRAM) | 生成速度 (TPS) |
| :--- | :---: | :--- | :--- | :--- | :---: |
| **Qwen3-VL-2B**    | 4096 | ~2.26 GB | ~0.65 GB | ~2.91 GB | **5.74** |
| **Qwen3-VL-4B**    | 4096 | ~4.63 GB | ~0.65 GB | ~5.28 GB | **2.58** |
| **Qwen3-VL-8B** | 4096 | ~7.65 GB | ~0.96 GB | ~8.61 GB | **1.42** |
| **InternVL3.5-1B** | 4096 | ~1.22 GB | ~0.66 GB | ~1.88 GB | **14.28** |
| **InternVL3.5-2B** | 4096 | ~2.27 GB | ~0.66 GB | ~2.93 GB | **5.77** |
| **InternVL3.5-4B** | 4096 | ~4.63 GB | ~0.65 GB | ~5.28 GB | **2.59** |
| **InternVL3.5-8B** | 4096 | ~7.44 GB | ~0.90 GB | ~8.32 GB | **1.46** |
| **Qwen2.5-VL-7B** | 4096 | ~7.02 GB | ~1.50 GB | ~8.52 GB | **1.53** |

### 3.3 Benchmark 演示录屏

#### 纯文本 LLM（Text-only）

**Qwen3-0.6B**

https://github.com/user-attachments/assets/af16fb17-a7df-42b5-8600-8a132316096a

**Qwen3-1.7B**

https://github.com/user-attachments/assets/7120518f-9d32-4bf3-83cd-714c7f57780b

**Qwen3-4B**

https://github.com/user-attachments/assets/a611d801-2550-4a1d-b05b-d30dc4f078a5

#### 视觉语言 VLM（InternVL3.5）

**InternVL3.5-1B**

https://github.com/user-attachments/assets/1cd25e22-e058-437b-8468-0f0d688c2660

**InternVL3.5-2B**

https://github.com/user-attachments/assets/8faf914f-6477-41d9-82a6-57e9c180ebfb

**InternVL3.5-4B**

https://github.com/user-attachments/assets/b5008f1d-bb55-4774-a4d7-888e10e7e306

---

## 4. 快速开始 (Quick Start)

### 第一步：克隆仓库与拉取子模块
由于依赖 Rockchip 的 SDK 和第三方代码，请务必递归克隆：
```bash
git clone https://github.com/lhj23333/RK3588_LLM.git
cd RK3588_LLM

git submodule update --init --recursive
```
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
模型转换耗内存大，**不建议在内存紧张的板端（尤其 8GB 机型）上直接转换**。请在 x86_64 PC 或充足内存的主机上完成转换，或下载已转换的 `.rkllm` / `.rknn` 文件，放入项目根目录下的 `models/` 文件夹中。

### 第五步：运行自动化基准测试 (Benchmark)
**这是本项目最核心的入口！**
它会加载 YAML 配置，拉起对应的底层 C++ 程序进行压力测试与内存探测：

```bash
# （推荐）跑分前先手动锁定高性能模式，保证结果稳定
sudo bash scripts/fix_freq_rk3588.sh

# 启动所有模型的一键测试
python3 run_benchmark.py --model all

# 启动 GUI 可视化测试
python3 run_benchmark.py --gui

# 或者只测试指定的几个模型
python3 run_benchmark.py --model qwen3-0.6b-text internvl3.5-1b-npu
```
跑分完成后，报告将自动保存在 `results/benchmark_report.md` 中。

---

## 5. 核心文档指引 (Documentation Index)

如果您需要进行深度定制或遇到问题，请查阅 `docs/` 目录下的详细指南：

| 文档名称 | 详细说明 |
| :--- | :--- |
| 📖 [**benchmark_guide.md**](docs/benchmark_guide.md) | **基准测试指南**。教你如何修改配置 `models_config.yaml`，添加自定义模型到测试队列，以及排查自动化测试失败的问题。 |
| 🗜️ [**dependencies.md**](docs/dependencies.md) | **底层系统依赖剖析**。极其详细地记录了 C++ 链接库 (.so) 与系统要求。如果您想在 **无 OS (裸机)** 或精简 Docker 中运行模型，请看这里。 |
| 📊 [**final_report.md**](docs/final_report.md) | **跑分大报告**。详细归纳了单核/多核 NPU 性能数据|

---

## 声明 (License & Disclaimer)

*   底层的 `librkllmrt.so` 和 `librknnrt.so` 闭源组件版权及使用许可归 Rockchip 所有。
*   本项目仅用于在 RK3588 平台进行大语言模型推理性能的基准测试、研究与学习交流。
