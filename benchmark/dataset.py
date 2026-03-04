import json
import os

class BenchmarkDataset:
    def __init__(self, workspace_root: str):
        self.workspace_root = workspace_root
        self.text_prompts = []
        self.vlm_tasks = []
        
        self._load_datasets()
        
    def _load_datasets(self):
        text_path = os.path.join(self.workspace_root, "data", "benchmark", "text_prompts.json")
        vlm_path = os.path.join(self.workspace_root, "data", "benchmark", "vlm_tasks.json")
        
        if os.path.exists(text_path):
            with open(text_path, "r", encoding="utf-8") as f:
                self.text_prompts = json.load(f)
                
        if os.path.exists(vlm_path):
            with open(vlm_path, "r", encoding="utf-8") as f:
                self.vlm_tasks = json.load(f)

    def get_text_prompts(self):
        return self.text_prompts
        
    def get_vlm_tasks(self):
        return self.vlm_tasks
