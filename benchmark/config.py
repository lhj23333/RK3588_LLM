import os
import yaml

class ModelConfig:
    def __init__(self, name: str, data: dict):
        self.name = name
        self.type = data.get("type", "text")
        self.binary_path = data.get("binary_path", "")
        self.max_new_tokens = data.get("max_new_tokens", 512)
        self.max_context_len = data.get("max_context_len", 4096)
        
        # Text specific
        self.model_path = data.get("model_path", "")
        
        # VLM specific
        self.vision_model_path = data.get("vision_model_path", "")
        self.llm_model_path = data.get("llm_model_path", "")

    def validate(self, workspace_root: str):
        # Validate binary
        bin_path = os.path.join(workspace_root, self.binary_path)
        if not os.path.isfile(bin_path):
            raise FileNotFoundError(f"Binary not found: {bin_path}")
        
        if self.type == "text":
            m_path = os.path.join(workspace_root, self.model_path)
            if not os.path.isfile(m_path):
                print(f"[Warning] Model file not found (might need download): {m_path}")
        elif self.type == "vlm":
            v_path = os.path.join(workspace_root, self.vision_model_path)
            l_path = os.path.join(workspace_root, self.llm_model_path)
            if not os.path.isfile(v_path):
                print(f"[Warning] Vision model not found (might need download): {v_path}")
            if not os.path.isfile(l_path):
                print(f"[Warning] LLM model not found (might need download): {l_path}")

def load_config(config_path: str) -> dict:
    if not os.path.isfile(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")
        
    with open(config_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
        
    models_data = data.get("models", {})
    models = {}
    for name, config_data in models_data.items():
        models[name] = ModelConfig(name, config_data)
        
    return models
