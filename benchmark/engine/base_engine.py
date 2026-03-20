import os
import subprocess
import time
from benchmark.profiler.memory_tracker import ProcessDRAMTracker

class BaseEngine:
    def __init__(self, config, workspace_root: str):
        self.config = config
        self.workspace_root = workspace_root
        self.env = os.environ.copy()
        self.tracker = ProcessDRAMTracker()
        
        # Setup LD_LIBRARY_PATH based on project structure
        rkllm_api = os.path.join(workspace_root, "third_party", "rknn-llm", "rkllm-runtime", "Linux", "librkllm_api", "aarch64")
        rknn_api = os.path.join(workspace_root, "third_party", "rknn-llm", "examples", "multimodal_model_demo", "deploy", "3rdparty", "librknnrt", "Linux", "librknn_api", "aarch64")
        
        current_ld = self.env.get("LD_LIBRARY_PATH", "")
        self.env["LD_LIBRARY_PATH"] = f"{rknn_api}:{rkllm_api}:{current_ld}"
        
        # 保持级别为 1，确保底层 parser 仍能抓取 TPS 数据，但我们在上层使用精确的 DRAM 追踪
        self.env["RKLLM_LOG_LEVEL"] = "1"

    def _build_cmd(self, **kwargs):
        raise NotImplementedError("Subclasses should implement this method.")

    def run(self, prompt: str, timeout: int = 900, **kwargs):
        cmd = self._build_cmd(**kwargs)
        
        start_time = time.time()
        process = None
        try:
            # We use Popen with bufsize=0 (unbuffered) to avoid deadlock while reading char by char
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=self.env,
                cwd=self.workspace_root,
                bufsize=0
            )
            
            # 绑定 DRAM 追踪器到该进程 PID
            self.tracker.set_pid(process.pid)
            
            output_bytes = bytearray()
            found_ready = False
            
            # Wait for "user" prompt indicating model is fully loaded and ready
            while True:
                # Check for timeout
                if time.time() - start_time > timeout:
                    break
                    
                char = process.stdout.read(1) if process.stdout else b''
                if not char:
                    break
                    
                output_bytes.extend(char)
                
                # C++ demo typically prints "user:" or just "user" at the end of the init
                if output_bytes.lower().endswith(b"user:") or output_bytes.lower().endswith(b"user"):
                    found_ready = True
                    break
                    
            if not found_ready:
                process.kill()
                duration = time.time() - start_time
                out_str = output_bytes.decode('utf-8', errors='replace')
                return False, f"Crash/Error: Did not find ready prompt.\nOutput: {out_str}", duration, {}
                
            # [T1 Stage] Model loaded, KV-Cache pre-allocated completely
            time.sleep(0.5) # Let memory stabilize
            
            # 此时 RKLLM 已经完成了模型的 load 并且根据 context len 预分配了完整的 KV-Cache DRAM
            init_dram_mb = self.tracker.get_process_dram_mb()
            print(f"[Profiler] Init DRAM (Weights + KV-Cache): {init_dram_mb:.2f} MB")
            
            # The demo apps expect questions on stdin, separated by newlines, and "exit" to quit
            input_data = f"{prompt}\nexit\n".encode('utf-8')
            output_remainder, _ = process.communicate(input=input_data, timeout=timeout)
            
            duration = time.time() - start_time
            
            full_output = output_bytes + (output_remainder or b"")
            out_str = full_output.decode('utf-8', errors='replace')
            
            # Parse metrics early to get the real peak memory
            from benchmark.parser import parse_rkllm_metrics
            parsed_metrics = parse_rkllm_metrics(out_str)
            
            # Use parsed VmHWM if available, otherwise fallback to current RSS
            if parsed_metrics.get("peak_memory_gb", 0.0) > 0:
                total_peak_mb = parsed_metrics["peak_memory_gb"] * 1024.0
            else:
                total_peak_mb = init_dram_mb # Fallback
                
            runtime_buffer_mb = max(0.0, total_peak_mb - init_dram_mb)
            
            print(f"[Profiler] Runtime Buffer: {runtime_buffer_mb:.2f} MB | Total Peak DRAM (VmHWM): {total_peak_mb:.2f} MB")
            
            mem_metrics = {
                "model_data_mb": init_dram_mb,              # Mapped to Init DRAM
                "kv_cache_overhead_mb": runtime_buffer_mb,  # Mapped to Runtime Buffer
                "total_peak_mb": total_peak_mb              # Mapped to Total Peak (VmHWM)
            }
            
            if process.returncode != 0:
                return False, f"Crash/Error (Code: {process.returncode})\nOutput: {out_str}", duration, mem_metrics
            
            return True, out_str, duration, mem_metrics
            
        except subprocess.TimeoutExpired:
            if process is not None:
                process.kill()
            return False, f"Timeout after {timeout} seconds", time.time() - start_time, {}
        except Exception as e:
            return False, f"Exception: {str(e)}", time.time() - start_time, {}
