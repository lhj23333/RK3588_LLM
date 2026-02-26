# RK3588 (8GB) LLM 性能测试记录

本表格用于记录在 RK3588 (8GB RAM) 开发板上运行各类 LLM 模型的实际性能数据。**8B 模型（Qwen3-8B、InternVL3.5-8B）不纳入测试**（已排除，会 OOM）；下表仅保留 8B 的 OOM 记录供参考。

**测试环境说明：**
- 硬件：RK3588 (8GB RAM)
- 操作系统：Ubuntu/Debian (Linux)
- 性能模式：已执行 `fix_freq_rk3588.sh` 锁定最高频率
- 编译方式：板端 Native 编译 (GCC + CMake)

## 1. 纯文本大语言模型 (Text-only LLM)

| 模型名称 | 参数量 | 量化精度 | NPU 核心数 | 峰值 DRAM 占用 (GB) | 首字延迟 (s) | 推理速度 (TPS) | 备注 (是否 OOM/稳定) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Qwen3 | 0.6B | w8a8 | 3 Cores | 1.24 | ~0.20 | 11.83 (Generate) | 稳定 |
| Qwen3 | 1.7B | w8a8 | 3 Cores | 2.25 | ~0.15 | 8.93 (Generate) | 稳定 |
| Qwen3 | 4B | w8a8 | 3 Cores | 4.53 | ~0.43 | 4.65 (Generate) | 稳定 |
| Qwen3 | 8B | w8a8 | 3 Cores | - | - | - | 不测试；加载时 OOM（记录供参考） |
| Qwen3 | 0.6B/1.7B/4B | w8a8 | 1 Core | - | - | - | 需单独转换 1 核模型，未测 |

## 2. 多模态视觉语言模型 (Vision-Language Model)

*注：多模态模型除了 LLM 权重外，还需加载 Vision Encoder (如 ViT)，内存占用更高。*

**VLM 性能记录方法**：先执行 `bash scripts/build_all_vlm.sh` 编译全部 VLM，再执行 `bash scripts/run_all_vlm_benchmarks.sh`（需先 `fix_freq_rk3588.sh` 且 `RKLLM_LOG_LEVEL=1`），日志在 `results/vlm_<demo名>.log`。从各日志中摘录 **Peak Memory Usage (GB)**、**Generate 阶段 Tokens per Second**、若有则图像/Vision 耗时，填入下表。详见 [docs/06_benchmark_guide.md](docs/06_benchmark_guide.md) 第 6、8 节。

| 模型名称 | 参数量 | 量化精度 | NPU 核心数 | 峰值 DRAM 占用 (GB) | 图像处理耗时 (s) | 推理速度 (TPS) | 备注 (是否 OOM/稳定) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Qwen3-VL | 2B | w8a8 | 3 Cores | 3.27 | ~0.18 (Prefill) | 10.09 | 板端实测；稳定 |
| Qwen3-VL | 4B | w8a8 | 3 Cores | 5.44 | ~0.37 (Prefill) | 4.87 | 板端实测；稳定 |
| InternVL3.5 | 1B | w8a8 | 3 Cores | 1.88 | ~0.11 (Prefill) | 21.12 | 板端实测；稳定 |
| InternVL3.5 | 2B | w8a8 | 3 Cores | 2.95 | ~0.19 (Prefill) | 9.32 | 板端实测；稳定 |
| InternVL3.5 | 4B | w8a8 | 3 Cores | 5.27 | ~0.37 (Prefill) | 4.84 | 板端实测；稳定 |

## 3. 失败/不可行记录

| 模型名称 | 参数量 | 失败原因 | 详细说明 |
| :--- | :--- | :--- | :--- |
| Qwen3 | 8B | 不测试 | 8GB 加载时 OOM（w8a8 约 8.3GB）；记录供参考 |
| Qwen3 | 14B | 硬件限制 | 8GB 物理内存无法加载 14B 模型 (即使 INT4 也需要 ~8GB 纯净内存) |
| Qwen3 | 32B | 硬件限制 | 内存严重不足 |
| InternVL3.5 | 30B-A3B | 硬件限制 | 内存严重不足 |
