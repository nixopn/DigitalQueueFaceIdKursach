from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class DisplayBackend(ABC):
    name: str = "display"

    @abstractmethod
    def show_message(self, title: str, body: str) -> None: ...

    @abstractmethod
    def close(self) -> None: ...


class WebDisplay(DisplayBackend):
    """Киоск в браузере: сенсор ноутбука, планшета или панели терминала."""

    name = "web"

    def show_message(self, title: str, body: str) -> None:
        return None

    def close(self) -> None:
        return None


class FramebufferDisplay(DisplayBackend):
    """ILI9431 через framebuffer /dev/fb0 (Luckfox)."""

    name = "framebuffer"

    def __init__(self, device: str = "/dev/fb0", width: int = 320, height: int = 240):
        self.device = device
        self.width = width
        self.height = height
        self._fd = None

    def available(self) -> bool:
        return Path(self.device).exists()

    def open(self) -> None:
        if not self.available():
            raise RuntimeError(f"Framebuffer не найден: {self.device}")
        self._fd = open(self.device, "r+b", buffering=0)

    def show_message(self, title: str, body: str) -> None:
        if self._fd is None:
            try:
                self.open()
            except OSError:
                return
        try:
            from PIL import Image, ImageDraw

            img = Image.new("RGB", (self.width, self.height), (18, 22, 28))
            draw = ImageDraw.Draw(img)
            draw.rectangle((8, 8, self.width - 9, 48), fill=(37, 99, 235))
            draw.text((16, 18), title[:28], fill=(255, 255, 255))
            y = 64
            for line in _wrap(body, 36):
                draw.text((16, y), line, fill=(226, 232, 240))
                y += 18
            raw = img.convert("RGB").tobytes()
            rgb565 = bytearray(self.width * self.height * 2)
            for i in range(0, len(raw), 3):
                r, g, b = raw[i], raw[i + 1], raw[i + 2]
                value = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
                idx = (i // 3) * 2
                rgb565[idx] = value & 0xFF
                rgb565[idx + 1] = (value >> 8) & 0xFF
            self._fd.seek(0)
            self._fd.write(rgb565)
        except Exception:
            return

    def close(self) -> None:
        if self._fd is not None:
            self._fd.close()
            self._fd = None


class CompositeDisplay(DisplayBackend):
    name = "both"

    def __init__(self, parts: list[DisplayBackend]):
        self.parts = parts

    def show_message(self, title: str, body: str) -> None:
        for part in self.parts:
            part.show_message(title, body)

    def close(self) -> None:
        for part in self.parts:
            part.close()


def create_display(backend: str, fb_device: str, width: int, height: int) -> DisplayBackend:
    backend = backend.lower().strip()
    web = WebDisplay()
    fb = FramebufferDisplay(fb_device, width, height)
    if backend == "web":
        return web
    if backend == "framebuffer":
        return fb
    parts: list[DisplayBackend] = [web]
    if fb.available():
        parts.append(fb)
    return CompositeDisplay(parts)


def _wrap(text: str, width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if len(trial) > width:
            if current:
                lines.append(current)
            current = word
        else:
            current = trial
    if current:
        lines.append(current)
    return lines or [""]
