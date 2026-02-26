cmake_minimum_required(VERSION 3.14)
project(RK3588_LLM_Demos)

set(CMAKE_CXX_STANDARD 14)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# 查找 OpenCV (多模态模型需要)
find_package(OpenCV REQUIRED)
include_directories(${OpenCV_INCLUDE_DIRS})

# 添加 rknn-llm 官方的头文件路径
include_directories(${CMAKE_CURRENT_SOURCE_DIR}/../third_party/rknn-llm/rkllm-runtime/Linux/librkllm_api/include)
include_directories(${CMAKE_CURRENT_SOURCE_DIR}/../third_party/rknn-llm/rknn-runtime/Linux/librknn_api/include)

# 添加 rknn-llm 官方的库文件路径 (针对 RK3588 aarch64)
link_directories(${CMAKE_CURRENT_SOURCE_DIR}/../third_party/rknn-llm/rkllm-runtime/Linux/librkllm_api/aarch64)
link_directories(${CMAKE_CURRENT_SOURCE_DIR}/../third_party/rknn-llm/rknn-runtime/Linux/librknn_api/aarch64)

# 假设 librkllmrt.so 已经放在 /usr/lib 或通过环境变量指定
# 这里我们添加一个基础的 Demo 目标 (后续可以根据具体模型添加)

# 1. 纯文本 LLM Demo (Qwen 等)
add_executable(text_llm_demo ../third_party/rknn-llm/examples/rkllm_api_demo/deploy/src/llm_demo.cpp)
target_link_libraries(text_llm_demo rkllmrt)

# 2. 多模态 LLM Demo (Qwen-VL, InternVL 等)
# 注意：官方的 multimodal_model_demo 中，main.cpp 和 img_encoder.cpp 都有 main 函数，它们是两个独立的 demo
# main.cpp 是完整的图文对话 demo，img_encoder.cpp 只是单独测试图像编码器的 demo
add_executable(multimodal_llm_demo 
    ../third_party/rknn-llm/examples/multimodal_model_demo/deploy/src/main.cpp
    ../third_party/rknn-llm/examples/multimodal_model_demo/deploy/src/image_enc.cc
)
target_link_libraries(multimodal_llm_demo rkllmrt rknnrt ${OpenCV_LIBS})

message(STATUS "CMake configuration for RK3588 LLM Demos completed.")
message(STATUS "Please uncomment the executable targets once source files are added.")
