from __future__ import annotations

import asyncio
import json
from typing import Any

import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from terminal.camera import create_camera
from terminal.config import Settings, load_settings
from terminal.db import connect
from terminal.display import create_display
from terminal.face_engine import FaceEngine, decode_image, encode_jpeg
from terminal.queue_service import QueueService


class CartIn(BaseModel):
    items: list[dict[str, Any]] = Field(default_factory=list)


class CameraSwitchIn(BaseModel):
    backend: str
    device: str = "0"


class ServeIn(BaseModel):
    queue_id: int


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    conn = connect()
    queue = QueueService(conn)
    engine = FaceEngine(
        min_face_size=settings.recognition.min_face_size,
        match_threshold=settings.recognition.match_threshold,
    )
    camera = create_camera(settings.camera)
    display = create_display(
        settings.display.backend,
        settings.display.fb_device,
        settings.display.fb_width,
        settings.display.fb_height,
    )
    try:
        camera.open()
    except Exception:
        camera = create_camera(settings.camera.model_copy(update={"backend": "browser"}))

    subscribers: set[asyncio.Queue] = set()
    lock = asyncio.Lock()

    app = FastAPI(title="Terminal API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    async def publish() -> dict:
        snap = queue.snapshot()
        snap["hardware"] = hardware_status()
        dead = []
        for sub in list(subscribers):
            try:
                sub.put_nowait(snap)
            except asyncio.QueueFull:
                dead.append(sub)
        for item in dead:
            subscribers.discard(item)
        return snap

    def hardware_status() -> dict:
        from pathlib import Path

        fb = Path(settings.display.fb_device)
        touch = Path(settings.display.touch_device)
        return {
            "camera_backend": camera.name,
            "camera_device": settings.camera.device,
            "display_backend": display.name,
            "framebuffer": fb.exists(),
            "framebuffer_path": settings.display.fb_device,
            "touch": touch.exists(),
            "touch_path": settings.display.touch_device,
        }

    def recognize_frame(frame: np.ndarray) -> dict:
        faces = engine.detect(frame)
        if not faces:
            display.show_message("Лицо не найдено", "Встаньте ближе к камере")
            queue.log("no_face", {})
            preview = encode_jpeg(frame)
            return {
                "ok": False,
                "reason": "no_face",
                "message": "Лицо не найдено. Встаньте ближе к камере.",
                "preview_jpeg": preview,
            }
        box = max(faces, key=lambda f: f[2] * f[3])
        embedding = engine.embed(frame, box)
        if embedding is None:
            raise RuntimeError("Не удалось построить вектор лица")
        client_id, score = engine.match(embedding, queue.stored_embeddings())
        registered = False
        if client_id is None:
            client_id = queue.register_client(embedding)
            registered = True
        else:
            queue.touch_client(client_id)
        ticket = queue.enqueue(client_id)
        items = queue.attach_pending_order(client_id, ticket["id"])
        ahead = queue.position(ticket["queue_number"])
        order_text = ", ".join(i.get("name", "") for i in items) or "без предзаказа"
        message = (
            f"Номер {ticket['queue_number']}. Заказ: {order_text}. Перед вами {ahead} чел."
        )
        display.show_message(f"Номер {ticket['queue_number']}", message)
        queue.log(
            "recognized" if not registered else "registered",
            {
                "client_id": client_id,
                "queue_number": ticket["queue_number"],
                "score": round(float(score), 3),
                "registered": registered,
            },
        )
        labeled = engine.annotate(frame, box, f"#{ticket['queue_number']}")
        return {
            "ok": True,
            "registered": registered,
            "client_id": client_id,
            "queue_number": ticket["queue_number"],
            "ahead": ahead,
            "score": round(float(max(score, 0.0)), 3),
            "items": items,
            "message": message,
            "preview_jpeg": encode_jpeg(labeled),
        }

    @app.get("/api/health")
    def health():
        return {"ok": True, "hardware": hardware_status()}

    @app.get("/api/state")
    def state():
        snap = queue.snapshot()
        snap["hardware"] = hardware_status()
        snap["catalog"] = [item.model_dump() for item in settings.catalog]
        return snap

    @app.get("/api/catalog")
    def catalog():
        return [item.model_dump() for item in settings.catalog]

    @app.post("/api/cart")
    async def cart(body: CartIn):
        queue.set_pending_cart(body.items)
        queue.log("preorder", {"items": body.items})
        display.show_message("Предзаказ", "Нажмите «Распознавание»")
        return await publish()

    @app.post("/api/recognize")
    async def recognize_upload(file: UploadFile = File(...)):
        async with lock:
            data = await file.read()
            frame = decode_image(data)
            result = recognize_frame(frame)
        await publish()
        preview = result.pop("preview_jpeg")
        result["preview_base64"] = _b64(preview)
        return result

    @app.post("/api/recognize/device")
    async def recognize_device():
        async with lock:
            frame = camera.grab()
            if frame is None:
                raise HTTPException(
                    409,
                    "Камера устройства не открыта. Выберите backend opencv/v4l2 или пришлите кадр из браузера.",
                )
            result = recognize_frame(frame)
        await publish()
        preview = result.pop("preview_jpeg")
        result["preview_base64"] = _b64(preview)
        return result

    @app.get("/api/camera/preview")
    def camera_preview():
        frame = camera.grab()
        if frame is None:
            raise HTTPException(409, "Нет кадра с OpenCV/V4L2. Для ноутбука используйте камеру браузера.")
        from fastapi.responses import Response

        return Response(encode_jpeg(frame), media_type="image/jpeg")

    @app.post("/api/camera")
    async def switch_camera(body: CameraSwitchIn):
        nonlocal camera
        settings.camera.backend = body.backend
        settings.camera.device = body.device
        camera.close()
        camera = create_camera(settings.camera)
        try:
            camera.open()
        except Exception as exc:
            camera = create_camera(settings.camera.model_copy(update={"backend": "browser"}))
            raise HTTPException(400, f"Камера не открылась: {exc}") from exc
        return await publish()

    @app.post("/api/queue/serve")
    async def serve(body: ServeIn):
        queue.serve(body.queue_id)
        queue.log("served", {"queue_id": body.queue_id})
        return await publish()

    @app.post("/api/queue/remove")
    async def remove(body: ServeIn):
        queue.remove(body.queue_id)
        queue.log("removed", {"queue_id": body.queue_id})
        return await publish()

    @app.post("/api/queue/reset")
    async def reset():
        queue.reset()
        queue.log("reset", {})
        display.show_message("Очередь", "Сброшена администратором")
        return await publish()

    @app.get("/api/events")
    async def events():
        from fastapi.responses import StreamingResponse

        q: asyncio.Queue = asyncio.Queue(maxsize=8)
        subscribers.add(q)
        await q.put(queue.snapshot() | {"hardware": hardware_status()})

        async def gen():
            try:
                while True:
                    data = await q.get()
                    yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
            finally:
                subscribers.discard(q)

        return StreamingResponse(gen(), media_type="text/event-stream")

    @app.on_event("shutdown")
    def shutdown():
        camera.close()
        display.close()
        conn.close()

    return app


def _b64(raw: bytes) -> str:
    import base64

    return base64.b64encode(raw).decode("ascii")


app = create_app()
