#!/bin/bash

echo "=================================================="
echo "  RK3588 Performance Mode Setup Script"
echo "=================================================="

# 检查是否为 root 权限
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root (use sudo)"
  exit
fi

echo "1. Setting CPU to performance mode..."
for policy in /sys/devices/system/cpu/cpufreq/policy*; do
    echo performance > $policy/scaling_governor
done

echo "2. Setting DDR to performance mode..."
if [ -e /sys/class/devfreq/dmc/governor ]; then
    echo performance > /sys/class/devfreq/dmc/governor
fi

echo "3. Setting NPU to performance mode..."
if [ -e /sys/class/devfreq/fdab0000.npu/governor ]; then
    echo performance > /sys/class/devfreq/fdab0000.npu/governor
fi

echo "4. Setting GPU to performance mode..."
if [ -e /sys/class/devfreq/fb000000.gpu/governor ]; then
    echo performance > /sys/class/devfreq/fb000000.gpu/governor
fi

echo "=================================================="
echo "  All devices set to maximum performance!"
echo "=================================================="
