# RK3588 LLM & VLM Workspace

Run text-only LLMs and vision-language models (VLMs) on **RK3588 (8GB RAM)** using the Rockchip RKLLM runtime. This repo provides the project layout, scripts, and on-board benchmark results with step-by-step reproduction instructions.

---

## Project structure

```
rk3588_llm_workspace/
├── README.md                 # This file (English)
├── .gitignore                # Ignores models/, build/
├── .gitmodules               # Submodule definitions
├── demos/                    # Text LLM demo (CMake + C++)
│   └── build/                # text_llm_demo binary (generated)
├── docs/                     # Detailed guides (Chinese)
│   ├── 01_environment_setup.md
│   ├── 02_dependencies.md
│   ├── 03_model_acquisition.md
│   ├── 04_run_text_llm.md
│   ├── 05_run_multimodal_vlm.md
│   ├── 06_benchmark_guide.md
│   └── 07_feasibility_report.md
├── models/                   # Put .rkllm / .rknn here (not in repo; see docs)
├── results/                  # Benchmark logs and summary
│   ├── benchmark_log.md      # Full benchmark table (source of truth)
│   ├── FINAL_REPORT.md       # Feasibility and summary
│   └── vlm_*.log             # Per-VLM run logs
├── scripts/
│   ├── build_all_vlm.sh      # Build all 5 VLM demos
│   ├── build_text_llm_demo.sh
│   ├── fix_freq_rk3588.sh    # Lock CPU/NPU/DDR to max perf (required before benchmarks)
│   ├── run_vlm_benchmark.sh  # Single VLM run
│   └── run_all_vlm_benchmarks.sh  # Run all VLMs, write logs to results/
└── third_party/              # Git submodules
    ├── rknn-llm              # Rockchip RKLLM SDK (runtime + headers)
    ├── InternVL3.5-1B-NPU    # Qengineering VLM demo
    ├── InternVL3.5-2B-NPU
    ├── InternVL3.5-4B-NPU
    ├── Qwen3-VL-2B-NPU
    └── Qwen3-VL-4B-NPU
```

- **Text LLM**: built under `demos/build/`; uses `third_party/rknn-llm` for `librkllmrt.so`.
- **VLM**: each `third_party/*-NPU` repo is built in-place and produces `VLM_NPU`; models live in workspace `models/` (see [Model acquisition](#4-model-acquisition)).

---

## Test environment

- **Board**: RK3588, **8 GB RAM**
- **OS**: Ubuntu/Debian (Linux aarch64)
- **Runtime**: rkllm-runtime 1.2.3, rknpu driver 0.9.8
- **Performance**: CPU/NPU/GPU/DDR set to performance mode via `scripts/fix_freq_rk3588.sh` before every run (required for stable TPS).

---

## Benchmark results

All numbers are from on-board runs with `RKLLM_LOG_LEVEL=1`. Peak memory = DRAM; TPS = Generate-phase tokens per second.

### Text-only LLM (3 NPU cores, W8A8)

| Model   | Size | Peak DRAM (GB) | First-token (s) | Throughput (TPS) | Note   |
|--------|------|----------------|-----------------|------------------|--------|
| Qwen3  | 0.6B | 1.24           | ~0.20           | 11.83            | Stable |
| Qwen3  | 1.7B | 2.25           | ~0.15           | 8.93             | Stable |
| Qwen3  | 4B   | 4.53           | ~0.43           | 4.65             | Stable |
| Qwen3  | 8B   | —              | —               | —                | Not tested (OOM on 8GB) |

### Vision-language model (3 NPU cores, W8A8)

| Model        | Size | Peak DRAM (GB) | Prefill (s) | Throughput (TPS) | Note   |
|-------------|------|----------------|-------------|------------------|--------|
| Qwen3-VL   | 2B   | 3.26           | ~0.18       | 10.01            | Stable |
| Qwen3-VL   | 4B   | 5.44           | ~0.37       | 4.86             | Stable |
| InternVL3.5| 1B   | 1.89           | ~0.11       | 21.08            | Stable |
| InternVL3.5| 2B   | 2.95           | ~0.19       | 9.76             | Stable |
| InternVL3.5| 4B   | 5.27           | ~0.37       | 4.89             | Stable |

Raw logs: `results/vlm_<demo_name>.log`. Full table and failure notes: [results/benchmark_log.md](results/benchmark_log.md).

---

## Reproduction steps

### 1. Clone and submodules

```bash
git clone --recurse-submodules https://github.com/lhj23333/RK3588_LLM.git
cd RK3588_LLM
```

If already cloned without submodules:

```bash
git submodule update --init --recursive
```

### 2. System dependencies (on RK3588)

```bash
sudo apt update
sudo apt install -y build-essential cmake libopencv-dev
```

### 3. RKLLM / RKNN runtime libraries

Use the libraries from the repo (no need to copy to `/usr` if you set `LD_LIBRARY_PATH` as below).

- **LLM**: `third_party/rknn-llm/rkllm-runtime/Linux/librkllm_api/aarch64/librkllmrt.so`
- **VLM vision encoder**: `third_party/rknn-llm/examples/multimodal_model_demo/deploy/3rdparty/librknnrt/Linux/librknn_api/aarch64/librknnrt.so`

Optional (for system-wide use):

```bash
sudo cp third_party/rknn-llm/rkllm-runtime/Linux/librkllm_api/aarch64/librkllmrt.so /usr/lib/
sudo cp third_party/rknn-llm/examples/multimodal_model_demo/deploy/3rdparty/librknnrt/Linux/librknn_api/aarch64/librknnrt.so /usr/lib/
sudo ldconfig
```

### 4. Model acquisition

Create `models/` in the workspace root. **Do not** convert models on the board (risk of OOM). Download pre-converted `.rkllm` / `.rknn` and place them in `models/`:

- **Text LLM**: Qwen3-0.6B, 1.7B, 4B (`.rkllm` only). Links and naming: [docs/03_model_acquisition.md](docs/03_model_acquisition.md).
- **VLM**: For each VLM you need the corresponding `.rkllm` + `.rknn` (e.g. `qwen3-vl-2b-instruct_w8a8_rk3588.rkllm` + `qwen3-vl-2b_vision_672_rk3588.rknn`). Same doc lists all download links and target filenames.

The `scripts/run_vlm_benchmark.sh` and `run_all_vlm_benchmarks.sh` expect files under `models/` as documented there and in `docs/03_model_acquisition.md`.

### 5. Performance mode (required before benchmarks)

On the RK3588, run before each benchmarking session (and after reboot):

```bash
sudo bash scripts/fix_freq_rk3588.sh
```

### 6. Build

**Text LLM demo:**

```bash
bash scripts/build_text_llm_demo.sh
# Binary: demos/build/text_llm_demo
```

**All VLM demos:**

```bash
bash scripts/build_all_vlm.sh
# Builds InternVL3.5-1B/2B/4B-NPU and Qwen3-VL-2B/4B-NPU; each has VLM_NPU in its directory or build/
```

### 7. Run text LLM

```bash
export LD_LIBRARY_PATH="third_party/rknn-llm/rkllm-runtime/Linux/librkllm_api/aarch64:$LD_LIBRARY_PATH"
export RKLLM_LOG_LEVEL=1

./demos/build/text_llm_demo models/Qwen3-0.6B-rk3588-w8a8-opt-1-hybrid-ratio-0.0.rkllm 512 4096
```

Replace the model path for 1.7B/4B as in [docs/04_run_text_llm.md](docs/04_run_text_llm.md). Type `exit` to quit.

### 8. Run a single VLM

```bash
export LD_LIBRARY_PATH="third_party/rknn-llm/examples/multimodal_model_demo/deploy/3rdparty/librknnrt/Linux/librknn_api/aarch64:third_party/rknn-llm/rkllm-runtime/Linux/librkllm_api/aarch64:$LD_LIBRARY_PATH"
export RKLLM_LOG_LEVEL=1

bash scripts/run_vlm_benchmark.sh <demo_name> <image_path> [log_file]
# Example:
bash scripts/run_vlm_benchmark.sh InternVL3.5-1B-NPU third_party/InternVL3.5-1B-NPU/Moon.jpg results/vlm_1b.log
```

`<demo_name>`: `InternVL3.5-1B-NPU`, `InternVL3.5-2B-NPU`, `InternVL3.5-4B-NPU`, `Qwen3-VL-2B-NPU`, `Qwen3-VL-4B-NPU`.

### 9. Run all VLM benchmarks (reproduce results table)

```bash
sudo bash scripts/fix_freq_rk3588.sh
export RKLLM_LOG_LEVEL=1
export BATCH=1

bash scripts/run_all_vlm_benchmarks.sh [image_path]
# Default image: third_party/InternVL3.5-1B-NPU/Moon.jpg
```

Logs are written to `results/vlm_<demo_name>.log`. From each log you can read **Peak Memory Usage (GB)** and **Generate Tokens per Second** to fill or check [results/benchmark_log.md](results/benchmark_log.md).

---

## Doc index

| Doc | Content |
|-----|---------|
| [docs/01_environment_setup.md](docs/01_environment_setup.md) | Environment, performance mode, RKLLM deployment |
| [docs/02_dependencies.md](docs/02_dependencies.md) | Dependencies and verification |
| [docs/03_model_acquisition.md](docs/03_model_acquisition.md) | Model download links and `models/` layout |
| [docs/04_run_text_llm.md](docs/04_run_text_llm.md) | Text LLM build and run |
| [docs/05_run_multimodal_vlm.md](docs/05_run_multimodal_vlm.md) | VLM build and run |
| [docs/06_benchmark_guide.md](docs/06_benchmark_guide.md) | How to run and record benchmarks |
| [docs/07_feasibility_report.md](docs/07_feasibility_report.md) | Feasibility (which models run / OOM) |
| [results/benchmark_log.md](results/benchmark_log.md) | Full benchmark table and failure notes |
| [results/FINAL_REPORT.md](results/FINAL_REPORT.md) | Summary and conclusions |

---

## License and references

- RKLLM / rknn-llm: Rockchip SDK ([third_party/rknn-llm](third_party/rknn-llm)).
- VLM demos: [Qengineering](https://github.com/Qengineering) (InternVL3.5-*‑NPU, Qwen3-VL-*‑NPU), used as git submodules.
- Pre-converted model sources: see [docs/03_model_acquisition.md](docs/03_model_acquisition.md) (Hugging Face, Qengineering, etc.).
