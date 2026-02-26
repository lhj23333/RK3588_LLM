#!/bin/bash
set -e

WORKSPACE_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RKLLM_SDK="${WORKSPACE_ROOT}/third_party/rknn-llm"
RKLLM_INCLUDE="${RKLLM_SDK}/rkllm-runtime/Linux/librkllm_api/include"
RKLLM_LIB="${RKLLM_SDK}/rkllm-runtime/Linux/librkllm_api/aarch64"
SRC="${RKLLM_SDK}/examples/rkllm_api_demo/deploy/src/llm_demo.cpp"
BUILD_DIR="${WORKSPACE_ROOT}/demos/build"
OUTPUT="${BUILD_DIR}/text_llm_demo"

mkdir -p "${BUILD_DIR}"

echo "=== Building text_llm_demo (native aarch64) ==="
echo "Source: ${SRC}"
echo "Include: ${RKLLM_INCLUDE}"
echo "Lib: ${RKLLM_LIB}"

g++ -O2 -std=c++17 \
    -I"${RKLLM_INCLUDE}" \
    -L"${RKLLM_LIB}" \
    "${SRC}" \
    -o "${OUTPUT}" \
    -lrkllmrt -lpthread -ldl

echo "=== Build successful ==="
echo "Output: ${OUTPUT}"
echo ""
echo "Usage: ${OUTPUT} <model.rkllm> <max_new_tokens> <max_context_len>"
echo "Example: ${OUTPUT} models/qwen3-0.6b_w8a8_rk3588.rkllm 512 4096"
