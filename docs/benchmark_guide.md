# RK3588 LLM/VLM 基准测试 (Benchmark) 指导文档

本文档为您提供了一套在 Rockchip RK3588 平台上快速运行大语言模型 (LLM) 和视觉语言模型 (VLM) 性能基准测试的标准操作流程。

---

## 1. 概述 (Overview)

本项目的基准测试框架通过统一的 Python 入口脚本 `run_benchmark.py` 进行调度，支持批量测试、NPU 环境变量配置，并自动收集性能指标（Init DRAM, Runtime Buffer, Generate TPS 等）生成 Markdown 格式的测试报告。

核心架构与目录构成：
*   **入口脚本**: `run_benchmark.py`
*   **配置中心**: `conf/models_config.yaml`
*   **报告输出**: `results/benchmark_report.md`
*   **底层执行器**: 位于 `demos/build/` 下编译好的 C++ 执行程序

---

## 2. 前置准备 (Prerequisites)

在运行 Benchmark 之前，请确保以下环境和文件均已准备就绪：

1.  **编译 Demo 二进制文件**: 确保您已经通过 C++ / CMake 完成了执行程序的编译。
    *   纯文本模型执行器：`demos/build/text_llm_demo` 等。
    *   *注：具体路径需要与 `models_config.yaml` 中配置的 `binary_path` 一致。*
2.  **准备量化模型**: 请将转换好的 `.rkllm` (及相关 `.rknn`) 权重文件放置在项目根目录的 `models/` 文件夹下。
3.  **安装 Python 依赖**: 确保系统已安装 Python 3 环境。
4.  **可选：锁定高性能模式（推荐）**: 为了保证测试数据的稳定性，建议在跑分前手动运行 `sudo bash scripts/fix_freq_rk3588.sh`，开启 CPU/DDR/NPU/GPU 的性能（定频）模式。

---

## 3. 配置文件说明 (Configuration)

基准测试的测试用例统一由 `conf/models_config.yaml` 管理。
您可以在此文件中任意添加或注销需要测试的模型用例。

**配置示例**:
```yaml
models:
  qwen3-0.6b-text:                     # 模型的唯一标识名称
    type: "text"                       # 模型类型 ("text" 或 "vlm")
    binary_path: "demos/build/text_llm_demo" # 对应的 C++ 推理程序路径
    model_path: "models/Qwen3-0.6B_W8A8_RK3588.rkllm" # 模型权重路径
    max_new_tokens: 512                # 生成的最大 token 数
    max_context_len: 4096              # 最大上下文长度
```
*   **添加新模型**：直接在 `models:` 节点下新增模型字典即可。
*   **排查 OOM 问题**：如果某个模型在您的设备上频繁导致显存溢出，可以直接在配置文件中将其注释掉（例如 `internlm2-7b-text: # OOM`），避免中断整体的批量自动化测试流程。

---

## 4. 运行测试 (Running Benchmark)

回到项目根目录，使用 Python 执行基准测试脚本。脚本会自动接管 `LD_LIBRARY_PATH` 环境变量，无需您手动配置链接库。

### 4.1 运行所有配置的模型
命令将遍历并测试 `conf/models_config.yaml` 中启用的所有模型：
```bash
python run_benchmark.py --model all
```

### 4.2 运行指定的单模型
支持指定一个具体的模型名称（必须与 yaml 配置文件中定义的 key 完全一致）进行针对性测试：
```bash
# 测试单个模型
python run_benchmark.py --model qwen3-0.6b-text
```

---

## 5. 查看测试报告 (Benchmark Results)

测试程序运行结束后，它会调用 Benchmark 框架内的 `reporter.py` 进行数据统计与分析，最终报告会自动生成并保存在：

👉 **`results/benchmark_report.md`**

**报告涵盖的主要指标包括：**
*   **Init DRAM (Weights+KV-Cache)**: 模型权重和 KV Cache 初始化时消耗的显存（MB）。
*   **Runtime Buffer DRAM**: 推理过程中算子调度和上下文等使用的动态内存（MB）。
*   **Total Peak DRAM (VmHWM)**: 进程运行期间内存占用的历史最高峰值。
*   **Avg Runtime CPU Usage**: 从模型进入可推理状态到任务结束期间，进程平均 CPU 使用率（已按在线 CPU 核数归一化为百分比）。
*   **Generate TPS (Token/s)**: 模型自回归生成阶段的吞吐速度（Token per second）。
*   **Status**: 运行状态（如 `Success` 或由于 OOM 导致的异常退出）。
