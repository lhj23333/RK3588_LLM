import os
import datetime
import threading
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
        
    def run_all(self, target_models=None, event_sink=None, cancel_event=None):
        """
        Run benchmark for all (or specified) models.

        Args:
            target_models: list[str] | None
            event_sink: optional object with callbacks:
                - on_log(msg: str)
                - on_model_start(model_name, model_type, total_tasks_for_model, log_file_path)
                - on_task_start(model_name, task_dict)
                - on_task_stream(model_name, task_dict, text_chunk)
                - on_task_metric(model_name, task_dict, metrics_dict)
                - on_task_end(model_name, task_dict, success, output_text, duration_s, mem_metrics_dict, parsed_metrics_dict)
                - on_model_end(model_name, status)
                - on_run_end(report_path)
            cancel_event: optional threading.Event-like with is_set()
        """
        results = []
        
        models_to_run = target_models if target_models else list(self.models_config.keys())

        def _emit_log(msg: str):
            print(msg)
            if event_sink is not None and hasattr(event_sink, "on_log"):
                try:
                    event_sink.on_log(msg)
                except Exception:
                    # Never break benchmark because of GUI/log sink issues
                    pass

        def _is_cancelled() -> bool:
            if cancel_event is None:
                return False
            try:
                return bool(cancel_event.is_set())
            except Exception:
                return False

        def _emit_task_stream(model_name: str, task_dict: dict, text_chunk: str):
            if not text_chunk:
                return
            if event_sink is not None and hasattr(event_sink, "on_task_stream"):
                try:
                    event_sink.on_task_stream(model_name, task_dict, text_chunk)
                except Exception:
                    pass

        def _emit_task_metric(model_name: str, task_dict: dict, metrics_dict: dict):
            if not metrics_dict:
                return
            if event_sink is not None and hasattr(event_sink, "on_task_metric"):
                try:
                    event_sink.on_task_metric(model_name, task_dict, metrics_dict)
                except Exception:
                    pass
        
        for model_name in models_to_run:
            if _is_cancelled():
                _emit_log("[Info] Cancel requested, stopping benchmark before next model.")
                break

            if model_name not in self.models_config:
                _emit_log(f"[Warn] Model {model_name} not found in config, skipping.")
                continue
                
            config = self.models_config[model_name]
            _emit_log("")
            _emit_log("==========================================")
            _emit_log(f"Running benchmark for: {model_name} ({config.type})")
            _emit_log("==========================================")
            
            try:
                config.validate(self.workspace_root)
            except Exception as e:
                _emit_log(f"Validation failed: {e}")
                results.append(self._create_empty_result(model_name, config.type, f"Failed: {e}"))
                continue
            
            engine = create_engine(config, self.workspace_root)
            # Allow GUI/log sinks to receive engine profiler logs.
            try:
                engine.log_fn = _emit_log
            except Exception:
                pass
            
            model_metrics = []
            status = "Success"
            
            # Prepare log file for this model
            log_file_path = os.path.join(self.logs_dir, f"{model_name}.log")

            if config.type == "text":
                total_tasks_for_model = len(self.dataset.get_text_prompts())
            elif config.type == "vlm":
                total_tasks_for_model = len(self.dataset.get_vlm_tasks())
            else:
                total_tasks_for_model = 0

            if event_sink is not None and hasattr(event_sink, "on_model_start"):
                try:
                    event_sink.on_model_start(model_name, config.type, total_tasks_for_model, log_file_path)
                except Exception:
                    pass
            
            with open(log_file_path, "w", encoding="utf-8") as log_f:
                log_f.write(f"=== Benchmark Run: {model_name} ===\n")
                log_f.write(f"Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
                if config.type == "text":
                    prompts = self.dataset.get_text_prompts()
                    for task in prompts:
                        if _is_cancelled():
                            status = "Cancelled"
                            _emit_log("[Info] Cancel requested, stopping before next task.")
                            break

                        task_dict = {"id": task.get("id"), "prompt": task.get("prompt", "")}
                        if event_sink is not None and hasattr(event_sink, "on_task_start"):
                            try:
                                event_sink.on_task_start(model_name, task_dict)
                            except Exception:
                                pass

                        _emit_log(f"Task {task['id']}: {task['prompt'][:20]}...")
                        try:
                            engine.stream_fn = lambda chunk, mn=model_name, td=task_dict: _emit_task_stream(mn, td, chunk)
                            engine.metrics_fn = lambda metrics, mn=model_name, td=task_dict: _emit_task_metric(mn, td, metrics)
                        except Exception:
                            pass

                        try:
                            success, output, duration, mem_metrics = engine.run(task['prompt'])
                        finally:
                            try:
                                engine.stream_fn = None
                                engine.metrics_fn = None
                            except Exception:
                                pass
                        
                        log_f.write(f"--- Task {task['id']} (Prompt: {task['prompt']}) ---\n")
                        log_f.write(f"Duration: {duration:.2f}s\n")
                        log_f.write(f"Output:\n{output}\n")
                        log_f.write("-" * 50 + "\n\n")
                        
                        if not success:
                            _emit_log(f"Error occurred: {output}")
                            status = "Crash/Error"
                            parsed = {}
                            if event_sink is not None and hasattr(event_sink, "on_task_end"):
                                try:
                                    event_sink.on_task_end(model_name, task_dict, success, output, duration, mem_metrics, parsed)
                                except Exception:
                                    pass
                            break
                            
                        parsed = parse_rkllm_metrics(output)
                        metrics = dict(parsed)
                        metrics.update(mem_metrics)
                        model_metrics.append(metrics)

                        if event_sink is not None and hasattr(event_sink, "on_task_end"):
                            try:
                                event_sink.on_task_end(model_name, task_dict, success, output, duration, mem_metrics, parsed)
                            except Exception:
                                pass
                        
                elif config.type == "vlm":
                    tasks = self.dataset.get_vlm_tasks()
                    for task in tasks:
                        if _is_cancelled():
                            status = "Cancelled"
                            _emit_log("[Info] Cancel requested, stopping before next task.")
                            break

                        raw_prompt = task.get("prompt", "") or ""
                        # The underlying multimodal demo expects "<image>" to appear in the user prompt.
                        # If missing, the image may not be routed into the model at all.
                        prompt = raw_prompt
                        if "<image>" not in prompt:
                            prompt = "<image>" + prompt.lstrip()

                        task_dict = {"id": task.get("id"), "prompt": prompt, "image": task.get("image", "")}
                        if event_sink is not None and hasattr(event_sink, "on_task_start"):
                            try:
                                event_sink.on_task_start(model_name, task_dict)
                            except Exception:
                                pass

                        _emit_log(f"Task {task['id']}: image={os.path.basename(task['image'])}, prompt='{prompt[:20]}...'")
                        try:
                            engine.stream_fn = lambda chunk, mn=model_name, td=task_dict: _emit_task_stream(mn, td, chunk)
                            engine.metrics_fn = lambda metrics, mn=model_name, td=task_dict: _emit_task_metric(mn, td, metrics)
                        except Exception:
                            pass

                        try:
                            success, output, duration, mem_metrics = engine.run(prompt, image_path=task['image'])
                        finally:
                            try:
                                engine.stream_fn = None
                                engine.metrics_fn = None
                            except Exception:
                                pass
                        
                        log_f.write(f"--- Task {task['id']} (Image: {task['image']} | Prompt: {prompt}) ---\n")
                        log_f.write(f"Duration: {duration:.2f}s\n")
                        log_f.write(f"Output:\n{output}\n")
                        log_f.write("-" * 50 + "\n\n")
                        
                        if not success:
                            _emit_log(f"Error occurred: {output}")
                            status = "Crash/Error"
                            parsed = {}
                            if event_sink is not None and hasattr(event_sink, "on_task_end"):
                                try:
                                    event_sink.on_task_end(model_name, task_dict, success, output, duration, mem_metrics, parsed)
                                except Exception:
                                    pass
                            break
                            
                        parsed = parse_rkllm_metrics(output)
                        metrics = dict(parsed)
                        metrics.update(mem_metrics)
                        model_metrics.append(metrics)

                        if event_sink is not None and hasattr(event_sink, "on_task_end"):
                            try:
                                event_sink.on_task_end(model_name, task_dict, success, output, duration, mem_metrics, parsed)
                            except Exception:
                                pass
            
            _emit_log(f"Detailed raw log saved to: {log_file_path}")
            res = self._aggregate_metrics(model_name, config.type, model_metrics, status, config)
            results.append(res)

            if event_sink is not None and hasattr(event_sink, "on_model_end"):
                try:
                    event_sink.on_model_end(model_name, status)
                except Exception:
                    pass
            
        self.reporter.generate_report(results)

        report_path = getattr(self.reporter, "report_path", "")
        if event_sink is not None and hasattr(event_sink, "on_run_end"):
            try:
                event_sink.on_run_end(report_path)
            except Exception:
                pass
        
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
            "avg_cpu_usage_percent": 0.0,
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
        avg_cpu_usage = sum(m.get("avg_cpu_usage_percent", 0.0) for m in metrics_list) / len(metrics_list)
        
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
            "avg_cpu_usage_percent": avg_cpu_usage,
            "npu_core_num": max_npu_core,
            "status": status
        }
