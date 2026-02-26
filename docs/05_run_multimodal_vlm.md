# 多模态 VLM Demo 运行指南

## 1. 官方 multimodal demo 编译（rknn-llm 仓库）

```bash
cd third_party/rknn-llm/examples/multimodal_model_demo/deploy
mkdir -p build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j4
```

可执行文件：`build/demo`。依赖：CMake、OpenCV（3rdparty 已带）、librknnrt、librkllmrt（见 [02_dependencies.md](02_dependencies.md)）。

## 2. 运行命令格式

```bash
./demo <image_path> <encoder_model_path> <llm_model_path> <max_new_tokens> <max_context_len> <rknn_core_num> [img_start] [img_end] [img_content]
```

- **Qwen3-VL**：`img_start` / `img_end` / `img_content` 分别为 `"<|vision_start|>"`、`"<|vision_end|>"`、`"<|image_pad|>"`。
- **InternVL3**：通常为 `"<img>"`、`"</img>"`、`"<IMG_CONTEXT>"`（以模型配置为准）。

运行前设置库路径（若未安装到系统）：

```bash
export LD_LIBRARY_PATH=third_party/rknn-llm/examples/multimodal_model_demo/deploy/3rdparty/librknnrt/Linux/librknn_api/aarch64:third_party/rknn-llm/rkllm-runtime/Linux/librkllm_api/aarch64:$LD_LIBRARY_PATH
```

## 3. Qwen3-VL-2B 示例命令（672 分辨率）

在工作区根目录执行：

```bash
./third_party/rknn-llm/examples/multimodal_model_demo/deploy/build/demo \
  <图片路径.jpg> \
  models/qwen3-vl-2b_vision_672_rk3588.rknn \
  models/qwen3-vl-2b-instruct_w8a8_rk3588.rkllm \
  512 4096 3 \
  "<|vision_start|>" "<|vision_end|>" "<|image_pad|>"
```

**说明**：在当前环境实测时，上述命令在 LLM 加载完成后运行阶段出现 **Segmentation fault**，可能与官方 demo 与 Qwen3-VL-2B 的接口或内存布局有关。若需稳定跑通 Qwen3-VL-2B，建议使用 [Qengineering/Qwen3-VL-2B-NPU](https://github.com/Qengineering/Qwen3-VL-2B-NPU) 的 C++ 工程与配套模型；InternVL3.5 系列同样建议使用 Qengineering 对应仓库的 demo。

## 4. InternVL3.5 与 Qwen3-VL（Qengineering 仓库，third_party submodule）

- **不要直接 clone**：第三方 VLM 仓库以 **submodule** 形式放在 **`third_party/`**，初始化：`git submodule update --init --recursive`（见 [03_model_acquisition.md](03_model_acquisition.md)）。
- 模型文件统一放在工作区 **`models/`**，与 `scripts/run_vlm_benchmark.sh` 一致。

### 4.1 集成编译所有 VLM

在工作区根目录执行一键编译（会使用 `third_party/rknn-llm` 的 .so 作为链接库，无需提前安装到 /usr/local）：

```bash
bash scripts/build_all_vlm.sh
```

将依次编译 `third_party/InternVL3.5-1B-NPU`、`InternVL3.5-2B-NPU`、`InternVL3.5-4B-NPU`、`Qwen3-VL-2B-NPU`、`Qwen3-VL-4B-NPU`，生成各目录下的 **VLM_NPU** 可执行文件。依赖：cmake、make、pkg-config、opencv4。

### 4.2 单次运行与性能测试

运行前设置 `export RKLLM_LOG_LEVEL=1`，执行：

```bash
bash scripts/run_vlm_benchmark.sh <demo_dir_name> <图片路径> [可选日志文件]
# 示例: bash scripts/run_vlm_benchmark.sh InternVL3.5-1B-NPU third_party/InternVL3.5-1B-NPU/Moon.jpg results/vlm_1b.log
```

详见 [06_benchmark_guide.md](06_benchmark_guide.md) 第 6、8 节（含批量跑 benchmark 与性能记录）。

## 5. 多模态依赖小结

除 [02_dependencies.md](02_dependencies.md) 中的 RKLLM/RKNN 运行时与性能模式外，多模态还需：

- **OpenCV**：`sudo apt install -y libopencv-dev`（若使用系统 OpenCV）；官方 demo 使用 3rdparty 内 OpenCV 则无需单独安装。
- **librknnrt.so**：视觉编码器推理必须。
