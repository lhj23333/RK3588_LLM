# 性能测试方法说明

## 1. 测试前必做：性能模式

RK3588 默认动态调频会导致 TPS 波动大、数值偏低。**每次重启或跑 benchmark 前**执行：

```bash
sudo bash scripts/fix_freq_rk3588.sh
```

将 CPU、DDR、NPU、GPU 设为 performance 模式。

## 2. 输出推理耗时与内存（RKLLM）

运行纯文本或多模态 demo 前设置：

```bash
export RKLLM_LOG_LEVEL=1
```

运行结束后会在终端打印：
- **Model init time**：模型加载耗时 (ms)
- **Stage**：Prefill / Generate 的 Total Time、Tokens、Time per Token、**Tokens per Second**
- **Peak Memory Usage (GB)**：峰值 DRAM 占用

据此可填写 `results/benchmark_log.md` 中的 TPS 与峰值 DRAM。

## 3. 单次运行示例（纯文本）

```bash
cd /path/to/rk3588_llm_workspace
export LD_LIBRARY_PATH=third_party/rknn-llm/rkllm-runtime/Linux/librkllm_api/aarch64:$LD_LIBRARY_PATH
export RKLLM_LOG_LEVEL=1
# 输入一个问题后输入 exit，即可从日志中读取该轮 Prefill/Generate 的 TPS 与 Peak Memory
./demos/build/text_llm_demo models/Qwen3-0.6B-rk3588-w8a8-opt-1-hybrid-ratio-0.0.rkllm 512 4096
```

## 4. DRAM 监控（可选）

在**另一终端**运行，观察推理过程中内存变化：

```bash
watch -n 1 "free -m | grep Mem"
```

或使用工作区脚本（需 root 时可看 NPU 负载）：

```bash
bash scripts/monitor_perf.sh
```

## 5. 单核 vs 三核 NPU 对比

当前预转换模型多为 **3 核**（转换时 `num_npu_core=3`）。若需单核 TPS 对比，须在 **x86 PC** 上用 rkllm-toolkit 将同一模型以 `num_npu_core=1` 重新转换得到单独 .rkllm，再在板端运行并记录日志。本仓库未提供 1 核预转换模型，故单核数据未测。

## 6. 多模态 VLM 实测步骤

多模态使用 **third_party/** 下的 Qengineering 仓库（submodule），可执行文件如 `third_party/InternVL3.5-1B-NPU/VLM_NPU`。模型统一放在工作区 **`models/`**，见 [03_model_acquisition.md](03_model_acquisition.md)。

1. **初始化 submodule**：`git submodule update --init --recursive`
2. **下载模型**：按 03 文档将 .rkllm/.rknn 放到工作区 **`models/`**
3. **集成编译**（推荐）：
   ```bash
   bash scripts/build_all_vlm.sh
   ```
   将编译全部 5 个 VLM demo，无需单独进每个目录执行 cmake。
4. **单次运行**（需先 `sudo bash scripts/fix_freq_rk3588.sh`）：
   ```bash
   export RKLLM_LOG_LEVEL=1
   bash scripts/run_vlm_benchmark.sh <demo_dir_name> <图片路径> [可选日志文件]
   ```
   从终端或日志摘录 **Peak Memory Usage (GB)**、**Generate Tokens per Second**、若有则 **图像/Vision 耗时 (s)**，填入 `results/benchmark_log.md` 第 2 节。

## 7. 结果记录位置

- 纯文本 / 多模态的 TPS、峰值 DRAM、失败原因等统一填入 **`results/benchmark_log.md`**。
- 可行性结论与不可行模型清单见 **`docs/07_feasibility_report.md`**。

## 8. 批量跑 VLM 并详细记录性能

依次跑齐 5 个 VLM、将日志写入 `results/`，便于统一摘录数据填入 `benchmark_log.md`。

1. **测试前**：`sudo bash scripts/fix_freq_rk3588.sh`，并确保 `models/` 下有所需 .rkllm/.rknn。
2. **一键跑齐**（每个 demo 自动输入一句问题后 exit，无需手敲）：
   ```bash
   export RKLLM_LOG_LEVEL=1
   bash scripts/run_all_vlm_benchmarks.sh [测试图片路径]
   ```
   默认图片为 `third_party/InternVL3.5-1B-NPU/Moon.jpg`。日志输出到 `results/vlm_<demo名>.log`。
3. **从日志摘录并填入 `results/benchmark_log.md` 第 2 节**：
   - **Peak Memory Usage (GB)**：在日志中搜 `Peak Memory` 或 `peak memory`，取数值。
   - **推理速度 (TPS)**：在 **Generate** 阶段找 `Tokens per Second` 或 `tokens/s`，取该轮生成速度。
   - **图像处理耗时 (s)**：若有 Vision Encoder / Prefill 单独耗时则填；否则可填 `-` 或从首 token 延迟估算。
   - 若某模型 OOM 或段错误，在备注列写 **OOM** / **Segmentation fault**，并在第 3 节「失败/不可行记录」补一行。
4. **单模型补测**：`bash scripts/run_vlm_benchmark.sh <demo_dir_name> <图片> results/vlm_<name>.log`（不设 `BATCH=1` 时可交互多轮对话后再输入 `exit`）。
