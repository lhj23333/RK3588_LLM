import os
from .base_engine import BaseEngine

class VLMEngine(BaseEngine):
    def _build_cmd(self, **kwargs):
        bin_path = os.path.join(self.workspace_root, self.config.binary_path)
        vision_model = os.path.join(self.workspace_root, self.config.vision_model_path)
        llm_model = os.path.join(self.workspace_root, self.config.llm_model_path)
        
        # Must provide image path
        image_path = kwargs.get("image_path")
        if not image_path:
            raise ValueError("VLM requires 'image_path' to be provided.")
        
        img_abs = os.path.join(self.workspace_root, image_path)
        if not os.path.isfile(img_abs):
            raise FileNotFoundError(f"Image not found: {img_abs}")

        # ./VLM_NPU <image_path> <vision_model> <llm_model> 2048 4096
        return [
            bin_path,
            img_abs,
            vision_model,
            llm_model,
            str(self.config.max_new_tokens),
            str(self.config.max_context_len)
        ]

    def run(self, prompt: str, timeout: int = 300, image_path: str = "", **kwargs):
        # Override to ensure image_path is passed
        if not image_path:
            raise ValueError("VLMEngine.run requires an 'image_path'.")
            
        return super().run(prompt, timeout=timeout, image_path=image_path, **kwargs)
