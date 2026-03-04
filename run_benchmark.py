#!/usr/bin/env python3
import os
import argparse
from benchmark.runner import BenchmarkRunner

def main():
    parser = argparse.ArgumentParser(description="RK3588 LLM/VLM Benchmark Framework")
    parser.add_argument("--model", nargs="+", default=["all"], help="Specify models to benchmark. Use 'all' for all models.")
    parser.add_argument("--config", default="conf/models_config.yaml", help="Path to models configuration file.")
    
    args = parser.parse_args()
    
    workspace_root = os.path.dirname(os.path.abspath(__file__))
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
