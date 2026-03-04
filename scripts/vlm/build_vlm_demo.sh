#!/usr/bin/env bash
# 根据 conf/models_config.yaml 编译 third_party 下的 VLM demo
# 用法: bash scripts/vlm/build_vlm_demo.sh [demo_name]
# 如果不提供 demo_name，则默认编译配置文件中列出的所有 VLM demo。
# 依赖: cmake, make, pkg-config, opencv4；rknn-llm 子模块已拉取

set -e
WORKSPACE_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$WORKSPACE_ROOT"

CONFIG_FILE="$WORKSPACE_ROOT/conf/models_config.yaml"
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: Config file not found at $CONFIG_FILE"
    exit 1
fi

# 动态解析配置中用到的所有 VLM demo 目录名
VLM_NAMES=$(grep 'binary_path: "third_party/' "$CONFIG_FILE" | awk -F '"' '{print $2}' | awk -F '/' '{print $2}' | sort | uniq | tr '\n' ' ' | sed 's/ $//')

RKLLM_SO="$WORKSPACE_ROOT/third_party/rknn-llm/rkllm-runtime/Linux/librkllm_api/aarch64/librkllmrt.so"
RKNN_SO="$WORKSPACE_ROOT/third_party/rknn-llm/examples/multimodal_model_demo/deploy/3rdparty/librknnrt/Linux/librknn_api/aarch64/librknnrt.so"
VLM_LIB_DIR="$WORKSPACE_ROOT/build/vlm_lib"
RKLLM_INCLUDE="$WORKSPACE_ROOT/third_party/rknn-llm/rkllm-runtime/Linux/librkllm_api/include"
RKNN_INCLUDE="$WORKSPACE_ROOT/third_party/rknn-llm/examples/multimodal_model_demo/deploy/3rdparty/librknnrt/Linux/librknn_api/include"

if [ ! -f "$RKLLM_SO" ] || [ ! -f "$RKNN_SO" ]; then
  echo "Error: librkllmrt.so or librknnrt.so not found. Run: git submodule update --init third_party/rknn-llm"
  exit 1
fi

mkdir -p "$VLM_LIB_DIR"
cp -f "$RKLLM_SO" "$VLM_LIB_DIR/"
cp -f "$RKNN_SO" "$VLM_LIB_DIR/"
echo "Using RK_LIB_PATH=$VLM_LIB_DIR"

# 检查是否传入了特定的 demo 名称
if [ -n "$1" ]; then
  if [[ " $VLM_NAMES " =~ " $1 " ]]; then
    VLM_NAMES="$1"
  elif [ "$1" == "all" ]; then
    : # 保持默认的 VLM_NAMES 编译所有
  else
    echo "Error: Unknown demo name '$1'"
    echo "Supported demos (from config): $VLM_NAMES"
    exit 1
  fi
fi

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
  
  # 修改 CMakeLists.txt 以包含 RKLLM 和 RKNN 头文件
  if ! grep -q "RKLLM_INCLUDE" "$dir/CMakeLists.txt"; then
    sed -i "/include_directories(include)/a include_directories(\"\${RKLLM_INCLUDE}\" \"\${RKNN_INCLUDE}\")" "$dir/CMakeLists.txt"
  fi
  
  ( cd "$build_dir" && cmake .. -DRK_LIB_PATH="$VLM_LIB_DIR" -DRKLLM_INCLUDE="$RKLLM_INCLUDE" -DRKNN_INCLUDE="$RKNN_INCLUDE" && make -j"$(nproc)" )
  if [ -f "$dir/VLM_NPU" ] || [ -f "$build_dir/VLM_NPU" ]; then
    echo "OK: $name -> VLM_NPU"
  else
    echo "WARN: $name build may have failed (VLM_NPU not found)"
  fi
done

echo ""
echo "Done. Run VLM with: bash scripts/run_vlm_benchmark.sh <demo_name> <image>"
