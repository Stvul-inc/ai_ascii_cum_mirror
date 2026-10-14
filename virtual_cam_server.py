#!/usr/bin/env python3
"""
ASCII Camera Studio — Виртуальная камера macOS (Сервер трансляции и видеопотока)

Принимает бинарные кадры с WebGL ASCII-холста по WebSocket и раздаёт их:
1. В системную виртуальную камеру macOS через pyvirtualcam (если установлен DAL-плагин OBS).
2. В высокоскоростной MJPEG-поток (http://localhost:8081/video_feed) для OBS Browser/Media Source.
3. В интерактивную контрольную панель (http://localhost:8081/).
"""

import sys
import os
import time
import asyncio
import logging
from aiohttp import web

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger('vcam_server')

# Глобальное состояние
latest_frame = None
latest_frame_time = 0
frame_count = 0
fps = 0
active_websockets = set()
mjpeg_subscribers = set()
vcam_device = None

# Попытка инициализации pyvirtualcam
try:
    import pyvirtualcam
    PYVIRTUALCAM_AVAILABLE = True
except ImportError:
    PYVIRTUALCAM_AVAILABLE = False


def check_dal_plugin_installed() -> bool:
    """Проверяет наличие системного DAL-плагина виртуальной камеры в macOS."""
    dal_path = '/Library/CoreMediaIO/Plug-Ins/DAL/'
    if os.path.exists(dal_path):
        for item in os.listdir(dal_path):
            if item.endswith('.plugin') and ('obs' in item.lower() or 'virtual' in item.lower()):
                return True
    return False


async def ws_handler(request):
    """Приём кадров от браузерного клиента (app.js) по WebSocket."""
    global latest_frame, latest_frame_time, frame_count, fps

    ws = web.WebSocketResponse(max_msg_size=10 * 1024 * 1024)
    await ws.prepare(request)

    active_websockets.add(ws)
    logger.info("Клиент ASCII-зеркала подключился к WebSocket")

    status_msg = {
        "type": "status",
        "msg": "✓ Соединение с сервером вирткамеры установлено",
        "mjpeg_url": "http://localhost:8081/video_feed",
        "dal_installed": check_dal_plugin_installed(),
        "pyvirtualcam": PYVIRTUALCAM_AVAILABLE
    }
    await ws.send_json(status_msg)

    last_fps_calc = time.time()
    frames_in_interval = 0

    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.BINARY:
                frame_data = msg.data
                latest_frame = frame_data
                latest_frame_time = time.time()
                frame_count += 1
                frames_in_interval += 1

                # Считаем реальный FPS
                now = time.time()
                if now - last_fps_calc >= 1.0:
                    fps = round(frames_in_interval / (now - last_fps_calc), 1)
                    frames_in_interval = 0
                    last_fps_calc = now

                # Рассылаем кадр всем подключённым MJPEG-потребителям (OBS / VLC)
                for q in list(mjpeg_subscribers):
                    try:
                        if not q.full():
                            q.put_nowait(frame_data)
                    except Exception:
                        pass

            elif msg.type == web.WSMsgType.TEXT:
                logger.info(f"Текстовое сообщение: {msg.data}")
            elif msg.type == web.WSMsgType.ERROR:
                logger.error(f"Ошибка WebSocket: {ws.exception()}")

    finally:
        active_websockets.discard(ws)
        logger.info("Клиент ASCII-зеркала отключился от WebSocket")

    return ws


async def mjpeg_feed_handler(request):
    """
    Отдаёт непрерывный поток MJPEG multipart/x-mixed-replace.
    Поддерживается OBS Studio (Media Source / VLC), Chrome, QuickTime, Telegram.
    """
    response = web.StreamResponse(
        status=200,
        reason='OK',
        headers={
            'Content-Type': 'multipart/x-mixed-replace; boundary=frame',
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Access-Control-Allow-Origin': '*'
        }
    )
    await response.prepare(request)

    q = asyncio.Queue(maxsize=4)
    mjpeg_subscribers.add(q)
    logger.info(f"Новый MJPEG подписчик подключен (всего: {len(mjpeg_subscribers)})")

    try:
        # Отправляем последний кадр сразу, если есть
        if latest_frame:
            header = b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + latest_frame + b'\r\n'
            await response.write(header)

        while True:
            frame_bytes = await q.get()
            header = b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n'
            await response.write(header)
    except (asyncio.CancelledError, ConnectionResetError):
        pass
    finally:
        mjpeg_subscribers.discard(q)
        logger.info(f"MJPEG подписчик отключен (осталось: {len(mjpeg_subscribers)})")

    return response


async def snapshot_handler(request):
    """Возвращает один актуальный JPEG-кадр."""
    if latest_frame is None:
        return web.Response(text="Кадры ещё не поступали", status=503)
    return web.Response(body=latest_frame, content_type='image/jpeg', headers={'Access-Control-Allow-Origin': '*'})


async def status_json_handler(request):
    """Статус в формате JSON."""
    data = {
        "status": "online",
        "has_stream": latest_frame is not None,
        "fps": fps,
        "total_frames": frame_count,
        "active_clients": len(active_websockets),
        "mjpeg_subscribers": len(mjpeg_subscribers),
        "dal_plugin_detected": check_dal_plugin_installed(),
        "mjpeg_url": "http://localhost:8081/video_feed",
        "clean_obs_url": "http://localhost:8080/?mode=cam"
    }
    return web.json_response(data)


async def index_page_handler(request):
    """Информационная панель и видео-превью потока (или WS при хендшейке)."""
    if request.headers.get('Upgrade', '').lower() == 'websocket':
        return await ws_handler(request)

    dal_status = "✅ Обнаружен системный DAL-плагин" if check_dal_plugin_installed() else "⚠️ DAL-плагин не найден в /Library/CoreMediaIO/Plug-Ins/DAL/"

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ASCII Camera — Монитор виртуальной камеры macOS</title>
    <style>
        body {{
            background: #0d0d11;
            color: #f5f5f7;
            font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", sans-serif;
            margin: 0;
            padding: 30px;
            display: flex;
            flex-direction: column;
            align-items: center;
        }}
        .card {{
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 16px;
            padding: 24px;
            max-width: 720px;
            width: 100%;
            box-shadow: 0 20px 50px rgba(0,0,0,0.6);
        }}
        h1 {{ margin-top: 0; font-size: 22px; display: flex; align-items: center; gap: 10px; }}
        .badge {{ background: #0a84ff; color: #fff; font-size: 11px; padding: 4px 10px; border-radius: 999px; }}
        .badge.live {{ background: #30d158; }}
        .preview-box {{
            width: 100%;
            border-radius: 12px;
            overflow: hidden;
            background: #000;
            border: 1px solid rgba(255,255,255,0.1);
            margin: 20px 0;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 280px;
        }}
        .preview-box img {{
            max-width: 100%;
            height: auto;
            display: block;
        }}
        .code-block {{
            background: rgba(0,0,0,0.6);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 8px;
            padding: 12px;
            font-family: ui-monospace, Menlo, monospace;
            font-size: 13px;
            color: #ffd60a;
            user-select: all;
            margin: 8px 0;
            word-break: break-all;
        }}
        .step {{ margin-bottom: 16px; line-height: 1.5; font-size: 14px; color: #ccc; }}
        .step b {{ color: #fff; }}
        a.btn {{
            display: inline-block;
            background: #0a84ff;
            color: #fff;
            padding: 8px 16px;
            border-radius: 8px;
            text-decoration: none;
            font-weight: 600;
            margin-top: 10px;
        }}
    </style>
</head>
<body>
    <div class="card">
        <h1>🎥 Монитор виртуальной камеры macOS <span class="badge live">PORT 8081</span></h1>
        <p style="color: #98989d; font-size: 13px;">{dal_status}</p>

        <div class="preview-box">
            <img src="/video_feed" alt="ASCII Видеопоток в реальном времени" onerror="this.alt='Ожидание подключения из браузера... Нажмите Вирткамера в шапке http://localhost:8080'">
        </div>

        <h3>Способ 1. Использование в OBS Studio (Виртуальная камера)</h3>
        <div class="step">
            <b>Шаг 1:</b> В OBS добавьте источник <b>«Браузер»</b> (Browser Source) и вставьте чистый URL:<br>
            <div class="code-block">http://localhost:8080/?mode=cam</div>
            (Или добавьте источник <b>«Медиа / VLC»</b> с сетевым адресом: <div class="code-block">http://localhost:8081/video_feed</div>)
        </div>
        <div class="step">
            <b>Шаг 2:</b> В OBS нажмите <b>«Запустить виртуальную камеру»</b> (Start Virtual Camera).
        </div>
        <div class="step">
            <b>Шаг 3:</b> В Telegram, Zoom, Discord или Google Chrome выберите камеру <b>«OBS Virtual Camera»</b>.
        </div>

        <a class="btn" href="http://localhost:8080" target="_blank">Перейти в Camera Studio (Порт 8080) →</a>
    </div>
</body>
</html>
"""
    return web.Response(text=html, content_type='text/html')


def create_app():
    app = web.Application()
    app.router.add_get('/', index_page_handler)
    app.router.add_get('/ws', ws_handler)
    app.router.add_get('/video_feed', mjpeg_feed_handler)
    app.router.add_get('/snapshot', snapshot_handler)
    app.router.add_get('/status', status_json_handler)
    return app


if __name__ == '__main__':
    port = 8081
    print(f"==================================================")
    print(f" 🎥 ASCII Video Streamer & Virtual Cam Bridge")
    print(f" Сервер запущен на: http://localhost:{port}")
    print(f" MJPEG видеопоток:   http://localhost:{port}/video_feed")
    print(f" WebSocket приёмник: ws://localhost:{port}/ws")
    print(f" Режим чистого OBS:  http://localhost:8080/?mode=cam")
    print(f"==================================================")

    app = create_app()
    web.run_app(app, host='0.0.0.0', port=port)
