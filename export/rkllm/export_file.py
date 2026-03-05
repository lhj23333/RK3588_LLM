import argparse
import os
from rkllm.api import RKLLM

def main():
    parser = argparse.ArgumentParser(description="Export RKLLM model")
    parser.add_argument("-m", "--model_path", required=True, help="Path to the huggingface model")
    parser.add_argument("-d", "--dataset", default="data_quant.json", help="Path to the quantization dataset json file")
    parser.add_argument("-t", "--target_platform", default="RK3588", help="Target platform (e.g., RK3588)")
    parser.add_argument("-q", "--quantized_dtype", default="w8a8", help="Quantized dtype (e.g., w8a8, w4a16)")
    parser.add_argument("-a", "--quantized_algorithm", default="normal", help="Quantized algorithm (e.g., normal, grq)")
    parser.add_argument("-o", "--output_path", default=None, help="Output path for the exported .rkllm model")
    parser.add_argument("-c", "--max_context", type=int, default=4096, help="Max context size")
    
    args = parser.parse_args()

    # Load model
    print(f"Loading model from {args.model_path} ...")
    llm = RKLLM()
    ret = llm.load_huggingface(model=args.model_path, model_lora=None, device='cpu', dtype="float16", custom_config=None, load_weight=True)
    if ret != 0:
        print('Load model failed!')
        exit(ret)

    print(f"Building model with dataset {args.dataset} ...")
    ret = llm.build(do_quantization=True, 
                    optimization_level=1, 
                    quantized_dtype=args.quantized_dtype,
                    quantized_algorithm=args.quantized_algorithm, 
                    target_platform=args.target_platform, 
                    num_npu_core=3, 
                    extra_qparams=None, 
                    dataset=args.dataset, 
                    hybrid_rate=0, 
                    max_context=args.max_context)
    if ret != 0:
        print('Build model failed!')
        exit(ret)

    # Export rkllm model
    output_path = args.output_path
    if not output_path:
        model_name = os.path.basename(args.model_path.rstrip("/"))
        output_path = f"./{model_name}_{args.quantized_dtype}_{args.target_platform}.rkllm"

    print(f"Exporting RKLLM model to {output_path} ...")
    ret = llm.export_rkllm(output_path)
    if ret != 0:
        print('Export model failed!')
        exit(ret)

    print(f"Successfully exported to {output_path}")

if __name__ == "__main__":
    main()
