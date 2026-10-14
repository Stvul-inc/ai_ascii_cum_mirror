# Project Context

## Архитектура ASCII Mirror Studio (Apple Modern UI)
- Вместо устаревшего OpenCV HighGUI реализовано полноценное веб-приложение на чистом HTML5 + CSS3 Glassmorphism + WebRTC Canvas API:
  - **Дизайн**: Темный режим macOS (`#09090b`), эффект стеклянного размытия `backdrop-filter: blur(35px)`, системная типографика SF Pro, светодиодный индикатор `● LIVE`.
  - **Адаптивный ресайз**: Динамический пересчёт сетки (колонок и строк) при изменении размеров окна с сохранением точных пропорций камеры (aspect ratio).
  - **Интерактивные элементы**:
    - Переключатели палитр (TrueColor RGB, Cyber Neon, Matrix Phosphor, Silver Mono, Amber Sunset, Negative Invert).
    - Плавные слайдеры плотности сетки (50–180) и контраста (0.5–2.0).
    - Копирование форматированного текстового ASCII в буфер обмена системы (`navigator.clipboard`).
    - Скачивание снимка PNG со вспышкой Apple Camera.
    - Полноэкранный режим (Fullscreen API).
    - Поддержка горячих клавиш (Space, C, S, M, F, 1-6).
  - **Сервер**: `server.py` раздаёт приложение на порту `8080` (`http://localhost:8080`).
