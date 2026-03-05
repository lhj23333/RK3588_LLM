import os
import sys
import datetime
from .config import load_config
from .dataset import BenchmarkDataset
from .engine import create_engine
from .parser import parse_rkllm_metrics
from .reporter import MarkdownReporter

class BenchmarkRunner:
    def __init__(self, workspace_root: str, config_path: str):
        self.workspace_root = workspace_root
        self.models_config = load_config(config_path)
        self.dataset = BenchmarkDataset(workspace_root)
        self.reporter = MarkdownReporter(workspace_root)
        
        # Ensure logs directory exists
        self.logs_dir = os.path.join(self.workspace_root, "logs")
        os.makedirs(self.logs_dir, exist_ok=True)
        
    def run_all(self, target_models=None):
        results = []
        
        models_to_run = target_models if target_models else list(self.models_config.keys())
        
        for model_name in models_to_run:
            if model_name not in self.models_config:
                print(f"[Warn] Model {model_name} not found in config, skipping.")
                continue
                
            config = self.models_config[model_name]
            print(f"\n==========================================")
            print(f"Running benchmark for: {model_name} ({config.type})")
            print(f"==========================================")
            
            try:
                config.validate(self.workspace_root)
            except Exception as e:
                print(f"Validation failed: {e}")
                results.append(self._create_empty_result(model_name, config.type, f"Failed: {e}"))
                continue
            
            engine = create_engine(config, self.workspace_root)
            
            model_metrics = []
            status = "Success"
            
            # Prepare log file for this model
            log_file_path = os.path.join(self.logs_dir, f"{model_name}.log")
            
            with open(log_file_path, "w", encoding="utf-8") as log_f:
                log_f.write(f"=== Benchmark Run: {model_name} ===\n")
                log_f.write(f"Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
                if config.type == "text":
                    prompts = self.dataset.get_text_prompts()
                    for task in prompts:
                        print(f"Task {task['id']}: {task['prompt'][:20]}...")
                        success, output, duration, mem_metrics = engine.run(task['prompt'])
                        
                        log_f.write(f"--- Task {task['id']} (Prompt: {task['prompt']}) ---\n")
                        log_f.write(f"Duration: {duration:.2f}s\n")
                        log_f.write(f"Output:\n{output}\n")
                        log_f.write("-" * 50 + "\n\n")
                        
                        if not success:
                            print(f"Error occurred: {output}")
                            status = "Crash/Error"
                            break
                            
                        metrics = parse_rkllm_metrics(output)
                        metrics.update(mem_metrics)
                        model_metrics.append(metrics)
                        
                elif config.type == "vlm":
                    tasks = self.dataset.get_vlm_tasks()
                    for task in tasks:
                        print(f"Task {task['id']}: image={os.path.basename(task['image'])}, prompt='{task['prompt'][:20]}...'")
                        success, output, duration, mem_metrics = engine.run(task['prompt'], image_path=task['image'])
                        
                        log_f.write(f"--- Task {task['id']} (Image: {task['image']} | Prompt: {task['prompt']}) ---\n")
                        log_f.write(f"Duration: {duration:.2f}s\n")
                        log_f.write(f"Output:\n{output}\n")
                        log_f.write("-" * 50 + "\n\n")
                        
                        if not success:
                            print(f"Error occurred: {output}")
                            status = "Crash/Error"
                            break
                            
                        metrics = parse_rkllm_metrics(output)
                        metrics.update(mem_metrics)
                        model_metrics.append(metrics)
            
            print(f"Detailed raw log saved to: {log_file_path}")
            res = self._aggregate_metrics(model_name, config.type, model_metrics, status, config)
            results.append(res)
            
        self.reporter.generate_report(results)
        
    def _create_empty_result(self, model_name: str, model_type: str, status: str, config=None):
        return {
            "model_name": model_name,
            "type": model_type,
            "max_context": config.max_context_len if config else 0,
            "prompts_tested": 0,
            "avg_prefill_tps": 0.0,
            "avg_generate_tps": 0.0,
            "peak_memory_rkllm": 0.0,
            "model_data_mb": 0.0,
            "kv_cache_overhead_mb": 0.0,
            "total_peak_mb": 0.0,
            "npu_core_num": 0,
            "status": status
        }
        
    def _aggregate_metrics(self, model_name: str, model_type: str, metrics_list: list, status: str, config=None):
        if not metrics_list:
            return self._create_empty_result(model_name, model_type, status, config)
            
        total_prefill = sum(m.get("prefill_tps", 0.0) for m in metrics_list)
        total_gen = sum(m.get("generate_tps", 0.0) for m in metrics_list)
        peak_memories = [m.get("peak_memory_gb", 0.0) for m in metrics_list]
        max_peak_memory = max(peak_memories) if peak_memories else 0.0
        
        # Max is more representative for memory usages across different prompts
        max_model_data = max([m.get("model_data_mb", 0.0) for m in metrics_list])
        max_kv_cache = max([m.get("kv_cache_overhead_mb", 0.0) for m in metrics_list])
        max_total_peak = max([m.get("total_peak_mb", 0.0) for m in metrics_list])
        
        count = len(metrics_list)

        npu_cores = [m.get("npu_core_num", 0) for m in metrics_list]
        max_npu_core = max(npu_cores) if npu_cores else 0
        
        return {
            "model_name": model_name,
            "type": model_type,
            "max_context": config.max_context_len if config else 0,
            "prompts_tested": count,
            "avg_prefill_tps": total_prefill / count if count > 0 else 0.0,
            "avg_generate_tps": total_gen / count if count > 0 else 0.0,
            "peak_memory_rkllm": max_peak_memory,
            "model_data_mb": max_model_data,
            "kv_cache_overhead_mb": max_kv_cache,
            "total_peak_mb": max_total_peak,
            "npu_core_num": max_npu_core,
            "status": status
        }
