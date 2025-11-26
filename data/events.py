# data/events.py
import yaml
from pathlib import Path
from .paths import CONFIG_DIR

def load_event(name: str):
    """
    name: 예) 'seoul_hangang_2020'
    """
    cfg_path = CONFIG_DIR / f"event_{name}.yaml"
    with cfg_path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)

if __name__ == "__main__":
    cfg = load_event("seoul_hangang_2020")
    print(cfg["flood"]["start"], cfg["flood"]["end"])
