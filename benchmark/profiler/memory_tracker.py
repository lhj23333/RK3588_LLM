import os

class ProcessDRAMTracker:
    def __init__(self):
        self.pid = None

    def set_pid(self, pid: int):
        self.pid = pid

    def get_process_dram_mb(self):
        """
        读取 /proc/<pid>/status 获取 VmRSS (Resident Set Size)
        这是进程在物理 DRAM 中实际占用的空间（包含映射的 NPU dma_buf）
        """
        if not self.pid:
            return 0.0
            
        status_file = f"/proc/{self.pid}/status"
        if not os.path.exists(status_file):
            return 0.0
            
        try:
            with open(status_file, 'r') as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        # VmRSS: 1024560 kB
                        rss_kb = int(line.split()[1])
                        return rss_kb / 1024.0
        except Exception:
            return 0.0
        return 0.0
