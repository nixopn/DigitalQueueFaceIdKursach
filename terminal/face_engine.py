from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


class FaceEngine:
    def __init__(self, min_face_size: int = 80, match_threshold: float = 0.78):
        cascade_path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
        self.detector = cv2.CascadeClassifier(str(cascade_path))
        self.min_face_size = min_face_size
        self.match_threshold = match_threshold

    def detect(self, frame: np.ndarray) -> list[tuple[int, int, int, int]]:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)
        faces = self.detector.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(self.min_face_size, self.min_face_size),
        )
        if len(faces) == 0:
            alt_path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_alt2.xml"
            alt = cv2.CascadeClassifier(str(alt_path))
            faces = alt.detectMultiScale(
                gray,
                scaleFactor=1.08,
                minNeighbors=4,
                minSize=(max(40, self.min_face_size // 2), max(40, self.min_face_size // 2)),
            )
        return [tuple(map(int, f)) for f in faces]

    def embed(self, frame: np.ndarray, box: tuple[int, int, int, int] | None = None) -> np.ndarray | None:
        if box is None:
            faces = self.detect(frame)
            if not faces:
                return None
            box = max(faces, key=lambda f: f[2] * f[3])
        x, y, w, h = box
        pad = int(0.12 * w)
        x0, y0 = max(0, x - pad), max(0, y - pad)
        x1, y1 = min(frame.shape[1], x + w + pad), min(frame.shape[0], y + h + pad)
        face = frame[y0:y1, x0:x1]
        if face.size == 0:
            return None
        gray = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, (128, 128), interpolation=cv2.INTER_AREA)
        lbp = _lbp_image(gray)
        hist = _grid_hist(lbp, grid=8, bins=16)
        norm = np.linalg.norm(hist)
        if norm == 0:
            return None
        return (hist / norm).astype(np.float32)

    def match(
        self, embedding: np.ndarray, stored: list[tuple[int, np.ndarray]]
    ) -> tuple[int | None, float]:
        best_id = None
        best_score = -1.0
        for client_id, other in stored:
            score = float(np.dot(embedding, other))
            if score > best_score:
                best_score = score
                best_id = client_id
        if best_id is None or best_score < self.match_threshold:
            return None, best_score
        return best_id, best_score

    def annotate(self, frame: np.ndarray, box: tuple[int, int, int, int], label: str) -> np.ndarray:
        x, y, w, h = box
        out = frame.copy()
        cv2.rectangle(out, (x, y), (x + w, y + h), (37, 99, 235), 2)
        cv2.putText(out, label, (x, max(20, y - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (37, 99, 235), 2)
        return out


def decode_image(data: bytes) -> np.ndarray:
    arr = np.frombuffer(data, dtype=np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("Не удалось декодировать изображение")
    return frame


def encode_jpeg(frame: np.ndarray, quality: int = 85) -> bytes:
    ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        raise ValueError("Не удалось закодировать кадр")
    return buf.tobytes()


def embedding_to_bytes(vec: np.ndarray) -> bytes:
    return vec.astype(np.float32).tobytes()


def bytes_to_embedding(raw: bytes) -> np.ndarray:
    return np.frombuffer(raw, dtype=np.float32).copy()


def _lbp_image(gray: np.ndarray) -> np.ndarray:
    padded = cv2.copyMakeBorder(gray, 1, 1, 1, 1, cv2.BORDER_REPLICATE)
    center = padded[1:-1, 1:-1]
    codes = np.zeros_like(center, dtype=np.uint8)
    shifts = [
        (0, 0, 1),
        (0, 1, 2),
        (0, 2, 4),
        (1, 2, 8),
        (2, 2, 16),
        (2, 1, 32),
        (2, 0, 64),
        (1, 0, 128),
    ]
    for dy, dx, bit in shifts:
        neighbor = padded[dy : dy + center.shape[0], dx : dx + center.shape[1]]
        codes |= np.where(neighbor >= center, bit, 0).astype(np.uint8)
    return codes


def _grid_hist(lbp: np.ndarray, grid: int, bins: int) -> np.ndarray:
    h, w = lbp.shape
    cell_h, cell_w = h // grid, w // grid
    parts = []
    for gy in range(grid):
        for gx in range(grid):
            cell = lbp[gy * cell_h : (gy + 1) * cell_h, gx * cell_w : (gx + 1) * cell_w]
            hist, _ = np.histogram(cell, bins=bins, range=(0, 256), density=True)
            parts.append(hist.astype(np.float32))
    return np.concatenate(parts)
