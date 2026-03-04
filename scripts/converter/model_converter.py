#!/usr/bin/env python3
"""
RK3588 LLM 模型自动下载与转换脚本
支持: Qwen3 系列 (纯文本 LLM)
"""

import os
import sys
import json
import argparse
import subprocess
from pathlib import Path
from typing import Optional, List

# ============================================
# 配置项
# ============================================

# 支持的模型列表
SUPPORTED_MODELS = {
    # Qwen3 纯文本 LLM
    "qwen3-0.6b": {
        "model_id": "Qwen/Qwen3-0.6B",
        "type": "llm",
        "params": "0.6B",
        "description": "Qwen3 0.6B 参数模型"
    },
    "qwen3-1.7b": {
        "model_id": "Qwen/Qwen3-1.7B", 
        "type": "llm",
        "params": "1.7B",
        "description": "Qwen3 1.7B 参数模型"
    },
    "qwen3-4b": {
        "model_id": "Qwen/Qwen3-4B",
        "type": "llm", 
        "params": "4B",
        "description": "Qwen3 4B 参数模型"
    },
    "qwen3-8b": {
        "model_id": "Qwen/Qwen3-8B",
        "type": "llm",
        "params": "8B",
        "description": "Qwen3 8B 参数模型 (W4A16 推荐)"
    },
}

# 默认量化配置
DEFAULT_QUANT_CONFIG = {
    "qwen3-0.6b": "w8a8",
    "qwen3-1.7b": "w8a8", 
    "qwen3-4b": "w8a8",
    "qwen3-8b": "w4a16",  # 8B 推荐用 w4a16
}

# 默认校准数据
DEFAULT_CALIBRATION_DATA = [
    {"input": "你好，请介绍一下你自己。", "target": "你好！我是人工智能助手。"},
    {"input": "什么是人工智能？", "target": "人工智能是计算机科学的一个分支。"},
    {"input": "请用Python写一个Hello World程序。", "target": "print('Hello World')"},
    {"input": "1+1等于多少？", "target": "1+1=2"},
    {"input": "请解释一下深度学习的概念。", "target": "深度学习是机器学习的一个子领域。"},
]


# ============================================
# 模型下载模块
# ============================================

def check_dependencies():
    """检查必要的依赖包"""
    print("=" * 60)
    print("检查依赖...")
    print("=" * 60)
    
    required_packages = [
        ("torch", "PyTorch"),
        ("transformers", "Transformers"),
        ("modelscope", "ModelScope"),
    ]
    
    missing = []
    for package, name in required_packages:
        try:
            __import__(package)
            print(f"✓ {name} 已安装")
        except ImportError:
            print(f"✗ {name} 未安装")
            missing.append(package)
    
    if missing:
        print(f"\n缺少依赖包: {', '.join(missing)}")
        print("请运行: pip install " + " ".join(missing))
        return False
    
    return True


def download_model_modelscope(model_id: str, cache_dir: str = None) -> str:
    """使用 ModelScope 下载模型"""
    from modelscope import snapshot_download
    
    if cache_dir is None:
        cache_dir = os.path.expanduser("~/.cache/modelscope/hub")
    
    print(f"\n正在从 ModelScope 下载模型: {model_id}")
    print(f"缓存目录: {cache_dir}")
    
    model_path = snapshot_download(
        model_id,
        cache_dir=cache_dir,
        revision="master"
    )
    
    print(f"✓ 模型下载完成: {model_path}")
    return model_path


def download_model_huggingface(model_id: str, cache_dir: str = None) -> str:
    """使用 HuggingFace 下载模型"""
    from huggingface_hub import snapshot_download
    
    if cache_dir is None:
        cache_dir = os.path.expanduser("~/.cache/huggingface/hub")
    
    print(f"\n正在从 HuggingFace 下载模型: {model_id}")
    print(f"缓存目录: {cache_dir}")
    
    # 设置镜像（国内用户）
    if "HF_ENDPOINT" not in os.environ:
        os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
        print(f"已设置 HuggingFace 镜像: {os.environ['HF_ENDPOINT']}")
    
    model_path = snapshot_download(
        model_id,
        cache_dir=cache_dir,
        local_dir_use_symlinks=False
    )
    
    print(f"✓ 模型下载完成: {model_path}")
    return model_path


def download_model(model_name: str, source: str = "modelscope", cache_dir: str = None) -> str:
    """下载模型"""
    if model_name not in SUPPORTED_MODELS:
        raise ValueError(f"不支持的模型: {model_name}。支持的模型: {list(SUPPORTED_MODELS.keys())}")
    
    model_id = SUPPORTED_MODELS[model_name]["model_id"]
    
    if source == "modelscope":
        return download_model_modelscope(model_id, cache_dir)
    elif source == "huggingface":
        return download_model_huggingface(model_id, cache_dir)
    else:
        raise ValueError(f"不支持的下载源: {source}")


# ============================================
# 模型转换模块
# ============================================

def generate_calibration_data(output_path: str, custom_data: List[dict] = None):
    """生成量化校准数据"""
    data = custom_data if custom_data else DEFAULT_CALIBRATION_DATA
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"✓ 校准数据已生成: {output_path}")


def convert_to_rkllm(
    model_path: str,
    output_path: str,
    target_platform: str = "RK3588",
    quantized_dtype: str = "w8a8",
    num_npu_core: int = 3,
    max_context: int = 4096,
    device: str = "cuda",
    dataset_path: str = None
):
    """将 HuggingFace 模型转换为 RKLLM 格式"""
    from rkllm.api import RKLLM
    
    print("\n" + "=" * 60)
    print("开始转换模型为 RKLLM 格式")
    print("=" * 60)
    print(f"模型路径: {model_path}")
    print(f"目标平台: {target_platform}")
    print(f"量化类型: {quantized_dtype}")
    print(f"NPU核心数: {num_npu_core}")
    print(f"最大上下文: {max_context}")
    
    # 初始化 RKLLM
    llm = RKLLM()
    
    # 加载模型
    print("\n[1/3] 加载 HuggingFace 模型...")
    ret = llm.load_huggingface(
        model=model_path,
        model_lora=None,
        device=device,
        dtype="float16"
    )
    
    if ret != 0:
        print("✗ 加载模型失败!")
        sys.exit(ret)
    print("✓ 模型加载成功")
    
    # 构建模型
    print("\n[2/3] 构建并量化模型...")
    
    # 根据量化类型选择算法
    if quantized_dtype in ["w8a8", "w8a8_gx"]:
        quantized_algorithm = "normal"
    elif quantized_dtype in ["w4a16", "w4a16_gx"]:
        quantized_algorithm = "grq"
    else:
        quantized_algorithm = "normal"
    
    ret = llm.build(
        do_quantization=True,
        optimization_level=1,
        quantized_dtype=quantized_dtype.upper(),
        quantized_algorithm=quantized_algorithm,
        target_platform=target_platform,
        num_npu_core=num_npu_core,
        dataset=dataset_path,
        max_context=max_context
    )
    
    if ret != 0:
        print("✗ 构建模型失败!")
        sys.exit(ret)
    print("✓ 模型构建成功")
    
    # 导出模型
    print("\n[3/3] 导出 RKLLM 模型...")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    ret = llm.export_rkllm(output_path)
    
    if ret != 0:
        print("✗ 导出模型失败!")
        sys.exit(ret)
    
    # 获取文件大小
    file_size = os.path.getsize(output_path) / (1024 ** 3)
    print(f"✓ 模型导出成功: {output_path}")
    print(f"  文件大小: {file_size:.2f} GB")
    
    return output_path


# ============================================
# 主程序
# ============================================

def list_models():
    """列出所有支持的模型"""
    print("\n支持的模型列表:")
    print("-" * 60)
    for name, info in SUPPORTED_MODELS.items():
        quant = DEFAULT_QUANT_CONFIG.get(name, "w8a8")
        print(f"  {name:<15} | {info['params']:<6} | {info['description']}")
        print(f"  {'':<15} | 推荐量化: {quant}")
    print("-" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="RK3588 LLM 模型自动下载与转换工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 列出所有支持的模型
  python model_converter.py --list

  # 下载模型
  python model_converter.py --model qwen3-0.6b --download-only

  # 下载并转换模型
  python model_converter.py --model qwen3-0.6b --convert

  # 使用自定义参数转换
  python model_converter.py --model qwen3-1.7b --convert --quant w8a8 --npu-cores 3

  # 指定已下载的模型路径进行转换
  python model_converter.py --model-path /path/to/model --output ./output.rkllm --convert
        """
    )
    
    # 模型选择
    parser.add_argument("--model", type=str, help="要下载/转换的模型名称")
    parser.add_argument("--model-path", type=str, help="已下载的模型路径（跳过下载）")
    parser.add_argument("--list", action="store_true", help="列出所有支持的模型")
    
    # 下载选项
    parser.add_argument("--source", type=str, default="modelscope", 
                       choices=["modelscope", "huggingface"],
                       help="模型下载源 (默认: modelscope)")
    parser.add_argument("--cache-dir", type=str, help="模型缓存目录")
    
    # 转换选项
    parser.add_argument("--convert", action="store_true", help="转换为 RKLLM 格式")
    parser.add_argument("--download-only", action="store_true", help="仅下载，不转换")
    parser.add_argument("--quant", type=str, choices=["w8a8", "w4a16"], 
                       help="量化类型 (默认: 根据模型自动选择)")
    parser.add_argument("--npu-cores", type=int, default=3, 
                       help="NPU 核心数 (默认: 3, RK3588)")
    parser.add_argument("--max-context", type=int, default=4096,
                       help="最大上下文长度 (默认: 4096)")
    parser.add_argument("--device", type=str, default="cuda",
                       choices=["cuda", "cpu"],
                       help="转换设备 (默认: cuda)")
    parser.add_argument("--output", type=str, help="输出文件路径")
    
    args = parser.parse_args()
    
    # 列出模型
    if args.list:
        list_models()
        return
    
    # 检查参数
    if not args.model and not args.model_path:
        parser.print_help()
        print("\n错误: 请指定 --model 或 --model-path")
        sys.exit(1)
    
    # 检查依赖
    if not check_dependencies():
        sys.exit(1)
    
    # 确定模型路径
    model_path = None
    model_name = None
    
    if args.model_path:
        model_path = args.model_path
        model_name = os.path.basename(model_path)
    elif args.model:
        model_name = args.model
        
        # 检查模型是否支持
        if model_name not in SUPPORTED_MODELS:
            print(f"错误: 不支持的模型 '{model_name}'")
            list_models()
            sys.exit(1)
        
        # 下载模型
        model_path = download_model(
            model_name,
            source=args.source,
            cache_dir=args.cache_dir
        )
    
    # 仅下载模式
    if args.download_only:
        print(f"\n✓ 模型已下载到: {model_path}")
        return
    
    # 转换模式
    if args.convert or not args.download_only:
        # 确定量化类型
        quant = args.quant
        if not quant and model_name in DEFAULT_QUANT_CONFIG:
            quant = DEFAULT_QUANT_CONFIG[model_name]
        elif not quant:
            quant = "w8a8"
        
        # 确定输出路径
        if args.output:
            output_path = args.output
        else:
            output_dir = Path(__file__).parent.parent / "models"
            model_basename = os.path.basename(model_path)
            output_path = output_dir / f"{model_basename}_{quant.upper()}_RK3588.rkllm"
        
        # 生成校准数据
        calib_dir = Path(__file__).parent / "calibration"
        dataset_path = calib_dir / "data_quant.json"
        generate_calibration_data(str(dataset_path))
        
        # 转换模型
        convert_to_rkllm(
            model_path=model_path,
            output_path=str(output_path),
            target_platform="RK3588",
            quantized_dtype=quant,
            num_npu_core=args.npu_cores,
            max_context=args.max_context,
            device=args.device,
            dataset_path=str(dataset_path)
        )
        
        print("\n" + "=" * 60)
        print("✓ 转换完成!")
        print("=" * 60)
        print(f"输出文件: {output_path}")
        print("\n部署命令示例:")
        print(f"  ./llm_demo {output_path} 2048 4096")


if __name__ == "__main__":
    main()