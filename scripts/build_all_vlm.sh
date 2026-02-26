#!/usr/bin/env bash
# 一键编译 third_party 下所有 VLM demo（InternVL3.5-1B/2B/4B-NPU, Qwen3-VL-2B/4B-NPU）
# 用法: bash scripts/build_all_vlm.sh
# 依赖: cmake, make, pkg-config, opencv4；rknn-llm 子模块已拉取

set -e
WORKSPACE_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$WORKSPACE_ROOT"

RKLLM_SO="$WORKSPACE_ROOT/third_party/rknn-llm/rkllm-runtime/Linux/librkllm_api/aarch64/librkllmrt.so"
RKNN_SO="$WORKSPACE_ROOT/third_party/rknn-llm/examples/multimodal_model_demo/deploy/3rdparty/librknnrt/Linux/librknn_api/aarch64/librknnrt.so"
VLM_LIB_DIR="$WORKSPACE_ROOT/build/vlm_lib"

if [ ! -f "$RKLLM_SO" ] || [ ! -f "$RKNN_SO" ]; then
  echo "Error: librkllmrt.so or librknnrt.so not found. Run: git submodule update --init third_party/rknn-llm"
  exit 1
fi

mkdir -p "$VLM_LIB_DIR"
cp -f "$RKLLM_SO" "$VLM_LIB_DIR/"
cp -f "$RKNN_SO" "$VLM_LIB_DIR/"
echo "Using RK_LIB_PATH=$VLM_LIB_DIR"

VLM_NAMES="InternVL3.5-1B-NPU InternVL3.5-2B-NPU InternVL3.5-4B-NPU Qwen3-VL-2B-NPU Qwen3-VL-4B-NPU"
for name in $VLM_NAMES; do
  dir="$WORKSPACE_ROOT/third_party/$name"
  if [ ! -d "$dir" ]; then
    echo "Skip $name (not found)"
    continue
  fi
  echo "=============================================="
  echo "Building $name"
  echo "=============================================="
  build_dir="$dir/build"
  mkdir -p "$build_dir"
  ( cd "$build_dir" && cmake .. -DRK_LIB_PATH="$VLM_LIB_DIR" && make -j"$(nproc)" )
  if [ -f "$dir/VLM_NPU" ] || [ -f "$build_dir/VLM_NPU" ]; then
    echo "OK: $name -> VLM_NPU"
  else
    echo "WARN: $name build may have failed (VLM_NPU not found)"
  fi
done

echo ""
echo "Done. Run VLM with: bash scripts/run_vlm_benchmark.sh <demo_name> <image>"
