from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"


class AppCfg(BaseModel):
    host: str = "0.0.0.0"
    python_port: int = 8081
    name: str = "Электронная очередь"


class CameraCfg(BaseModel):
    backend: str = "browser"
    device: str = "0"
    width: int = 640
    height: int = 480
    fps: int = 15


class DisplayCfg(BaseModel):
    backend: str = "web"
    fb_device: str = "/dev/fb0"
    fb_width: int = 320
    fb_height: int = 240
    touch_device: str = "/dev/input/event0"


class RecognitionCfg(BaseModel):
    match_threshold: float = 0.78
    min_face_size: int = 80


class CatalogItem(BaseModel):
    id: str
    name: str
    price: float


class Settings(BaseModel):
    app: AppCfg = Field(default_factory=AppCfg)
    camera: CameraCfg = Field(default_factory=CameraCfg)
    display: DisplayCfg = Field(default_factory=DisplayCfg)
    recognition: RecognitionCfg = Field(default_factory=RecognitionCfg)
    catalog: list[CatalogItem] = Field(default_factory=list)


def load_settings(path: str | None = None) -> Settings:
    cfg_path = Path(path) if path else Path(__import__("os").environ.get("QUEUE_CONFIG", ROOT / "config.yaml"))
    if not cfg_path.is_absolute():
        cfg_path = ROOT / cfg_path
    raw: dict[str, Any] = {}
    if cfg_path.exists():
        with cfg_path.open(encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
    return Settings.model_validate(raw)
