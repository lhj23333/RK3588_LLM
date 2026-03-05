import os
import time
import threading
import subprocess

class RK3588MemoryTracker:
    def __init__(self):
        self.keep_running = False
        self.peak_memory_used = 0
        self.thread = None

    def clear_caches(self):
        print("[Profiler] Attempting to clear system caches for accurate memory measurement...")
        try:
            # Try to drop caches. This requires root privileges.
            # If it fails, we continue anyway but memory measurements may be slightly less accurate.
            result = subprocess.run(
                "sync && echo 3 | sudo tee /proc/sys/vm/drop_caches > /dev/null",
                shell=True,
                check=False,
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                print("[Profiler] System caches cleared successfully.")
            else:
                print("[Profiler] Warning: Failed to clear caches (permission denied).")
                print("[Profiler] Run with sudo for accurate memory profiling, or skip if not critical.")
        except subprocess.TimeoutExpired:
            print("[Profiler] Warning: Timeout while clearing caches, skipping.")
        except Exception as e:
            print(f"[Profiler] Warning: Failed to clear caches: {e}")

    def get_system_used_memory_mb(self):
        """Parse /proc/meminfo to get current used physical memory in MB"""
        meminfo = {}
        with open('/proc/meminfo', 'r') as f:
            for line in f:
                parts = line.split(':')
                if len(parts) == 2:
                    meminfo[parts[0].strip()] = int(parts[1].split()[0].strip())
        
        # Calculate used memory. 
        # Note: Linux memory calculation -> Total - Free - Buffers - Cached - SReclaimable
        mem_total = meminfo.get('MemTotal', 0)
        mem_free = meminfo.get('MemFree', 0)
        buffers = meminfo.get('Buffers', 0)
        cached = meminfo.get('Cached', 0)
        sreclaimable = meminfo.get('SReclaimable', 0) 
        
        used_kb = mem_total - mem_free - buffers - cached - sreclaimable
        return used_kb / 1024.0

    def start_tracking(self):
        """Start a background thread to poll memory usage and find the peak"""
        self.keep_running = True
        self.peak_memory_used = self.get_system_used_memory_mb()
        self.thread = threading.Thread(target=self._poll_memory)
        self.thread.start()

    def _poll_memory(self):
        while self.keep_running:
            current_used = self.get_system_used_memory_mb()
            if current_used > self.peak_memory_used:
                self.peak_memory_used = current_used
            time.sleep(0.05)

    def stop_tracking(self):
        """Stop polling and return the peak memory recorded"""
        self.keep_running = False
        if self.thread:
            self.thread.join()
        return self.peak_memory_used
