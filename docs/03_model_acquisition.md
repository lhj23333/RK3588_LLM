# RK3588 模型获取指南（本地下载后拷贝到板子）

本文档列出所有需要的预转换模型及**直接下载链接**。您可在本机（浏览器或 wget/curl）下载后，拷贝到 RK3588 的指定目录。

**说明**：当前工作区 `models/` 目录内的模型均为**本地下载后拷贝**，无需从下文链接再次下载。以下链接供他人复现或后续增补模型时使用。

当前 `models/` 中已有（仅供参考）；**8B 已删除，本项目不测试 8B（8GB 板子会 OOM）**：
- **纯文本**：Qwen3-0.6B、1.7B、4B（.rkllm）
- **Qwen3-VL-2B**：qwen3-vl-2b-instruct_w8a8_rk3588.rkllm + qwen3-vl-2b_vision_672_rk3588.rknn
- **InternVL3.5-1B**：internvl3_5-1b-instruct_w8a8_rk3588.rkllm + internvl3_5-1b_vision_rk3588.rknn
- **InternVL3.5-2B**：internvl3_5-2b-instruct_w8a8_rk3588.rkllm + internvl3_5-2b_vision_rk3588.rknn
- **InternVL3.5-4B**：internvl3_5-4b-instruct_w8a8_rk3588.rkllm + internvl3_5-4b_vision_rk3588.rknn

---

## 拷贝到板子的目录

| 模型类型 | 拷贝目标目录 |
| :--- | :--- |
| **纯文本 LLM**（.rkllm） | `rk3588_llm_workspace/models/` |
| **多模态 VLM**（.rkllm + .rknn） | **统一** `rk3588_llm_workspace/models/`（与脚本、third_party demo 一致） |

---

## 一、纯文本 Qwen3 系列（仅 .rkllm，用于 text_llm_demo）

拷贝到：**`models/`**

### 1. Qwen3-0.6B（约 953 MB）

- **推荐文件**（w8a8，通用）：  
  https://huggingface.co/dulimov/Qwen3-0.6B-rk3588-1.2.1-unsloth-16k/resolve/main/Qwen3-0.6B-rk3588-w8a8-opt-1-hybrid-ratio-0.0.rkllm  
- 下载后建议重命名为：`Qwen3-0.6B-rk3588-w8a8.rkllm`（便于命令行输入）

### 2. Qwen3-1.7B（约 2.37 GB）

- **唯一 .rkllm 文件**：  
  https://huggingface.co/GatekeeperZA/Qwen3-1.7B-RKLLM-v1.2.3/resolve/main/Qwen3-1.7B-w8a8-rk3588.rkllm  
- 拷贝到 `models/` 即可，无需改名。

### 3. Qwen3-4B（约 4.6 GB，任选一个 w8a8 即可）

- **推荐**（w8a8，opt-1）：  
  https://huggingface.co/dulimov/Qwen3-4B-rk3588-1.2.1-base/resolve/main/Qwen3-4B-rk3588-w8a8-opt-1-hybrid-ratio-0.0.rkllm  
- 下载后建议重命名为：`Qwen3-4B-rk3588-w8a8.rkllm`

### 4. Qwen3-8B（不测试）

- **说明**：8GB 板子加载会 OOM，本项目已排除 8B，不测试。以下链接仅供 16GB 板子或自测使用。  
- **w8a8**（约 8.3 GB）：  
  https://huggingface.co/dulimov/Qwen3-8B-rk3588-1.2.1-unsloth/resolve/main/Qwen3-8B-rk3588-w8a8-opt-1-hybrid-ratio-0.5.rkllm  
- 拷贝到 `models/` 时可重命名为 `Qwen3-8B-rk3588-w8a8.rkllm`。

---

## 二、多模态 Qwen3-VL-2B（.rkllm + .rknn）

需要 **1 个 .rkllm + 1 个 .rknn**（分辨率三选一）。拷贝到工作区统一目录：**`models/`**。

### 2.1 LLM 解码器（必下，约 2.37 GB）

- https://huggingface.co/GatekeeperZA/Qwen3-VL-2B-Instruct-RKLLM-v1.2.3/resolve/main/qwen3-vl-2b-instruct_w8a8_rk3588.rkllm  

### 2.2 视觉编码器（三选一，与分辨率对应）

- **448×448**（速度最快，约 812 MB）：  
  https://huggingface.co/GatekeeperZA/Qwen3-VL-2B-Instruct-RKLLM-v1.2.3/resolve/main/qwen3-vl-2b_vision_448_rk3588.rknn  

- **672×672**（推荐，约 854 MB）：  
  https://huggingface.co/GatekeeperZA/Qwen3-VL-2B-Instruct-RKLLM-v1.2.3/resolve/main/qwen3-vl-2b_vision_672_rk3588.rknn  

- **896×896**（精度最高，约 923 MB）：  
  https://huggingface.co/GatekeeperZA/Qwen3-VL-2B-Instruct-RKLLM-v1.2.3/resolve/main/qwen3-vl-2b_vision_896_rk3588.rknn  

若只下一个，建议下 **672** 的 .rknn，与上面 .rkllm 放在同一 `models/` 目录。

---

## 三、InternVL3.5 系列（Qengineering，Sync.com）

此类模型需在 **浏览器中打开 Sync.com 分享链接** 下载（不支持直接 wget）。下载得到 **.rkllm + .rknn** 两个文件后，拷贝到工作区统一目录 **`models/`**。第三方 VLM demo 以 **submodule** 形式放在 **`third_party/`**，不要直接 clone 到 demos。

### 3.1 InternVL3.5-1B

- 仓库：https://github.com/Qengineering/InternVL3.5-1B-NPU  
- 模型下载页（打开后点下载）：  
  - **.rkllm**：https://ln5.sync.com/dl/e39884100#p6b8474m-bwwirtqb-rcmsjck8-9byi6a6d  
  - **.rknn**：https://ln5.sync.com/dl/99635ce70#v7iucs3y-9bw4w4gf-ygmrkkkg-cbx9rg9j  
- 拷贝到：**`models/`**（工作区根目录，与 `run_vlm_benchmark.sh` 一致）  
- 文件名需与 README 一致：`internvl3_5-1b-instruct_w8a8_rk3588.rkllm`、`internvl3_5-1b_vision_rk3588.rknn`

### 3.2 InternVL3.5-2B

- 仓库：https://github.com/Qengineering/InternVL3.5-2B-NPU  
- 模型链接见仓库内 `models/README.md`（Sync.com），下载 .rkllm 与 .rknn 后拷贝到工作区 **`models/`**。

### 3.3 InternVL3.5-4B

- 仓库：https://github.com/Qengineering/InternVL3.5-4B-NPU  
- 模型链接见仓库内 `models/README.md`，拷贝到工作区 **`models/`**。

### 3.4 InternVL3.5-8B（不测试）

- **说明**：8GB 板子会 OOM，本项目已排除 8B，不测试。以下仅供 16GB 或后续参考。
- **仓库**：https://github.com/Qengineering/InternVL3.5-8B-NPU  
- **已知问题**：该仓库存在两处错误，**当前无法从仓库内拿到正确的 8B 下载链接**：  
  1. 主 README 的 “Installing the app” 写的是 `git clone .../Qwen3-VL-2B-NPU`（2B 仓库）。  
  2. [models 目录](https://github.com/Qengineering/InternVL3.5-8B-NPU/tree/main/models) 里的下载链接点进去也是 **2B 模型**，不是 8B。  
- **建议**：若需要 8B 的 `.rkllm` / `.rknn`（约 9GB，文件名应为 `internvl3_5-8b-instruct_w8a8_rk3588.rkllm`、`internvl3_5-8b_vision_rk3588.rknn`），可在 [InternVL3.5-8B-NPU 仓库提 Issue](https://github.com/Qengineering/InternVL3.5-8B-NPU/issues) 向维护者索要正确的 Sync.com 8B 链接，或查阅 Qengineering 官网/其它说明。  
- 拷贝到工作区 **`models/`**（若需 8B）。8GB 板子可能 OOM，本项目不测试。

#### 替代方案（拿不到 8B 链接时）

1. **用 Qwen2-VL-7B 替代（同属 8B 档、有现成预转换）**  
   - 性能与显存与 InternVL3.5-8B 接近（约 8.7GB RAM、~3.7 tokens/s）。  
   - **Qengineering**：https://github.com/Qengineering/Qwen2-VL-7B-NPU（README 内一般有 Sync.com 或说明）。  
   - **HuggingFace**：https://huggingface.co/3ib0n/Qwen2-VL-7B-rkllm（社区预转换，可能含 vision；需看仓库内文件列表确认 .rknn 是否一并提供）。  
   - 跑法参考该仓库的 demo，与 InternVL 类似（图 + 文本对话）。

2. **自行在 x86 PC 上转换 InternVL3.5-8B**  
   - 原始模型：https://huggingface.co/OpenGVLab/InternVL3_5-8B  
   - 在内存足够的 x86 上安装 rkllm-toolkit，按 rknn-llm 官方文档将 LLM 转为 .rkllm、Vision 转为 .rknn，再拷到板子。  
   - 需要一定时间和磁盘，但可得到真正的 8B 模型。

3. **向 Qengineering 索要正确链接**  
   - 在 [InternVL3.5-8B-NPU Issues](https://github.com/Qengineering/InternVL3.5-8B-NPU/issues) 提 Issue，说明 models 里链接是 2B，请维护者提供 8B 的 Sync.com 或其它下载地址。

4. **Rockchip 官方 rkllm_model_zoo（可自行查看是否有 8B）**  
   - 预转换模型集中下载：https://console.box.lenovo.com/l/l0tXb8 ，提取码：`rkllm`  
   - 官方 [rknn-llm README](https://github.com/airockchip/rknn-llm#download) 说明可在此处下载 “converted rkllm model”。  
   - 仓库未公开列出具体模型清单，**需登录后浏览目录**，看是否包含 InternVL3.5-8B 或其它 8B 档 VLM；若有则可直接下载 .rkllm/.rknn，无需用 Qengineering 的错链。

#### 其他来源排查结果（截至文档更新时）

- **HuggingFace**：以 "InternVL"、"rk3588"、"rkllm"、"8B" 等关键词搜索，未发现除 Qengineering 以外的 **InternVL3.5-8B** 预转换（.rkllm/.rknn）仓库；仅有原始权重 [OpenGVLab/InternVL3_5-8B](https://huggingface.co/OpenGVLab/InternVL3_5-8B)。  
- **ModelScope**：未找到标注为 RK3588/RKLLM 的 InternVL3.5-8B 预转换模型。  
- **GitHub**：除 [Qengineering/InternVL3.5-8B-NPU](https://github.com/Qengineering/InternVL3.5-8B-NPU) 外，未发现其它提供 InternVL3.5-8B 预转换的仓库。  
- **结论**：若坚持要 **已转好的** InternVL3.5-8B，目前只能依赖 Qengineering 修复/提供正确链接，或从官方 rkllm_model_zoo（Lenovo Box）里自行确认是否有该模型；否则用上文「替代方案」中的 Qwen2-VL-7B 或自转 InternVL3.5-8B。

---

## 四、Qwen3-VL-4B 与其它 VLM

- **Qwen3-VL-4B**：见 https://github.com/Qengineering/Qwen3-VL-4B-NPU 的 README，模型多为 Sync.com，下载后拷贝到工作区 **`models/`**。  
- **DeepSeek-R1** 等：可从 Radxa ModelScope 用 `modelscope download --model radxa/DeepSeek-R1-Distill-Qwen-1.5B_RKLLM` 在板子或本机下载（若本机下载，再拷贝到板子对应目录）。

---

## 五、本机下载方式简要说明

1. **浏览器**：直接打开上面 HuggingFace/Sync.com 链接，保存到本地，再通过 U 盘、scp、rsync 等拷到 RK3588。  
2. **wget（仅适用于 HuggingFace）**：  
   ```bash
   wget -c "https://huggingface.co/仓库/resolve/main/文件名.rkllm" -O 本地保存名.rkllm
   ```  
   Sync.com 链接不要用 wget（会下到 HTML 而不是文件）。  
3. **HuggingFace CLI**（可选）：  
   ```bash
   pip install huggingface_hub
   huggingface-cli download dulimov/Qwen3-0.6B-rk3588-1.2.1-unsloth-16k Qwen3-0.6B-rk3588-w8a8-opt-1-hybrid-ratio-0.0.rkllm --local-dir ./models
   ```

---

## 六、拷贝到板子后的目录结构示例

```
rk3588_llm_workspace/
├── models/                          # 所有模型统一放此目录
│   ├── Qwen3-0.6B-rk3588-w8a8.rkllm
│   ├── Qwen3-1.7B-w8a8-rk3588.rkllm
│   ├── Qwen3-4B-rk3588-w8a8.rkllm
│   ├── internvl3_5-1b-instruct_w8a8_rk3588.rkllm
│   ├── internvl3_5-1b_vision_rk3588.rknn
│   ├── qwen3-vl-2b-instruct_w8a8_rk3588.rkllm
│   ├── qwen3-vl-2b_vision_672_rk3588.rknn
│   └── …（其他 .rkllm/.rknn 同上文文件名）
├── third_party/                     # 第三方 VLM demo，以 submodule 形式存在
│   ├── rknn-llm/
│   ├── InternVL3.5-1B-NPU/         # git submodule update --init 后才有
│   ├── InternVL3.5-2B-NPU/
│   ├── InternVL3.5-4B-NPU/
│   ├── Qwen3-VL-2B-NPU/
│   └── Qwen3-VL-4B-NPU/
└── demos/                           # 本仓库自有的 text_llm_demo / multimodal_llm_demo 构建目录
```

完成拷贝后，运行 `git submodule update --init --recursive` 拉齐 third_party 下的 VLM demo，再按 `04_run_text_llm.md` 与 `05_run_multimodal_vlm.md` 运行。
