# План реализации: Полноценный Modern Apple UI (HTML5 + WebGL/Canvas + Camera API)

## 1. Проблема текущего решения в OpenCV
- OpenCV HighGUI (`cv2.imshow`) не является современным GUI:
  - Шрифты растровые (Hershey) без антиалиасинга.
  - На Retina дисплеях координаты мыши сдвигаются из-за scale factor 2x, кнопки не нажимаются.
  - Ресайз в `WINDOW_AUTOSIZE` заблокирован, а в `WINDOW_NORMAL` растягивает пиксели и ломает пропорции.
  - Нет настоящей эстетики Apple (blur glassmorphism, SF Pro, адаптивный layout).

## 2. Архитектура Modern Apple Web App (`index.html`, `style.css`, `app.js`)
1. **Эстетика Apple Glassmorphism**:
   - macOS Dark Mode: фон `#0a0a0c`, полупрозрачный стеклянный сайдбар и док (`backdrop-filter: blur(25px)`, `rgba(255, 255, 255, 0.08)` границы).
   - Типографика: `-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display"`.
   - Акцентные цвета: Apple Blue `#0A84FF`, Green `#30D158`, Purple `#BF5AF2`, Orange `#FF9F0A`.
2. **Адаптивность и ресайз**:
   - `ResizeObserver` и `window.onresize`: пересчет колонок и строк в реальном времени с сохранением квадратной сетки и идеального соотношения сторон видеопотока.
   - Поддержка полноэкранного режима (Fullscreen API).
3. **Функционал**:
   - Прямой захват камеры FaceTime через `navigator.mediaDevices.getUserMedia`.
   - Режимы:
     - 🌈 *TrueColor RGB* (цвет каждого символа = цвет пикселя)
     - 🔮 *Cyber Neon* (градиент)
     - 💚 *Matrix Phosphor*
     - ⚪ *Silver Monochrome*
     - 🌅 *Amber Retro*
     - 🔲 *Negative Invert*
   - Инструменты:
     - Слайдер плотности сетки (разрешения) с шагом от 40 до 200 символов.
     - Слайдер контрастности / гаммы.
     - Выбор символьного набора (Классический ASCII, Блочные символы, Минимал точки).
     - Кнопка «Скопировать ASCII» в буфер обмена (`navigator.clipboard`).
     - Кнопка «Снимок в PNG» с анимацией вспышки камеры Apple.
     - Пауза и горизонтальное зеркалирование.
4. **Запуск**:
   - Локальный HTTP-сервер Python + мгновенное открытие в Safari/Chrome (`open http://localhost:8000`).
   - Работает и на хосте Mac, и в Docker!
