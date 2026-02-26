# RK3588 LLM Demo 文档说明

本目录为 RK3588 (8GB) 上运行 LLM/VLM Demo 的完整复现文档，按使用顺序阅读即可从零在板子上跑通并复现测试结果。

| 文档 | 内容 |
| :--- | :--- |
| [01_environment_setup.md](01_environment_setup.md) | 环境与性能模式、RKLLM 库部署 |
| [02_dependencies.md](02_dependencies.md) | 依赖清单（边跑边记，含验证与常见问题） |
| [03_model_acquisition.md](03_model_acquisition.md) | 模型获取（下载链接与拷贝目录） |
| [04_run_text_llm.md](04_run_text_llm.md) | 纯文本 LLM Demo 编译与运行 |
| [05_run_multimodal_vlm.md](05_run_multimodal_vlm.md) | 多模态 VLM Demo 编译与运行 |
| [06_benchmark_guide.md](06_benchmark_guide.md) | 性能测试方法（fix_freq、RKLLM_LOG_LEVEL、DRAM 监控） |
| [07_feasibility_report.md](07_feasibility_report.md) | 模型可行性报告（可跑/不可跑/极限） |

**性能数据**：见工作区根目录 `results/benchmark_log.md`。

**最终报告**：见 `results/FINAL_REPORT.md`（整合可行性、benchmark 与不可行模型清单）。
