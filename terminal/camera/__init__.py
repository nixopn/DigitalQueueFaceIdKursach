from __future__ import annotations

from terminal.camera.base import CameraBackend
from terminal.camera.opencv_camera import OpenCVCamera
from terminal.camera.v4l2_camera import V4L2Camera
from terminal.config import CameraCfg


class BrowserCamera(CameraBackend):
    """Кадр приходит с киоска (getUserMedia). Физический захват не открывается."""

    name = "browser"

    def open(self) -> None:
        return None

    def grab(self):
        return None

    def close(self) -> None:
        return None


def create_camera(cfg: CameraCfg) -> CameraBackend:
    backend = cfg.backend.lower().strip()
    if backend in {"browser", "web", "auto"}:
        if backend == "auto":
            cam = OpenCVCamera(cfg.device, cfg.width, cfg.height, cfg.fps)
            if cam.available():
                return cam
        return BrowserCamera()
    if backend in {"opencv", "webcam", "usb"}:
        return OpenCVCamera(cfg.device, cfg.width, cfg.height, cfg.fps)
    if backend in {"v4l2", "csi", "sc3336"}:
        device = cfg.device if not str(cfg.device).isdigit() else f"/dev/video{cfg.device}"
        return V4L2Camera(device, cfg.width, cfg.height, cfg.fps)
    raise ValueError(f"Неизвестный camera.backend: {cfg.backend}")
