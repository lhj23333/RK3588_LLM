#!/bin/bash

echo "=================================================="
echo "  RK3588 RAM & NPU Monitor"
echo "  Press Ctrl+C to stop"
echo "=================================================="

while true; do
    echo "--- $(date '+%Y-%m-%d %H:%M:%S') ---"
    
    # 打印内存使用情况 (仅显示 Mem 行)
    free -h | grep -E "total|Mem"
    
    # 打印 NPU 负载 (需要 root 权限或 debugfs 挂载)
    if [ -e /sys/kernel/debug/rknpu/load ]; then
        echo "NPU Load:"
        cat /sys/kernel/debug/rknpu/load
    else
        echo "NPU Load: [Unavailable - requires root or debugfs]"
    fi
    
    echo ""
    sleep 2
done
