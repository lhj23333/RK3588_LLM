import os
import subprocess
import time
import codecs
import threading
import select
from benchmark.profiler.cpu_tracker import ProcessCPUTracker
from benchmark.profiler.memory_tracker import ProcessDRAMTracker

class BaseEngine:
    def __init__(self, config, workspace_root: str):
        self.config = config
        self.workspace_root = workspace_root
        self.env = os.environ.copy()
        self.tracker = ProcessDRAMTracker()
        self.cpu_tracker = ProcessCPUTracker()
        # Log hook (e.g. GUI can inject a sink). Default preserves current behavior.
        self.log_fn = print
        # Stream hook for incremental model output.
        self.stream_fn = None
        # Metrics hook for structured runtime profiler updates.
        self.metrics_fn = None
        
        # Setup LD_LIBRARY_PATH based on project structure
        rkllm_api = os.path.join(workspace_root, "third_party", "rknn-llm", "rkllm-runtime", "Linux", "librkllm_api", "aarch64")
        rknn_api = os.path.join(workspace_root, "third_party", "rknn-llm", "examples", "multimodal_model_demo", "deploy", "3rdparty", "librknnrt", "Linux", "librknn_api", "aarch64")
        
        current_ld = self.env.get("LD_LIBRARY_PATH", "")
        self.env["LD_LIBRARY_PATH"] = f"{rknn_api}:{rkllm_api}:{current_ld}"
        
        # 保持级别为 1，确保底层 parser 仍能抓取 TPS 数据，但我们在上层使用精确的 DRAM 追踪
        self.env["RKLLM_LOG_LEVEL"] = "1"

    def _build_cmd(self, **kwargs):
        raise NotImplementedError("Subclasses should implement this method.")

    def _emit_metrics(self, metrics: dict):
        if not metrics or self.metrics_fn is None:
            return
        try:
            self.metrics_fn(metrics)
        except Exception:
            pass

    def run(self, prompt: str, timeout: int = 900, cancel_event=None, **kwargs):
        cmd = self._build_cmd(**kwargs)

        def _emit_stream(text: str):
            if not text:
                return
            if self.stream_fn is None:
                return
            try:
                self.stream_fn(text)
            except Exception:
                pass

        def _is_cancelled() -> bool:
            if cancel_event is None:
                return False
            try:
                return bool(cancel_event.is_set())
            except Exception:
                return False
        
        start_time = time.time()
        process = None
        init_dram_mb = None
        live_peak_mb = 0.0
        last_avg_cpu_usage = 0.0
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
            self.cpu_tracker.set_pid(process.pid)
            
            output_bytes = bytearray()
            output_lock = threading.Lock()
            found_ready = False

            def _decode_output() -> str:
                with output_lock:
                    return bytes(output_bytes).decode("utf-8", errors="replace")

            def _stop_process():
                if process is None or process.poll() is not None:
                    return
                try:
                    process.terminate()
                    process.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    try:
                        process.kill()
                        process.wait(timeout=2.0)
                    except Exception:
                        pass
                except Exception:
                    try:
                        process.kill()
                    except Exception:
                        pass

            def _cancelled_result():
                nonlocal live_peak_mb, last_avg_cpu_usage
                duration = time.time() - start_time
                avg_cpu_usage = self.cpu_tracker.stop()
                if avg_cpu_usage <= 0:
                    avg_cpu_usage = last_avg_cpu_usage

                current_dram_mb = self.tracker.get_process_dram_mb()
                if current_dram_mb > 0:
                    live_peak_mb = max(live_peak_mb, current_dram_mb)

                runtime_buffer_mb = None
                if init_dram_mb is not None and live_peak_mb > 0:
                    runtime_buffer_mb = max(0.0, live_peak_mb - init_dram_mb)

                self._emit_metrics(
                    {
                        "stage": "cancelled",
                        "status": "cancelled",
                        "init_dram_mb": init_dram_mb,
                        "current_dram_mb": current_dram_mb if current_dram_mb > 0 else None,
                        "runtime_buffer_mb": runtime_buffer_mb,
                        "total_peak_mb": live_peak_mb if live_peak_mb > 0 else None,
                        "avg_cpu_usage_percent": avg_cpu_usage if avg_cpu_usage > 0 else None,
                        "prefill_tps": None,
                        "generate_tps": None,
                        "duration_s": duration,
                    }
                )

                mem_metrics = {
                    "model_data_mb": init_dram_mb,
                    "kv_cache_overhead_mb": runtime_buffer_mb,
                    "total_peak_mb": live_peak_mb if live_peak_mb > 0 else None,
                    "avg_cpu_usage_percent": avg_cpu_usage if avg_cpu_usage > 0 else None,
                }
                out_str = _decode_output()
                if out_str.strip():
                    out_str = f"Cancelled by user\nOutput:\n{out_str}"
                else:
                    out_str = "Cancelled by user"
                return False, out_str, duration, mem_metrics
            
            # Wait for "user" prompt indicating model is fully loaded and ready
            while True:
                if _is_cancelled():
                    _stop_process()
                    return _cancelled_result()

                # Check for timeout
                if time.time() - start_time > timeout:
                    break

                if process.poll() is not None:
                    break

                if process.stdout is None:
                    break

                readable, _, _ = select.select([process.stdout], [], [], 0.05)
                if not readable:
                    continue

                char = process.stdout.read(1)
                if not char:
                    break
                    
                with output_lock:
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

            if _is_cancelled():
                _stop_process()
                return _cancelled_result()
            
            # 此时 RKLLM 已经完成了模型的 load 并且根据 context len 预分配了完整的 KV-Cache DRAM
            init_dram_mb = self.tracker.get_process_dram_mb()
            live_peak_mb = max(live_peak_mb, init_dram_mb)
            self.log_fn(f"[Profiler] Init DRAM (Weights + KV-Cache): {init_dram_mb:.2f} MB")
            self._emit_metrics(
                {
                    "stage": "init",
                    "status": "running",
                    "init_dram_mb": init_dram_mb,
                    "current_dram_mb": init_dram_mb,
                    "runtime_buffer_mb": 0.0,
                    "total_peak_mb": live_peak_mb,
                    "avg_cpu_usage_percent": None,
                    "prefill_tps": None,
                    "generate_tps": None,
                    "duration_s": time.time() - start_time,
                }
            )
            
            # The demo apps expect questions on stdin, separated by newlines, and "exit" to quit
            input_data = f"{prompt}\nexit\n".encode('utf-8')
            self.cpu_tracker.start()

            if process.stdin is None:
                raise RuntimeError("Subprocess stdin is not available.")
            process.stdin.write(input_data)
            process.stdin.flush()
            process.stdin.close()

            read_errors = []

            def _reader_loop():
                if process.stdout is None:
                    return
                decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
                try:
                    while True:
                        chunk = process.stdout.read(256)
                        if not chunk:
                            break
                        with output_lock:
                            output_bytes.extend(chunk)
                        text_chunk = decoder.decode(chunk, final=False)
                        _emit_stream(text_chunk)
                    tail = decoder.decode(b"", final=True)
                    _emit_stream(tail)
                except Exception as e:
                    read_errors.append(e)

            reader_thread = threading.Thread(target=_reader_loop, daemon=True)
            reader_thread.start()

            # 必须在子进程仍存活时采样 CPU；wait() 返回后子进程已被回收，/proc/<pid> 消失会导致 tick 差分为 0。
            wait_started = time.time()
            poll_interval_s = 0.05
            metrics_emit_interval_s = 0.5
            last_metrics_emit = 0.0
            while True:
                if _is_cancelled():
                    _stop_process()
                    reader_thread.join(timeout=2.0)
                    return _cancelled_result()

                self.cpu_tracker.sample()
                now = time.time()
                if init_dram_mb is not None and now - last_metrics_emit >= metrics_emit_interval_s:
                    current_dram_mb = self.tracker.get_process_dram_mb()
                    if current_dram_mb > 0:
                        live_peak_mb = max(live_peak_mb, current_dram_mb)
                    with output_lock:
                        partial_output = bytes(output_bytes).decode("utf-8", errors="replace")
                    from benchmark.parser import parse_rkllm_metrics

                    live_metrics = parse_rkllm_metrics(partial_output)
                    self._emit_metrics(
                        {
                            "stage": "running",
                            "status": "running",
                            "init_dram_mb": init_dram_mb,
                            "current_dram_mb": current_dram_mb if current_dram_mb > 0 else None,
                            "runtime_buffer_mb": max(0.0, current_dram_mb - init_dram_mb) if current_dram_mb > 0 else None,
                            "total_peak_mb": live_peak_mb if live_peak_mb > 0 else None,
                            "avg_cpu_usage_percent": self.cpu_tracker.get_avg_cpu_percent_so_far(now_wall=now),
                            "prefill_tps": live_metrics.get("prefill_tps") or None,
                            "generate_tps": live_metrics.get("generate_tps") or None,
                            "duration_s": now - start_time,
                        }
                    )
                    last_metrics_emit = now
                if process.poll() is not None:
                    break
                if time.time() - wait_started > timeout:
                    process.kill()
                    reader_thread.join(timeout=2.0)
                    timeout_duration = time.time() - start_time
                    avg_cpu_usage = self.cpu_tracker.stop()
                    last_avg_cpu_usage = avg_cpu_usage
                    current_dram_mb = self.tracker.get_process_dram_mb()
                    if current_dram_mb > 0:
                        live_peak_mb = max(live_peak_mb, current_dram_mb)
                    self._emit_metrics(
                        {
                            "stage": "timeout",
                            "status": "timeout",
                            "init_dram_mb": init_dram_mb,
                            "current_dram_mb": current_dram_mb if current_dram_mb > 0 else None,
                            "runtime_buffer_mb": max(0.0, live_peak_mb - init_dram_mb) if init_dram_mb is not None and live_peak_mb > 0 else None,
                            "total_peak_mb": live_peak_mb if live_peak_mb > 0 else None,
                            "avg_cpu_usage_percent": avg_cpu_usage if avg_cpu_usage > 0 else None,
                            "prefill_tps": None,
                            "generate_tps": None,
                            "duration_s": timeout_duration,
                        }
                    )
                    raise subprocess.TimeoutExpired(cmd, timeout)
                time.sleep(poll_interval_s)

            reader_thread.join(timeout=2.0)

            if read_errors:
                raise RuntimeError(f"Failed to read subprocess stdout: {read_errors[0]}")
            
            duration = time.time() - start_time
            avg_cpu_usage = self.cpu_tracker.stop()
            last_avg_cpu_usage = avg_cpu_usage
            
            with output_lock:
                full_output = bytes(output_bytes)
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
            final_status = "success" if process.returncode == 0 else "error"
            final_stage = "finished" if process.returncode == 0 else "error"
            
            self.log_fn(f"[Profiler] Runtime Buffer: {runtime_buffer_mb:.2f} MB | Total Peak DRAM (VmHWM): {total_peak_mb:.2f} MB")
            self.log_fn(f"[Profiler] Avg Runtime CPU Usage: {avg_cpu_usage:.2f}%")
            self._emit_metrics(
                {
                    "stage": final_stage,
                    "status": final_status,
                    "init_dram_mb": init_dram_mb,
                    "current_dram_mb": None,
                    "runtime_buffer_mb": runtime_buffer_mb,
                    "total_peak_mb": total_peak_mb,
                    "avg_cpu_usage_percent": avg_cpu_usage,
                    "prefill_tps": parsed_metrics.get("prefill_tps") or None,
                    "generate_tps": parsed_metrics.get("generate_tps") or None,
                    "duration_s": duration,
                }
            )
            
            mem_metrics = {
                "model_data_mb": init_dram_mb,              # Mapped to Init DRAM
                "kv_cache_overhead_mb": runtime_buffer_mb,  # Mapped to Runtime Buffer
                "total_peak_mb": total_peak_mb,             # Mapped to Total Peak (VmHWM)
                "avg_cpu_usage_percent": avg_cpu_usage      # Average CPU usage during runtime stage
            }
            
            if process.returncode != 0:
                return False, f"Crash/Error (Code: {process.returncode})\nOutput: {out_str}", duration, mem_metrics
            
            return True, out_str, duration, mem_metrics
            
        except subprocess.TimeoutExpired:
            if process is not None:
                process.kill()
            avg_cpu_usage = self.cpu_tracker.stop()
            if avg_cpu_usage <= 0:
                avg_cpu_usage = last_avg_cpu_usage
            timeout_metrics = {"avg_cpu_usage_percent": avg_cpu_usage} if avg_cpu_usage > 0 else {}
            return False, f"Timeout after {timeout} seconds", time.time() - start_time, timeout_metrics
        except Exception as e:
            avg_cpu_usage = self.cpu_tracker.stop()
            if avg_cpu_usage <= 0:
                avg_cpu_usage = last_avg_cpu_usage
            current_dram_mb = self.tracker.get_process_dram_mb()
            if current_dram_mb > 0:
                live_peak_mb = max(live_peak_mb, current_dram_mb)
            self._emit_metrics(
                {
                    "stage": "error",
                    "status": "error",
                    "init_dram_mb": init_dram_mb,
                    "current_dram_mb": current_dram_mb if current_dram_mb > 0 else None,
                    "runtime_buffer_mb": max(0.0, live_peak_mb - init_dram_mb) if init_dram_mb is not None and live_peak_mb > 0 else None,
                    "total_peak_mb": live_peak_mb if live_peak_mb > 0 else None,
                    "avg_cpu_usage_percent": avg_cpu_usage if avg_cpu_usage > 0 else None,
                    "prefill_tps": None,
                    "generate_tps": None,
                    "duration_s": time.time() - start_time,
                }
            )
            error_metrics = {"avg_cpu_usage_percent": avg_cpu_usage} if avg_cpu_usage > 0 else {}
            return False, f"Exception: {str(e)}", time.time() - start_time, error_metrics
