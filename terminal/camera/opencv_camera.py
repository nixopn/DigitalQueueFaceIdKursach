from __future__ import annotations

import cv2
import numpy as np

from terminal.camera.base import CameraBackend


class OpenCVCamera(CameraBackend):
    """Встроенная веб-камера, USB-камера или любой V4L2-узел через OpenCV."""

    name = "opencv"

    def __init__(self, device: str | int = 0, width: int = 640, height: int = 480, fps: int = 15):
        self.device = int(device) if str(device).isdigit() else device
        self.width = width
        self.height = height
        self.fps = fps
        self._cap: cv2.VideoCapture | None = None

    def open(self) -> None:
        if isinstance(self.device, int):
            cap = cv2.VideoCapture(self.device)
        else:
            cap = cv2.VideoCapture(self.device, cv2.CAP_V4L2) if _is_linux_path(self.device) else cv2.VideoCapture(self.device)
        if not cap.isOpened():
            raise RuntimeError(f"Не удалось открыть камеру: {self.device}")
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        cap.set(cv2.CAP_PROP_FPS, self.fps)
        self._cap = cap

    def grab(self) -> np.ndarray | None:
        if self._cap is None:
            return None
        ok, frame = self._cap.read()
        return frame if ok else None

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def available(self) -> bool:
        try:
            self.open()
            frame = self.grab()
            self.close()
            return frame is not None
        except Exception:
            self.close()
            return False


def _is_linux_path(device: str) -> bool:
    return str(device).startswith("/dev/")
