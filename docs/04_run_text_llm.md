# 纯文本 LLM Demo 运行指南

## 1. 编译

在工作区根目录执行：

```bash
bash scripts/build_text_llm_demo.sh
```

生成可执行文件：`demos/build/text_llm_demo`。

依赖：g++、工作区 `third_party/rknn-llm` 子模块、`librkllmrt.so`（见 [02_dependencies.md](02_dependencies.md)）。

---

## 2. 运行命令

```bash
./demos/build/text_llm_demo <模型路径.rkllm> <max_new_tokens> <max_context_len>
```

- **模型路径**：如 `models/Qwen3-0.6B-rk3588-w8a8-opt-1-hybrid-ratio-0.0.rkllm`
- **max_new_tokens**：单轮最大生成 token 数，如 512 或 2048
- **max_context_len**：最大上下文长度，须 ≤ 模型转换时的 max_context（如 4096、16384）

运行前请设置库路径（若未将 `librkllmrt.so` 安装到系统）：

```bash
export LD_LIBRARY_PATH=third_party/rknn-llm/rkllm-runtime/Linux/librkllm_api/aarch64:$LD_LIBRARY_PATH
```

需要看每轮推理耗时与峰值内存时：

```bash
export RKLLM_LOG_LEVEL=1
```

---

## 3. 各模型示例命令（3 核 NPU）

| 模型 | 命令 |
| :--- | :--- |
| Qwen3-0.6B | `./demos/build/text_llm_demo models/Qwen3-0.6B-rk3588-w8a8-opt-1-hybrid-ratio-0.0.rkllm 512 4096` |
| Qwen3-1.7B | `./demos/build/text_llm_demo models/Qwen3-1.7B-w8a8-rk3588.rkllm 512 4096` |
| Qwen3-4B | `./demos/build/text_llm_demo models/Qwen3-4B-rk3588-w8a8-opt-1-hybrid-ratio-0.0.rkllm 512 4096` |
| Qwen3-8B | **不测试**（已排除，8GB 会 OOM）；16GB 板子可尝试 `models/Qwen3-8B-rk3588-w8a8-opt-1-hybrid-ratio-0.5.rkllm` |

交互说明：输入问题后回车；输入 `exit` 退出；输入 `clear` 清 KV cache；输入 `0`/`1` 使用内置示例问题。

---

## 4. 实测数据（RK3588 8GB，RKLLM_LOG_LEVEL=1）

| 模型 | 峰值内存 (GB) | Prefill (tokens/s) | Generate (tokens/s) |
| :--- | :--- | :--- | :--- |
| Qwen3-0.6B | 1.24 | 229.93 | 11.83 |
| Qwen3-1.7B | 2.25 | 87.77 | 8.93 |
| Qwen3-4B | 4.53 | 30.50 | 4.65 |
| Qwen3-8B | - | - | 不测试（已排除，加载时 OOM） |

*Generate 为单次短回复测得，长文生成 TPS 会因序列长度有所变化。*
