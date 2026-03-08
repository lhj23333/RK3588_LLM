# RK3588 大语言模型 (LLM) 与视觉语言模型 (VLM) 性能总结报告

本报告基于最新的基准测试结果，对多款主流文本及视觉语言大模型在 Rockchip RK3588 (8GB 内存版本) 上的运行状态、显存占用以及推理性能进行全面评估。报告内容以 **NPU 核心数（单核与多核）** 作为首要分类维度。

## 1. 测试环境 (Test Environment)

- **硬件平台**: Rockchip RK3588
- **物理内存**: 8GB LPDDR4x/LPDDR5
- **NPU 算力**: 6.0 TOPS (全开三核)
- **操作系统**: Ubuntu 20.04.6 LTS (Focal Fossa)
- **底层驱动/SDK**: RKLLM Runtime (基于 rknn-llm C++ API)

---

## 2. 多核 NPU 性能测试结果 (Multi-Core: 3 Cores)

在多核并行推理模式下，NPU 能够充分释放 6.0 TOPS 算力。经过验证，部分中小参数量（0.5B ~ 4B）的模型能稳定运行，但受限于 8GB 物理内存的硬件上限，参数量大于等于 7B 级别（或包含超大 MoE 架构）的模型普遍出现了 OOM（Out Of Memory，显存溢出）而无法正常推理。

### 2.1 纯文本大模型 (Text LLMs)

**✅ 成功运行的模型表现：**


| Model Name      | Context Length | NPU Core | Init DRAM (Weights+KV) | Runtime Buffer DRAM | Total Peak DRAM | Generate TPS (Token/s) | Status  |
| --------------- | -------------- | -------- | ---------------------- | ------------------- | --------------- | ---------------------- | ------- |
| qwen3-0.6b-text | 4096           | 3        | ~1267.5 MB             | ~2.5 MB             | ~1269.8 MB      | **26.78**              | Success |
| qwen3-1b-text   | 4096           | 3        | ~1556.4 MB             | ~10.4 MB            | ~1566.7 MB      | **17.65**              | Success |
| qwen2-1.5b-text | 4096           | 3        | ~1807.8 MB             | ~4.8 MB             | ~1812.5 MB      | **14.11**              | Success |
| qwen3-4b-text   | 4096           | 3        | ~4825.0 MB             | ~8.4 MB             | ~4833.3 MB      | **6.29**               | Success |


**❌ 内存溢出 (OOM) 的模型统计：**
受限于 8GB DRAM，以下模型在权重加载或 KV Cache 初始化阶段超出物理内存上限，导致进程被 Kernel 强杀：

- **通义千问系列**: qwen1.5-7B, qwen1.5-14B, Qwen2-7B, Qwen2.5-7B, Qwen2.5-32B, Qwen3-8B, Qwen3-32B, Qwen3-moe-30B-A3B
- **Llama 系列**: llama2-7B, llama2-14B, llama3-8B
- **其他主流模型**: internlm2-7B, deepseek-moe-16B

### 2.2 视觉-语言混合大模型 (VLMs)

**✅ 成功运行的模型表现：**


| Model Name         | Context Length | NPU Core | Init DRAM (Weights+KV) | Runtime Buffer DRAM | Total Peak DRAM | Generate TPS (Token/s) | Status  |
| ------------------ | -------------- | -------- | ---------------------- | ------------------- | --------------- | ---------------------- | ------- |
| internvl3.5-1b-npu | 4096           | 3        | ~1887.0 MB             | ~669.6 MB           | ~1935.4 MB      | **27.39**              | Success |
| qwen3-vl-2b-npu    | 4096           | 3        | ~2341.4 MB             | ~871.6 MB           | ~3205.1 MB      | **13.17**              | Success |
| internvl3.5-2b-npu | 4096           | 3        | ~3008.3 MB             | ~689.5 MB           | ~3020.8 MB      | **12.79**              | Success |
| internvl3.5-4b-npu | 4096           | 3        | ~4675.0 MB             | ~721.7 MB           | ~5396.5 MB      | **6.33**               | Success |
| qwen3-vl-4b-npu    | 4096           | 3        | ~4673.0 MB             | ~897.6 MB           | ~5570.6 MB      | **6.30**               | Success |


**❌ 内存溢出 (OOM) 的模型统计：**
因 VLM 模型具备庞大的视觉 Encoder（如 ViT 等），以下模型初始化显存远超 RK3588 的硬件边界：

- Qwen2.5-VL-7B, Qwen2.5-VL-32B, Qwen3-VL-8B

---

## 3. 单核 NPU 性能测试结果 (Single-Core: 1 Core)

限制单一 NPU 核心（~2.0 TOPS）主要为了留出算力应对其他端侧并发任务。然而，单核模式会显著降低推理吞吐率，同时也面临模型架构支持度上的局限性。

### 3.1 纯文本大模型 (Text LLMs)

**✅ 成功运行的模型表现：**


| Model Name      | Context Length | NPU Core | Init DRAM (Weights+KV) | Runtime Buffer DRAM | Total Peak DRAM | Generate TPS (Token/s) | Status  |
| --------------- | -------------- | -------- | ---------------------- | ------------------- | --------------- | ---------------------- | ------- |
| qwen3-0.6b-text | 4096           | 1        | ~1204.3 MB             | ~4.2 MB             | ~1208.3 MB      | **13.87**              | Success |
| qwen3-1b-text   | 4096           | 1        | ~1530.3 MB             | ~6.0 MB             | ~1536.0 MB      | **7.61**               | Success |
| qwen2-1.5b-text | 4096           | 1        | ~1780.7 MB             | ~1.3 MB             | ~1781.8 MB      | **6.42**               | Success |
| qwen3-4b-text   | 4096           | 1        | ~4703.4 MB             | ~7.2 MB             | ~4710.4 MB      | **2.57**               | Success |


*(对比发现，在同等参数量下，单核的 TPS 性能基本下降至多核（三核）的 40% ~ 50% 左右。)*

**❌ 内存溢出 (OOM) 的模型统计：**
与多核测试结果保持一致，单核调度模式并不能减轻模型权重的静态显存占用：

- internlm2-7B, llama2-7B, llama2-14B, llama3-8B, qwen1.5-7B, qwen1.5-14B, Qwen2-7B, deepseek-moe-16B, Qwen2.5-7B, Qwen2.5-32B, Qwen3-8B, Qwen3-32B, Qwen3-moe-30B-A3B

### 3.2 视觉-语言混合大模型 (VLMs)

**✅ 成功运行的模型表现：**


| Model Name         | Context Length | NPU Core | Init DRAM (Weights+KV) | Runtime Buffer DRAM | Total Peak DRAM | Generate TPS (Token/s) | Status  |
| ------------------ | -------------- | -------- | ---------------------- | ------------------- | --------------- | ---------------------- | ------- |
| internvl3.5-1b-npu | 4096           | 1        | ~1247.7 MB             | ~677.7 MB           | ~1925.1 MB      | **14.28**              | Success |
| internvl3.5-2b-npu | 4096           | 1        | ~2322.5 MB             | ~678.0 MB           | ~3000.3 MB      | **5.77**               | Success |
| internvl3.5-4b-npu | 4096           | 1        | ~4738.2 MB             | ~669.3 MB           | ~5406.7 MB      | **2.59**               | Success |
| qwen3-vl-2b-npu    | 4096           | 1        | ~2313.2 MB             | ~666.8 MB           | ~2979.8 MB      | **5.74**               | Success |
| qwen3-vl-4b-npu    | 4096           | 1        | ~4735.3 MB             | ~671.6 MB           | ~5406.7 MB      | **2.58**               | Success |

*(对比发现，在同等参数量下，单核 VLM 的 TPS 性能基本下降至多核（三核）的 45% ~ 55% 左右。)*

**❌ 内存溢出 (OOM) 的模型统计：**
与多核情况一致，以下模型因超出 8GB 物理内存直接导致 OOM 崩溃，完全无法进行单/多核的部署评估：

- Qwen2.5-VL-7B, Qwen2.5-VL-32B, Qwen3-VL-8B

---

## 4. 评估总结 (Conclusion)

1. **硬件内存瓶颈明显**：在 RK3588 (8GB 内存版本) 平台上，能够安全流畅运行的模型参数量红线为 **4B 级别**（如 Qwen3-4B 或 InternVL3.5-4B）。当参数量达到 7B 及以上（如 Llama 2/3、Qwen 7B/8B 及 14B~32B 等），毫无例外均会遭遇 OOM 而无法启动。
2. **性能缩放比例**：纯文本模型在单核下的 TPS（Token Per Second）速率大幅缩水，以 Qwen3-1B 为例，单核 TPS（7.61）约为多核 TPS（17.65）的 43%。

