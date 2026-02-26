#!/usr/bin/env bash
# 依次运行所有 VLM 的 benchmark，将日志写入 results/，便于摘录 Peak Memory / TPS 填入 benchmark_log.md
# 用法: bash scripts/run_all_vlm_benchmarks.sh [测试图片路径]
# 默认图片: third_party/InternVL3.5-1B-NPU/Moon.jpg
# 运行前: sudo bash scripts/fix_freq_rk3588.sh && export RKLLM_LOG_LEVEL=1

set -e
WORKSPACE_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$WORKSPACE_ROOT"

IMAGE="${1:-$WORKSPACE_ROOT/third_party/InternVL3.5-1B-NPU/Moon.jpg}"
if [ ! -f "$IMAGE" ]; then
  echo "Error: image not found: $IMAGE"
  echo "Usage: $0 [path/to/test/image.jpg]"
  exit 1
fi

RESULTS="$WORKSPACE_ROOT/results"
mkdir -p "$RESULTS"

export RKLLM_LOG_LEVEL=1
export BATCH=1

VLM_NAMES="InternVL3.5-1B-NPU InternVL3.5-2B-NPU InternVL3.5-4B-NPU Qwen3-VL-2B-NPU Qwen3-VL-4B-NPU"

echo "Image: $IMAGE"
echo "Logs will be written to $RESULTS/vlm_<name>.log (BATCH=1: auto one prompt then exit)"
echo ""

for name in $VLM_NAMES; do
  log="$RESULTS/vlm_${name}.log"
  echo "=============================================="
  echo "Running $name -> $log"
  echo "=============================================="
  if bash scripts/run_vlm_benchmark.sh "$name" "$IMAGE" "$log"; then
    echo "OK"
  else
    echo "FAILED or OOM (check $log)"
  fi
  echo ""
done

echo "Done. From each log, extract: Peak Memory Usage (GB), Generate Tokens per Second, and optionally vision/prefill time."
echo "Fill results/benchmark_log.md Section 2 with these values."
