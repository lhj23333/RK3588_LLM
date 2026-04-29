import os
import time
from typing import Optional


class ProcessCPUTracker:
    """Track process average CPU usage (%) via /proc/<pid>/stat."""

    def __init__(self):
        self.pid = None
        self._clk_tck = os.sysconf(os.sysconf_names["SC_CLK_TCK"])
        self._start_wall = None
        self._start_ticks = None
        self._last_ticks = 0

    def set_pid(self, pid: int):
        self.pid = pid

    def sample(self) -> None:
        """在子进程仍存活时周期性调用，更新最近一次读到的 CPU ticks（供 stop 时进程已退出无法读 /proc 时使用）。"""
        self._read_process_total_cpu_ticks()

    def _read_process_total_cpu_ticks(self) -> int:
        if not self.pid:
            return 0

        stat_file = f"/proc/{self.pid}/stat"
        if not os.path.exists(stat_file):
            return 0

        try:
            with open(stat_file, "r", encoding="utf-8", errors="replace") as f:
                raw = f.read().strip()
            right_paren = raw.rfind(")")
            if right_paren <= 0:
                return 0

            fields = raw[right_paren + 2 :].split()
            if len(fields) < 15:
                return 0

            utime = int(fields[11])
            stime = int(fields[12])
            total_ticks = utime + stime
            self._last_ticks = total_ticks
            return total_ticks
        except Exception:
            return 0

    def start(self):
        self._start_wall = time.time()
        self._start_ticks = self._read_process_total_cpu_ticks()

    def _compute_avg_cpu_percent(self, end_ticks: int, end_wall: float, reset: bool) -> float:
        if self._start_wall is None or self._start_ticks is None:
            return 0.0

        if end_ticks <= 0 and self._last_ticks > 0:
            end_ticks = self._last_ticks

        elapsed = max(0.0, end_wall - self._start_wall)
        delta_ticks = max(0, end_ticks - self._start_ticks)

        if reset:
            self._start_wall = None
            self._start_ticks = None

        if elapsed <= 0.0 or delta_ticks <= 0:
            return 0.0

        cpu_seconds = float(delta_ticks) / float(self._clk_tck)
        return max(0.0, (cpu_seconds / elapsed) * 100.0)

    def get_avg_cpu_percent_so_far(self, now_wall: Optional[float] = None) -> float:
        """Return average CPU usage from start() until now without resetting tracker state."""
        if self._start_wall is None or self._start_ticks is None:
            return 0.0
        if now_wall is None:
            now_wall = time.time()
        current_ticks = self._read_process_total_cpu_ticks()
        return self._compute_avg_cpu_percent(current_ticks, now_wall, reset=False)

    def stop_and_get_avg_cpu_percent(
        self, end_ticks: Optional[int] = None, end_wall: Optional[float] = None
    ) -> float:
        if self._start_wall is None or self._start_ticks is None:
            return 0.0

        if end_wall is None:
            end_wall = time.time()
        if end_ticks is None:
            end_ticks = self._read_process_total_cpu_ticks()
        return self._compute_avg_cpu_percent(end_ticks, end_wall, reset=True)

    def stop(self) -> float:
        """Alias for benchmark callers; same as stop_and_get_avg_cpu_percent()."""
        return self.stop_and_get_avg_cpu_percent()
