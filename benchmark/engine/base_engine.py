import os
import subprocess
import time
from benchmark.profiler.memory_tracker import RK3588MemoryTracker

class BaseEngine:
    def __init__(self, config, workspace_root: str):
        self.config = config
        self.workspace_root = workspace_root
        self.env = os.environ.copy()
        self.tracker = RK3588MemoryTracker()
        
        # Setup LD_LIBRARY_PATH based on project structure
        rkllm_api = os.path.join(workspace_root, "third_party", "rknn-llm", "rkllm-runtime", "Linux", "librkllm_api", "aarch64")
        rknn_api = os.path.join(workspace_root, "third_party", "rknn-llm", "examples", "multimodal_model_demo", "deploy", "3rdparty", "librknnrt", "Linux", "librknn_api", "aarch64")
        
        current_ld = self.env.get("LD_LIBRARY_PATH", "")
        self.env["LD_LIBRARY_PATH"] = f"{rknn_api}:{rkllm_api}:{current_ld}"
        self.env["RKLLM_LOG_LEVEL"] = "1"

    def _build_cmd(self, **kwargs):
        raise NotImplementedError("Subclasses should implement this method.")

    def run(self, prompt: str, timeout: int = 300, **kwargs):
        cmd = self._build_cmd(**kwargs)
        
        # [T0 Stage] Clear caches and get baseline memory
        self.tracker.clear_caches()
        time.sleep(1.0) # Let system settle
        mem_base = self.tracker.get_system_used_memory_mb()
        print(f"[Profiler] Base Memory: {mem_base:.2f} MB")
        
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
                
            # [T1 Stage] Model loaded, no KV-Cache yet
            time.sleep(0.5) # Let memory stabilize
            mem_loaded = self.tracker.get_system_used_memory_mb()
            model_data_mb = max(0, mem_loaded - mem_base)
            print(f"[Profiler] Model Data Memory: {model_data_mb:.2f} MB")
            
            # [T2 Stage] Start tracking peak memory for dynamic KV-Cache overhead
            self.tracker.start_tracking()
            
            # The demo apps expect questions on stdin, separated by newlines, and "exit" to quit
            input_data = f"{prompt}\nexit\n".encode('utf-8')
            output_remainder, _ = process.communicate(input=input_data, timeout=timeout)
            
            # [End] Stop tracking and calculate KV cache overhead
            mem_peak = self.tracker.stop_tracking()
            kv_cache_mb = max(0, mem_peak - mem_loaded)
            total_peak_mb = max(0, mem_peak - mem_base)
            
            print(f"[Profiler] KV-Cache Overhead: {kv_cache_mb:.2f} MB | Total Peak: {total_peak_mb:.2f} MB")
            
            duration = time.time() - start_time
            
            full_output = output_bytes + (output_remainder or b"")
            out_str = full_output.decode('utf-8', errors='replace')
            
            mem_metrics = {
                "model_data_mb": model_data_mb,
                "kv_cache_overhead_mb": kv_cache_mb,
                "total_peak_mb": total_peak_mb
            }
            
            if process.returncode != 0:
                return False, f"Crash/Error (Code: {process.returncode})\nOutput: {out_str}", duration, mem_metrics
            
            return True, out_str, duration, mem_metrics
            
        except subprocess.TimeoutExpired:
            if process is not None:
                process.kill()
            self.tracker.stop_tracking()
            return False, f"Timeout after {timeout} seconds", time.time() - start_time, {}
        except Exception as e:
            self.tracker.stop_tracking()
            return False, f"Exception: {str(e)}", time.time() - start_time, {}
