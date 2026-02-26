# RK3588 (8GB) LLM Demo 最终报告

## 1. 执行摘要

- **硬件**：RK3588，8GB RAM，RKLLM Runtime 1.2.3，RKNPU 驱动 0.9.8。
- **纯文本 LLM**：Qwen3-0.6B / 1.7B / 4B 已跑通并测得 TPS 与峰值 DRAM。**8B 不测试**（已删除，8GB 会 OOM）。
- **多模态 VLM**：已提供 Qengineering 仓库的克隆与运行方法、`scripts/run_vlm_benchmark.sh` 及 [docs/06_benchmark_guide.md](docs/06_benchmark_guide.md) 第 6 节实测步骤。当前 `results/benchmark_log.md` 中多模态表已填入 **Qengineering 参考数据**（RAM、TPS、图像耗时）；板端完成实测后请从 RKLLM_LOG_LEVEL=1 日志摘录替换。
- **单核 vs 三核**：当前仅有 3 核预转换模型，单核 TPS 未测（需单独转换 1 核模型）。

---

## 2. 可行性结论（与老板要求模型对照）

### 2.1 可跑（已测或资源足够）

| 模型 | 类型 | 实测情况 |
| :--- | :--- | :--- |
| Qwen3-0.6B | 纯文本 | 已测：峰值 1.24 GB，Generate ~11.83 TPS |
| Qwen3-1.7B | 纯文本 | 已测：峰值 2.25 GB，Generate ~8.93 TPS |
| Qwen3-4B | 纯文本 | 已测：峰值 4.53 GB，Generate ~4.65 TPS |
| Qwen3-VL-2B | 多模态 | 参考 Qengineering：~3.1 GB、~11.5 TPS；板端用 Qwen3-VL-2B-NPU 实测后更新 |
| Qwen3-VL-4B | 多模态 | 参考 ~8.7 GB、~5.7 TPS；8GB 极限可能 OOM，板端实测后更新 |
| InternVL3.5-1B | 多模态 | 参考 ~1.9 GB、~24 TPS；板端用 run_vlm_benchmark.sh 实测后更新 |
| InternVL3.5-2B | 多模态 | 参考 ~3.0 GB、~11.2 TPS；板端实测后更新 |
| InternVL3.5-4B | 多模态 | 参考 ~5.4 GB、~5 TPS；板端实测后更新 |

### 2.2 不可跑（8GB 板子）

| 模型 | 原因 |
| :--- | :--- |
| Qwen3-8B / InternVL3.5-8B | 不测试（已排除，8GB 会 OOM） |
| Qwen3-14B / 32B | 内存严重不足 |
| Qwen3-VL-8B / 32B | 显存/内存需求远超 8GB |
| Qwen3-VL-30B-A3B | MoE 需加载完整 30B 权重 |
| InternVL3.5-14B | 内存不足 |
| InternVL3.5-30B-A3B | MoE 需完整 30B 权重 |

**说明**：老板列表中的「Qwen3-1B」实际不存在，已用 **Qwen3-1.7B** 代替并完成测试。

---

## 3. Benchmark 汇总（3 核 NPU，RKLLM_LOG_LEVEL=1）

### 纯文本 LLM（已实测）

| 模型 | 峰值 DRAM (GB) | Generate TPS | 备注 |
| :--- | :--- | :--- | :--- |
| Qwen3-0.6B | 1.24 | 11.83 | 稳定 |
| Qwen3-1.7B | 2.25 | 8.93 | 稳定 |
| Qwen3-4B | 4.53 | 4.65 | 稳定 |
| Qwen3-8B | - | - | 不测试（已排除） |
| 单核 TPS | - | - | 需 1 核专用模型，未测 |

### 多模态 VLM（参考 Qengineering 数据；板端实测后替换）

| 模型 | 峰值 DRAM (GB) | Generate TPS | 图像处理 (s) | 备注 |
| :--- | :--- | :--- | :--- | :--- |
| Qwen3-VL-2B | 3.1 | 11.5 | ~0.9 | 板端用 Qwen3-VL-2B-NPU 实测 |
| Qwen3-VL-4B | 8.7 | 5.7 | ~1.1 | 8GB 极限，可能 OOM |
| InternVL3.5-1B | 1.9 | 24 | ~0.8 | 板端用 run_vlm_benchmark.sh |
| InternVL3.5-2B | 3.0 | 11.2 | ~0.8 | 板端实测后更新 |
| InternVL3.5-4B | 5.4 | 5 | ~0.8 | 板端实测后更新 |

详细表格见 `results/benchmark_log.md`。

---

## 4. 依赖与复现

- **依赖**：见 `docs/02_dependencies.md`（边跑边记，含安装命令与常见问题）。
- **模型**：见 `docs/03_model_acquisition.md`（下载链接与拷贝目录）。
- **运行与性能测试**：见 `docs/04_run_text_llm.md`、`05_run_multimodal_vlm.md`、`06_benchmark_guide.md`。
- **可行性分析**：见 `docs/07_feasibility_report.md`。

---

## 5. 建议后续动作

1. **单核 TPS**：在 x86 PC 上用 rkllm-toolkit 以 `num_npu_core=1` 转换 Qwen3-0.6B/1.7B/4B，再在板端测 TPS。
2. **多模态**：按 `docs/06_benchmark_guide.md` 第 6 节与 `scripts/run_vlm_benchmark.sh` 在板端跑齐 5 个 VLM，从 RKLLM_LOG_LEVEL=1 输出摘录 TPS/DRAM 替换 `benchmark_log.md` 中的参考值。
3. **8B 模型**：本项目不测试 8B（会 OOM）。若有 16GB 板子可自行测 Qwen3-8B 或 InternVL3.5-8B。
