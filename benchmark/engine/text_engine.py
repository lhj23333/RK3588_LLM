import os
from .base_engine import BaseEngine

class TextEngine(BaseEngine):
    def _build_cmd(self, **kwargs):
        bin_path = os.path.join(self.workspace_root, self.config.binary_path)
        model_path = os.path.join(self.workspace_root, self.config.model_path)
        
        # ./text_llm_demo <model_path> <max_new_tokens> <max_context_len>
        return [
            bin_path,
            model_path,
            str(self.config.max_new_tokens),
            str(self.config.max_context_len)
        ]

    def run(self, prompt: str, timeout: int = 900, **kwargs):
        # Override run to adapt to text demo, or inherit and just pass prompt
        return super().run(prompt, timeout=timeout, **kwargs)
