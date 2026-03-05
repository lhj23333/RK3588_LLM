#!/usr/bin/env python3
import os
import sys
import subprocess
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
    
    # 默认开启 fix_freq_rk3588.sh 稳定模型性能
    fix_freq_script = os.path.join(workspace_root, "scripts", "fix_freq_rk3588.sh")
    if os.path.exists(fix_freq_script):
        print("Running fix_freq_rk3588.sh to stabilize performance...")
        try:
            subprocess.run(["sudo", "bash", fix_freq_script], check=True)
        except subprocess.CalledProcessError as e:
            print(f"Warning: Failed to run fix_freq_rk3588.sh (needs sudo). Error: {e}")

def main():
    parser = argparse.ArgumentParser(description="RK3588 LLM/VLM Benchmark Framework")
    parser.add_argument("--model", nargs="+", default=["all"], help="Specify models to benchmark. Use 'all' for all models.")
    parser.add_argument("--config", default="conf/models_config.yaml", help="Path to models configuration file.")
    
    args = parser.parse_args()
    
    workspace_root = os.path.dirname(os.path.abspath(__file__))
    setup_environment(workspace_root)
    
    config_path = os.path.join(workspace_root, args.config)
    
    if not os.path.exists(config_path):
        print(f"Error: Configuration file not found at {config_path}")
        return
        
    runner = BenchmarkRunner(workspace_root, config_path)
    
    if "all" in args.model:
        runner.run_all()
    else:
        runner.run_all(args.model)

if __name__ == "__main__":
    main()
