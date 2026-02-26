#!/usr/bin/env bash
# 多模态 VLM 性能测试脚本（RK3588 板端运行）
# 用法: bash scripts/run_vlm_benchmark.sh <demo_dir_name> <image_path> [output_log]
# 示例: bash scripts/run_vlm_benchmark.sh InternVL3.5-1B-NPU /path/to/Moon.jpg
# 运行前请: sudo bash scripts/fix_freq_rk3588.sh && export RKLLM_LOG_LEVEL=1

set -e
WORKSPACE_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$WORKSPACE_ROOT"

DEMO_NAME="${1:-}"
IMAGE_PATH="${2:-}"
LOG_FILE="${3:-}"

RKLLM_API="$WORKSPACE_ROOT/third_party/rknn-llm/rkllm-runtime/Linux/librkllm_api/aarch64"
RKNN_API="$WORKSPACE_ROOT/third_party/rknn-llm/examples/multimodal_model_demo/deploy/3rdparty/librknnrt/Linux/librknn_api/aarch64"
export LD_LIBRARY_PATH="$RKNN_API:$RKLLM_API:${LD_LIBRARY_PATH:-}"
export RKLLM_LOG_LEVEL="${RKLLM_LOG_LEVEL:-1}"

if [ -z "$DEMO_NAME" ] || [ -z "$IMAGE_PATH" ]; then
  echo "Usage: $0 <demo_dir_name> <image_path> [output_log]"
  echo "  demo_dir_name: e.g. InternVL3.5-1B-NPU, InternVL3.5-2B-NPU, InternVL3.5-4B-NPU, Qwen3-VL-2B-NPU, Qwen3-VL-4B-NPU"
  echo "  image_path: path to a test image (e.g. third_party/InternVL3.5-1B-NPU/Moon.jpg or any .jpg)"
  echo "  output_log: optional; if set, stdout is tee'd here for parsing Peak Memory / TPS"
  echo ""
  echo "Demo 来自 third_party/（submodule），模型统一用工作区 models/。初始化 submodule: git submodule update --init --recursive"
  echo "Before running: sudo bash scripts/fix_freq_rk3588.sh"
  exit 1
fi

# 优先 third_party（submodule），其次 demos（兼容旧布局）
DEMO_DIR="$WORKSPACE_ROOT/third_party/$DEMO_NAME"
if [ ! -d "$DEMO_DIR" ]; then
  DEMO_DIR="$WORKSPACE_ROOT/demos/$DEMO_NAME"
fi
if [ ! -d "$DEMO_DIR" ]; then
  echo "Error: demo dir not found (tried third_party/$DEMO_NAME and demos/$DEMO_NAME)"
  echo "Init submodules: git submodule update --init third_party/InternVL3.5-1B-NPU third_party/Qwen3-VL-2B-NPU ..."
  exit 1
fi

# 模型统一使用工作区根目录 models/
MODELS_DIR="$WORKSPACE_ROOT/models"

if [ ! -f "$IMAGE_PATH" ]; then
  echo "Error: image not found: $IMAGE_PATH"
  exit 1
fi

# 可执行文件在 demo 目录或 build 子目录（Qengineering 仓库为 VLM_NPU）
if [ -f "$DEMO_DIR/VLM_NPU" ]; then
  EXE="$DEMO_DIR/VLM_NPU"
elif [ -f "$DEMO_DIR/build/VLM_NPU" ]; then
  EXE="$DEMO_DIR/build/VLM_NPU"
else
  echo "Error: VLM_NPU not found in $DEMO_DIR or $DEMO_DIR/build"
  exit 1
fi

case "$DEMO_NAME" in
  InternVL3.5-1B-NPU)
    VISION="$MODELS_DIR/internvl3_5-1b_vision_rk3588.rknn"
    LLM="$MODELS_DIR/internvl3_5-1b-instruct_w8a8_rk3588.rkllm"
    ;;
  InternVL3.5-2B-NPU)
    VISION="$MODELS_DIR/internvl3_5-2b_vision_rk3588.rknn"
    LLM="$MODELS_DIR/internvl3_5-2b-instruct_w8a8_rk3588.rkllm"
    ;;
  InternVL3.5-4B-NPU)
    VISION="$MODELS_DIR/internvl3_5-4b_vision_rk3588.rknn"
    LLM="$MODELS_DIR/internvl3_5-4b-instruct_w8a8_rk3588.rkllm"
    ;;
  Qwen3-VL-2B-NPU)
    VISION="$MODELS_DIR/qwen3-vl-2b_vision_672_rk3588.rknn"
    LLM="$MODELS_DIR/qwen3-vl-2b-instruct_w8a8_rk3588.rkllm"
    ;;
  Qwen3-VL-4B-NPU)
    VISION="$MODELS_DIR/qwen3-vl-4b-vision_rk3588.rknn"
    LLM="$MODELS_DIR/qwen3-vl-4b-instruct_w8a8_rk3588.rkllm"
    ;;
  *)
    echo "Unknown demo: $DEMO_NAME. Edit this script to add model paths."
    exit 1
    ;;
esac

for f in "$VISION" "$LLM"; do
  if [ ! -f "$f" ]; then
    echo "Error: model file not found: $f"
    exit 1
  fi
done

echo "Running: $EXE $IMAGE_PATH $VISION $LLM 2048 4096"
echo "LD_LIBRARY_PATH=$LD_LIBRARY_PATH"
echo "RKLLM_LOG_LEVEL=$RKLLM_LOG_LEVEL"
echo "---"

# 若提供了日志文件且环境变量 BATCH=1，则自动输入一行问题后 exit，便于批量跑 benchmark
RUN_CMD=("$EXE" "$IMAGE_PATH" "$VISION" "$LLM" 2048 4096)
if [ -n "$LOG_FILE" ]; then
  if [ "${BATCH:-0}" = "1" ]; then
    printf 'What is in this image?\nexit\n' | "${RUN_CMD[@]}" 2>&1 | tee "$LOG_FILE"
  else
    "${RUN_CMD[@]}" 2>&1 | tee "$LOG_FILE"
  fi
else
  if [ "${BATCH:-0}" = "1" ]; then
    printf 'What is in this image?\nexit\n' | "${RUN_CMD[@]}"
  else
    "${RUN_CMD[@]}"
  fi
fi
