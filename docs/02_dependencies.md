# RK3588 LLM Demo 依赖清单（边跑边记）

本文档记录在**实际编写、安装、运行** Demo 过程中遇到的依赖，按安装顺序列出，便于他人复现。

---

## 1. 系统与工具链

| 依赖 | 安装命令 | 用途 | 验证 |
| :--- | :--- | :--- | :--- |
| 基础编译 | `sudo apt update && sudo apt install -y build-essential` | gcc/g++/make | `gcc --version` |
| CMake | `sudo apt install -y cmake` | 构建 C++ 工程（多模态 demo 可选） | `cmake --version` |
| Git | `sudo apt install -y git` | 克隆 rknn-llm、Qengineering 等仓库 | `git --version` |

**说明**：纯文本 `text_llm_demo` 使用工作区提供的 `scripts/build_text_llm_demo.sh` 直接 g++ 编译，不强制要求 CMake。多模态 demo 需要 CMake。

---

## 2. RKLLM / RKNN 运行时库

板端运行 **任何** RKLLM 模型前，必须让系统能找到 `librkllmrt.so`；多模态 VLM 还需 `librknnrt.so`。

| 库 | 来源路径（工作区） | 安装命令 | 验证 |
| :--- | :--- | :--- | :--- |
| librkllmrt.so | `third_party/rknn-llm/rkllm-runtime/Linux/librkllm_api/aarch64/` | `sudo cp <上述路径>/librkllmrt.so /usr/lib/ && sudo ldconfig` | `ldconfig -p \| grep rkllm` |
| librknnrt.so | `third_party/rknn-llm/examples/multimodal_model_demo/deploy/3rdparty/librknnrt/Linux/librknn_api/aarch64/` | `sudo cp <上述路径>/librknnrt.so /usr/lib/ && sudo ldconfig` | `ldconfig -p \| grep rknn` |

**不安装到系统时**：运行 demo 前设置  
`export LD_LIBRARY_PATH=third_party/rknn-llm/rkllm-runtime/Linux/librkllm_api/aarch64:$LD_LIBRARY_PATH`  
（多模态需同时包含 rknn 库所在目录。）

---

## 3. 多模态 Demo 专用依赖

| 依赖 | 安装命令 | 用途 | 验证 |
| :--- | :--- | :--- | :--- |
| OpenCV（含 pkg-config） | `sudo apt install -y libopencv-dev` | 图像读取与预处理（Qwen3-VL、InternVL 等） | `pkg-config --modversion opencv4` |

---

## 4. 性能测试前必做（强烈建议）

| 操作 | 命令 | 说明 |
| :--- | :--- | :--- |
| 锁定性能模式 | `sudo bash scripts/fix_freq_rk3588.sh` | 将 CPU/DDR/NPU/GPU 设为 performance，否则 TPS 波动大、数值偏低。每次重启后需重新执行。 |

---

## 5. 安装顺序建议

1. `apt update && apt install -y build-essential cmake git libopencv-dev`
2. 拷贝 `librkllmrt.so`、`librknnrt.so` 到 `/usr/lib` 并 `ldconfig`
3. 运行 `fix_freq_rk3588.sh` 后再做 benchmark

---

## 6. 常见问题

| 现象 | 原因 | 处理 |
| :--- | :--- | :--- |
| `error while loading shared libraries: librkllmrt.so` | 未安装或未在 LD_LIBRARY_PATH 中 | 按第 2 节安装到 `/usr/lib` 或设置 `LD_LIBRARY_PATH` |
| TPS 很低或波动大 | 未设性能模式 | 执行 `sudo bash scripts/fix_freq_rk3588.sh` |
| 多模态 demo 编译报错找不到 OpenCV | 未装 libopencv-dev | `sudo apt install -y libopencv-dev` |
| 多模态 demo 找不到 rknn/llm 头文件或库 | CMake 未指向 rknn-llm 路径 | 使用工作区 `demos/CMakeLists.txt` 或 Qengineering 仓库自带的 CMake 配置 |

---

*本文档随实际跑通 Demo 的过程持续补充，所有条目均经过当前环境验证。*
