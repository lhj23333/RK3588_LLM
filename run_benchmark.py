#!/usr/bin/env python3
import os
import sys
import argparse
from benchmark.runner import BenchmarkRunner

def setup_environment(workspace_root):
    # 配置 vlm/llm 模型推理所需的运行库环境变量
    rkllm_lib = os.path.join(workspace_root, "third_party/rknn-llm/rkllm-runtime/Linux/librkllm_api/aarch64")
    rknn_lib = os.path.join(workspace_root, "third_party/rknn-llm/examples/multimodal_model_demo/deploy/3rdparty/librknnrt/Linux/librknn_api/aarch64")
    
    current_ld = os.environ.get("LD_LIBRARY_PATH", "")
    new_ld = f"{rkllm_lib}:{rknn_lib}"
    if current_ld:
        new_ld = f"{new_ld}:{current_ld}"
        
    os.environ["LD_LIBRARY_PATH"] = new_ld
    os.environ["RKLLM_LOG_LEVEL"] = "1"

def main():
    parser = argparse.ArgumentParser(description="RK3588 LLM/VLM Benchmark Framework")
    parser.add_argument("--model", nargs="+", default=["all"], help="Specify models to benchmark. Use 'all' for all models.")
    parser.add_argument("--config", default="conf/models_config.yaml", help="Path to models configuration file.")
    parser.add_argument("--gui", action="store_true", help="Launch PyQt GUI to visualize benchmark progress.")
    
    args = parser.parse_args()
    
    workspace_root = os.path.dirname(os.path.abspath(__file__))
    setup_environment(workspace_root)
    
    config_path = os.path.join(workspace_root, args.config)
    
    if not os.path.exists(config_path):
        print(f"Error: Configuration file not found at {config_path}")
        return

    if args.gui:
        from benchmark.gui_app import run_gui
        run_gui(workspace_root, config_path, preselected_models=args.model)
        return
        
    runner = BenchmarkRunner(workspace_root, config_path)
    
    if "all" in args.model:
        runner.run_all()
    else:
        runner.run_all(args.model)

if __name__ == "__main__":
    main()
