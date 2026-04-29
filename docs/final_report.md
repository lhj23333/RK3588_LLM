# RK3588 大语言模型 (LLM) 与视觉语言模型 (VLM) 性能总结报告

本报告基于最新的基准测试结果，对多款主流文本及视觉语言大模型在 **Rockchip RK3588，16GB 板载内存** 上的运行状态、显存占用以及推理性能进行全面评估。

## 1. 测试环境 (Test Environment)

- **硬件平台**: Rockchip RK3588
- **物理内存**: 16GB LPDDR5
- **NPU 算力**: 6.0 TOPS（三核全开）
- **操作系统**: Debian GNU/Linux 12 (bookworm)，aarch64
- **内核**: Linux 6.1.84-8-rk2410
- **工具链与脚本环境**: GCC 12.x、Python 3.11
- **底层驱动 / 运行时**: RKLLM Runtime（基于 rknn-llm C++ API）

---

## 2. 多核 NPU 性能测试结果 (Multi-Core: 3 Cores)

在多核并行推理模式下，NPU 能够充分释放 6.0 TOPS 算力。

### 2.1 纯文本大模型 (Text LLMs)

**成功运行的模型表现：**


| Model Name        | Context Length | NPU Core | Init DRAM (Weights+KV) | Runtime Buffer DRAM | Total Peak DRAM | Generate TPS (Token/s) | Status    |
| ----------------- | -------------- | -------- | ---------------------- | ------------------- | --------------- | ---------------------- | --------- |
| qwen1.5-7b-text   | 4096           | 3        | ~8131.4 MB             | ~10.3 MB            | ~8140.8 MB      | **3.81**               | Success   |
| qwen1.5-14b-text  | 4096           | 3        | ~15112.8 MB            | ~127.7 MB           | ~15185.9 MB     | **2.04**               | Success   |
| qwen2-1.5b-text   | 4096           | 3        | ~1807.8 MB             | ~4.8 MB             | ~1812.5 MB      | **14.11**              | Success   |
| qwen2-7b-text     | 4096           | 3        | ~7210.6 MB             | ~9.4 MB             | ~7219.2 MB      | **4.05**               | Success   |
| qwen2.5-7b-text   | 4096           | 3        | ~7210.8 MB             | ~18.6 MB            | ~7229.4 MB      | **4.07**               | Success   |
| qwen3-0.6b-text   | 4096           | 3        | ~1267.5 MB             | ~2.5 MB             | ~1269.8 MB      | **26.78**              | Success   |
| qwen3-1.7b-text     | 4096           | 3        | ~1556.4 MB             | ~10.4 MB            | ~1566.7 MB      | **17.65**              | Success   |
| qwen3-4b-text     | 4096           | 3        | ~4825.0 MB             | ~8.4 MB             | ~4833.3 MB      | **6.29**               | Success   |
| qwen3-8b-text     | 4096           | 3        | ~7857.1 MB             | ~8.8 MB             | ~7864.3 MB      | **3.77**               | Success   |
| qwen3-14b-text    | 4096           | 3        | ~15135.0 MB            | ~125.0 MB           | ~15206.0 MB     | **2.01**               | Success |
| llama2-7b-text    | 4096           | 3        | ~7497.0 MB             | ~10.4 MB            | ~7505.9 MB      | **3.93**               | Success   |
| llama2-13b-text   | 4096           | 3        | ~15004.4 MB            | ~90.1 MB            | ~15052.8 MB     | **2.09**               | Success   |
| llama3-8b-text    | 4096           | 3        | ~7749.2 MB             | ~12.1 MB            | ~7751.7 MB      | **3.80**               | Success   |
| internlm2-7b-text | 4096           | 3        | ~7525.7 MB             | ~13.2 MB            | ~7536.6 MB      | **3.82**               | Success   |


### 2.2 视觉-语言混合大模型 (VLMs)

**成功运行的模型表现：**


| Model Name         | Context Length | NPU Core | Init DRAM (Weights+KV) | Runtime Buffer DRAM | Total Peak DRAM | Generate TPS (Token/s) | Status    |
| ------------------ | -------------- | -------- | ---------------------- | ------------------- | --------------- | ---------------------- | --------- |
| qwen2.5-vl-7b-npu  | 4096           | 3        | ~7246.1 MB             | ~1543.4 MB          | ~8785.9 MB      | **3.90**               | Success   |
| qwen3-vl-4b-npu    | 4096           | 3        | ~4673.0 MB             | ~897.6 MB           | ~5570.6 MB      | **6.30**               | Success   |
| qwen3-vl-2b-npu    | 4096           | 3        | ~2341.4 MB             | ~871.6 MB           | ~3205.1 MB      | **13.17**              | Success   |
| qwen3-vl-8b-npu    | 4096           | 3        | ~7890.3 MB             | ~967.9 MB           | ~8857.6 MB      | **3.61**               | Success   |
| internvl3.5-1b-npu | 4096           | 3        | ~1887.0 MB             | ~669.6 MB           | ~1935.4 MB      | **27.39**              | Success   |
| internvl3.5-2b-npu | 4096           | 3        | ~3008.3 MB             | ~689.5 MB           | ~3020.8 MB      | **12.79**              | Success   |
| internvl3.5-4b-npu | 4096           | 3        | ~4675.0 MB             | ~721.7 MB           | ~5396.5 MB      | **6.33**               | Success   |
| internvl3.5-8b-npu | 4096           | 3        | ~7680.0 MB             | ~901.0 MB           | ~8602.0 MB      | **3.56**               | Success |


---

## 3. 单核 NPU 性能测试结果 (Single-Core: 1 Core)

限制单一 NPU 核心（~2.0 TOPS）主要为了留出算力应对其他端侧并发任务。然而，单核模式会显著降低推理吞吐率，同时也面临模型架构支持度上的局限性。

### 3.1 纯文本大模型 (Text LLMs)

**成功运行的模型表现：**


| Model Name        | Context Length | NPU Core | Init DRAM (Weights+KV) | Runtime Buffer DRAM | Total Peak DRAM | Generate TPS (Token/s) | Status    |
| ----------------- | -------------- | -------- | ---------------------- | ------------------- | --------------- | ---------------------- | --------- |
| qwen1.5-7b-text   | 4096           | 1        | ~8086.6 MB             | ~14.2 MB            | ~8099.8 MB      | **1.49**               | Success   |
| qwen1.5-14b-text  | 4096           | 1        | ~15155.5 MB            | ~132.5 MB           | ~15206.4 MB     | **0.80**               | Success   |
| qwen2-1.5b-text   | 4096           | 1        | ~1780.7 MB             | ~1.3 MB             | ~1781.8 MB      | **6.42**               | Success   |
| qwen2-7b-text     | 4096           | 1        | ~7153.0 MB             | ~15.2 MB            | ~7168.0 MB      | **1.52**               | Success   |
| qwen2.5-7b-text   | 4096           | 1        | ~7152.7 MB             | ~16.3 MB            | ~7168.0 MB      | **1.53**               | Success   |
| qwen3-0.6b-text   | 4096           | 1        | ~1204.3 MB             | ~4.2 MB             | ~1208.3 MB      | **13.87**              | Success   |
| qwen3-1.7b-text     | 4096           | 1        | ~1530.3 MB             | ~6.0 MB             | ~1536.0 MB      | **7.61**               | Success   |
| qwen3-4b-text     | 4096           | 1        | ~4703.4 MB             | ~7.2 MB             | ~4710.4 MB      | **2.57**               | Success   |
| qwen3-8b-text     | 4096           | 1        | ~7803.2 MB             | ~11.4 MB            | ~7813.1 MB      | **1.42**               | Success   |
| qwen3-14b-text    | 4096           | 1        | ~15165.0 MB            | ~132.0 MB           | ~15247.0 MB     | **0.76**               | Success |
| llama2-7b-text    | 4096           | 1        | ~7452.0 MB             | ~14.1 MB            | ~7465.0 MB      | **1.59**               | Success   |
| llama2-13b-text   | 4096           | 1        | ~14998.9 MB            | ~84.1 MB            | ~15063.0 MB     | **0.82**               | Success   |
| llama3-8b-text    | 4096           | 1        | ~7698.0 MB             | ~14.5 MB            | ~7710.7 MB      | **1.44**               | Success   |
| internlm2-7b-text | 4096           | 1        | ~7474.3 MB             | ~11.1 MB            | ~7485.4 MB      | **1.46**               | Success   |


*(对比发现，在同等参数量下，单核的 TPS 性能基本下降至多核（三核）的 40% ~ 50% 左右。)*

### 3.2 视觉-语言混合大模型 (VLMs)

**成功运行的模型表现：**


| Model Name         | Context Length | NPU Core | Init DRAM (Weights+KV) | Runtime Buffer DRAM | Total Peak DRAM | Generate TPS (Token/s) | Status    |
| ------------------ | -------------- | -------- | ---------------------- | ------------------- | --------------- | ---------------------- | --------- |
| qwen2.5-vl-7b-npu  | 4096           | 1        | ~7185.8 MB             | ~1539.1 MB          | ~8724.5 MB      | **1.53**               | Success   |
| qwen3-vl-2b-npu    | 4096           | 1        | ~2313.2 MB             | ~666.8 MB           | ~2979.8 MB      | **5.74**               | Success   |
| qwen3-vl-4b-npu    | 4096           | 1        | ~4735.3 MB             | ~671.6 MB           | ~5406.7 MB      | **2.58**               | Success   |
| qwen3-vl-8b-npu    | 4096           | 1        | ~7837.9 MB             | ~980.2 MB           | ~8816.6 MB      | **1.42**               | Success   |
| internvl3.5-1b-npu | 4096           | 1        | ~1247.7 MB             | ~677.7 MB           | ~1925.1 MB      | **14.28**              | Success   |
| internvl3.5-2b-npu | 4096           | 1        | ~2322.5 MB             | ~678.0 MB           | ~3000.3 MB      | **5.77**               | Success   |
| internvl3.5-4b-npu | 4096           | 1        | ~4738.2 MB             | ~669.3 MB           | ~5406.7 MB      | **2.59**               | Success   |
| internvl3.5-8b-npu | 4096           | 1        | ~7619.0 MB             | ~922.0 MB           | ~8520.0 MB      | **1.46**               | Success |


*(对比发现，在同等参数量下，单核 VLM 的 TPS 性能基本下降至多核（三核）的 45% ~ 55% 左右。)*

---

## 4. 评估总结 (Conclusion)

1. **内存与模型形态**：表中峰值为进程级读数（权重、KV-Cache、运行缓冲等综合反映在 VmHWM 等指标上）。**纯文本**侧随参数量与 **4096** 上下文配置大致呈阶梯分布：**亚 2B** 约 **1.2~1.8 GB**，**4B** 约 **4.7~4.8 GB**，**7B~8B 家族**多落在 **7.1~8.8 GB**，更大稠密模型可达 **约 15 GB** 量级，说明在 **16 GB** 板载内存下可覆盖从端侧小模型到十余 GB 级权重的常用部署区间，同时余量随模型增大而收紧。**VLM** 因视觉分支与中间张量，在相近语言骨干规模下需额外 **约 0.6~1.5 GB** 级运行缓冲，**7B~8B 档 VLM** 峰值约 **8.6~8.9 GB**，整体高于同档纯文本。
2. **算力与 NPU 核心缩放**：三核并行更利于吃满标称 **6.0 TOPS**；**7B 档纯文本** 三核 TPS 多集中在 **约 3.7~4.1**，亚 **2B** 与 **1B 级 VLM** 在三核下可达 **十余~二十余 token/s**，更适合交互与演示。切到**单核**后，吞吐普遍明显下降，纯文本相对三核多为 **约 40%~50%**，VLM 多为 **约 45%~55%**，与「为其他负载预留 NPU」的设定相符；参数量增大时绝对 TPS 下降，但单/多核比例关系与中小模型同序。

