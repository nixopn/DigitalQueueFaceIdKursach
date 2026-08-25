from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np


class CameraBackend(ABC):
    name: str = "camera"

    @abstractmethod
    def open(self) -> None: ...

    @abstractmethod
    def grab(self) -> np.ndarray | None: ...

    @abstractmethod
    def close(self) -> None: ...

    def available(self) -> bool:
        return True
