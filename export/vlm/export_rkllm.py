import os
import argparse
from rkllm.api import RKLLM

def main():
    parser = argparse.ArgumentParser(description="Export RKLLM Vision Model")
    parser.add_argument('--path', type=str, default='Qwen/Qwen2-VL-2B-Instruct', help='Huggingface model path')
    parser.add_argument('--target_platform', type=str, default='rk3588', help='target platform (e.g., rk3588)')
    parser.add_argument('--num_npu_core', type=int, default=3, help='npu core num')
    parser.add_argument('--quantized_dtype', type=str, default='w8a8', help='quantized dtype (w8a8, w4a16, etc)')
    parser.add_argument('--device', type=str, default='cpu', help='device (cpu or cuda)')
    parser.add_argument('--dataset', type=str, default='data_quant.json', help='path to dataset json file')
    parser.add_argument('--savepath', type=str, default=None, help='save path for .rkllm model')
    args = parser.parse_args()

    modelpath = args.path.rstrip("/")
    target_platform = args.target_platform
    num_npu_core = args.num_npu_core
    quantized_dtype = args.quantized_dtype

    savepath = args.savepath
    if not savepath:
        savepath = os.path.join(".", os.path.basename(modelpath).lower() + "_" + quantized_dtype + "_" + target_platform + ".rkllm")

    os.makedirs(os.path.dirname(os.path.abspath(savepath)), exist_ok=True)

    llm = RKLLM()
    # Load model
    print(f"Loading model from {modelpath} on {args.device} ...")
    ret = llm.load_huggingface(model=modelpath, device=args.device)
    if ret != 0:
        print('Load model failed!')
        exit(ret)

    # Build model
    print(f"Building model with dataset {args.dataset} ...")
    qparams = None
    ret = llm.build(do_quantization=True, 
                    optimization_level=1, 
                    quantized_dtype=quantized_dtype,
                    quantized_algorithm='normal', 
                    target_platform=target_platform, 
                    num_npu_core=num_npu_core, 
                    extra_qparams=qparams, 
                    dataset=args.dataset)

    if ret != 0:
        print('Build model failed!')
        exit(ret)

    # Export rkllm model
    print(f"Exporting RKLLM model to {savepath} ...")
    ret = llm.export_rkllm(savepath)
    if ret != 0:
        print('Export model failed!')
        exit(ret)

    print(f"Successfully exported to {savepath}")

if __name__ == "__main__":
    main()
