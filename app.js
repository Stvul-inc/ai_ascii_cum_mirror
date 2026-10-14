/**
 * ASCII Mirror Pro — Apple Minimalist Web App
 * Высокопроизводительный WebRTC ASCII-движок с адаптивным соотношением сторон
 */

(function () {
    'use strict';

    // Элементы DOM
    const video = document.getElementById('webcam-video');
    const offscreenCanvas = document.getElementById('offscreen-canvas');
    const offscreenCtx = offscreenCanvas.getContext('2d', { willReadFrequently: true });
    const asciiCanvas = document.getElementById('ascii-canvas');
    const asciiCtx = asciiCanvas.getContext('2d');
    const viewportContainer = document.getElementById('viewport-container');
    const canvasWrapper = document.getElementById('canvas-wrapper');

    const fpsCounter = document.getElementById('fps-counter');
    const resolutionBadge = document.getElementById('resolution-badge');
    const pillModeIcon = document.getElementById('pill-mode-icon');
    const pillModeName = document.getElementById('pill-mode-name');

    const densitySlider = document.getElementById('density-slider');
    const densityVal = document.getElementById('density-val');
    const contrastSlider = document.getElementById('contrast-slider');
    const contrastVal = document.getElementById('contrast-val');

    const btnSnapshot = document.getElementById('btn-snapshot');
    const btnCopy = document.getElementById('btn-copy');
    const btnPause = document.getElementById('btn-pause');
    const btnMirror = document.getElementById('btn-mirror');
    const btnFullscreen = document.getElementById('btn-fullscreen');
    const pauseOverlay = document.getElementById('pause-overlay');
    const flashOverlay = document.getElementById('flash-overlay');
    const toast = document.getElementById('toast');
    const toastMsg = document.getElementById('toast-message');

    // Набор символов градации яркости (Apple typography)
    const ASCII_CHARS = " .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZ*#MW&8%B@$";
    const CHAR_COUNT = ASCII_CHARS.length;

    // Режимы и состояние
    let currentMode = 'pixel';
    let targetCols = 120;
    let contrastFactor = 1.0;
    let isMirrored = true;
    let isPaused = false;
    let isCameraReady = false;

    // Геометрия сетки
    let cols = 120;
    let rows = 66;
    let cellW = 8;
    let cellH = 14;
    let lastAsciiText = '';

    // FPS метрика
    let lastTime = performance.now();
    let frameCount = 0;
    let currentFps = 60;

    // Режимы интерфейса
    const MODE_META = {
        pixel: { name: 'TrueColor RGB', icon: '🌈' },
        neon: { name: 'Cyber Neon', icon: '🔮' },
        matrix: { name: 'Matrix Terminal', icon: '💚' },
        silver: { name: 'Silver Mono', icon: '⚪' },
        amber: { name: 'Amber Sunset', icon: '🌅' },
        invert: { name: 'Negative Invert', icon: '🔲' }
    };

    /**
     * 1. Инициализация камеры WebRTC с авто-фоллбэком на тест-генератор
     */
    async function initCamera() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                video: {
                    facingMode: 'user',
                    width: { ideal: 1280 },
                    height: { ideal: 720 }
                },
                audio: false
            });
            video.srcObject = stream;
            await video.play();
            isCameraReady = true;
            showToast('✓ Камера FaceTime подключена');
        } catch (err) {
            console.warn('Не удалось получить доступ к физической камере, используем динамический генератор:', err);
            isCameraReady = 'synthetic';
            showToast('Камера недоступна: включен тестовый видеопоток');
        }
        recalculateLayout();
        requestAnimationFrame(renderLoop);
    }

    /**
     * 2. Адаптивный ресайз сетки с сохранением пропорций видео
     */
    function recalculateLayout() {
        const containerRect = viewportContainer.getBoundingClientRect();
        const availableW = Math.max(300, containerRect.width - 32);
        const availableH = Math.max(200, containerRect.height - 32);

        // Соотношение сторон видео (по умолчанию 16:9 или соотношение реального потока)
        const videoRatio = (video.videoWidth && video.videoHeight)
            ? (video.videoWidth / video.videoHeight)
            : (16 / 9);

        // Отношение сторон моноширинного символа шрифта (~0.57)
        const charAspect = cellW / cellH;

        // Число колонок берем из слайдера
        cols = targetCols;
        // Число строк вычисляем так, чтобы итоговое изображение имело точные пропорции видео!
        rows = Math.round(cols / (videoRatio / charAspect));

        // Вычисляем размер отображаемого холста
        let renderW = cols * cellW;
        let renderH = rows * cellH;

        // Масштабируем, если не влезает в контейнер
        const scale = Math.min(availableW / renderW, availableH / renderH, 1.0);
        renderW = Math.round(renderW * scale);
        renderH = Math.round(renderH * scale);

        cellW = Math.max(4, Math.floor(renderW / cols));
        cellH = Math.max(7, Math.floor(renderH / rows));

        const finalCanvasW = cols * cellW;
        const finalCanvasH = rows * cellH;

        asciiCanvas.width = finalCanvasW;
        asciiCanvas.height = finalCanvasH;

        offscreenCanvas.width = cols;
        offscreenCanvas.height = rows;

        resolutionBadge.textContent = `${cols} × ${rows}`;
    }

    // Слушатель ресайза окна
    window.addEventListener('resize', recalculateLayout);

    /**
     * 3. Генерация синтетического кадра (если нет камеры)
     */
    let synthTime = 0;
    function drawSyntheticFrame() {
        synthTime += 0.04;
        offscreenCtx.fillStyle = '#0a0a0c';
        offscreenCtx.fillRect(0, 0, cols, rows);

        // Цветные градиентные волны
        for (let x = 0; x < cols; x += 4) {
            for (let y = 0; y < rows; y += 4) {
                const r = Math.sin(x * 0.08 + synthTime) * 127 + 128;
                const g = Math.cos(y * 0.08 + synthTime) * 127 + 128;
                const b = Math.sin((x + y) * 0.05 + synthTime) * 127 + 128;
                offscreenCtx.fillStyle = `rgb(${r},${g},${b})`;
                offscreenCtx.beginPath();
                offscreenCtx.arc(x + 2, y + 2, 3, 0, Math.PI * 2);
                offscreenCtx.fill();
            }
        }
    }

    /**
     * 4. Главный цикл рендеринга (60 FPS)
     */
    function renderLoop(now) {
        requestAnimationFrame(renderLoop);

        // Расчет FPS
        frameCount++;
        if (now - lastTime >= 500) {
            currentFps = Math.round((frameCount * 1000) / (now - lastTime));
            fpsCounter.textContent = `${currentFps} FPS`;
            frameCount = 0;
            lastTime = now;
        }

        if (isPaused) return;

        // Захват кадра в offscreen canvas
        if (isCameraReady === true && video.readyState >= 2) {
            offscreenCtx.save();
            if (isMirrored) {
                offscreenCtx.translate(cols, 0);
                offscreenCtx.scale(-1, 1);
            }
            offscreenCtx.drawImage(video, 0, 0, cols, rows);
            offscreenCtx.restore();
        } else {
            drawSyntheticFrame();
        }

        // Получение сырых данных пикселей
        const imgData = offscreenCtx.getImageData(0, 0, cols, rows);
        const data = imgData.data;

        // Очистка основного холста
        asciiCtx.fillStyle = (currentMode === 'invert') ? '#f5f5f7' : '#09090b';
        asciiCtx.fillRect(0, 0, asciiCanvas.width, asciiCanvas.height);

        // Настройка шрифта
        asciiCtx.font = `bold ${cellH}px "SF Mono", "Menlo", monospace`;
        asciiCtx.textBaseline = 'top';

        const lines = [];
        const timeSec = now * 0.002;

        for (let y = 0; y < rows; y++) {
            let rowChars = '';
            const py = y * cellH;

            for (let x = 0; x < cols; x++) {
                const idx = (y * cols + x) * 4;
                let r = data[idx];
                let g = data[idx + 1];
                let b = data[idx + 2];

                // Яркость по стандарту ITU-R BT.601
                let luma = 0.299 * r + 0.587 * g + 0.114 * b;

                // Применение контраста
                if (contrastFactor !== 1.0) {
                    luma = Math.min(255, Math.max(0, ((luma / 255 - 0.5) * contrastFactor + 0.5) * 255));
                }

                // Гамма-коррекция яркости для лучшей читаемости символов
                const norm = Math.pow(luma / 255, 0.65);
                const charIdx = Math.min(CHAR_COUNT - 1, Math.floor(norm * (CHAR_COUNT - 1)));
                const ch = ASCII_CHARS[charIdx];
                rowChars += ch;

                const px = x * cellW;

                // Выбор цвета в зависимости от режима
                if (currentMode === 'pixel') {
                    asciiCtx.fillStyle = `rgb(${r},${g},${b})`;
                } else if (currentMode === 'matrix') {
                    asciiCtx.fillStyle = `rgb(48, ${Math.floor(luma * 0.9 + 50)}, 88)`;
                } else if (currentMode === 'silver') {
                    asciiCtx.fillStyle = `rgb(${luma},${luma},${luma})`;
                } else if (currentMode === 'amber') {
                    asciiCtx.fillStyle = `rgb(255, ${Math.floor(luma * 0.6)}, 10)`;
                } else if (currentMode === 'neon') {
                    const nr = Math.floor(Math.sin(timeSec + x * 0.05) * 127 + 128);
                    const nb = Math.floor(Math.cos(timeSec + y * 0.05) * 127 + 128);
                    asciiCtx.fillStyle = `rgb(${nr}, 64, ${nb})`;
                } else if (currentMode === 'invert') {
                    asciiCtx.fillStyle = `rgb(${255 - r}, ${255 - g}, ${255 - b})`;
                }

                asciiCtx.fillText(ch, px, py);
            }
            lines.push(rowChars);
        }

        lastAsciiText = lines.join('\n');
    }

    /**
     * 5. Интерактивные действия и элементы управления
     */
    // Переключение режимов через кнопки Dock
    document.querySelectorAll('.seg-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.seg-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            setMode(btn.dataset.mode);
        });
    });

    function setMode(modeKey) {
        if (!MODE_META[modeKey]) return;
        currentMode = modeKey;
        pillModeIcon.textContent = MODE_META[modeKey].icon;
        pillModeName.textContent = MODE_META[modeKey].name;
        showToast(`Режим: ${MODE_META[modeKey].name}`);
    }

    // Слайдер плотности
    densitySlider.addEventListener('input', (e) => {
        targetCols = parseInt(e.target.value, 10);
        densityVal.textContent = targetCols;
        recalculateLayout();
    });

    // Слайдер контраста
    contrastSlider.addEventListener('input', (e) => {
        contrastFactor = parseFloat(e.target.value);
        contrastVal.textContent = contrastFactor.toFixed(1);
    });

    // Кнопка Паузы
    btnPause.addEventListener('click', togglePause);
    function togglePause() {
        isPaused = !isPaused;
        pauseOverlay.classList.toggle('hidden', !isPaused);
        document.getElementById('pause-btn-text').textContent = isPaused ? 'Пуск' : 'Пауза';
        showToast(isPaused ? '❚❚ Пауза' : '▶ Возобновлено');
    }

    // Кнопка Зеркала
    btnMirror.addEventListener('click', () => {
        isMirrored = !isMirrored;
        showToast(isMirrored ? 'Зеркало: ВКЛ' : 'Зеркало: ВЫКЛ');
    });

    // Кнопка Снимка (с вспышкой Apple Camera)
    btnSnapshot.addEventListener('click', takeSnapshot);
    function takeSnapshot() {
        // Эффект белой вспышки
        flashOverlay.classList.add('active');
        setTimeout(() => flashOverlay.classList.remove('active'), 250);

        // Скачивание файла PNG
        const link = document.createElement('a');
        link.download = `ascii_mirror_${new Date().toISOString().replace(/[:.]/g, '-')}.png`;
        link.href = asciiCanvas.toDataURL('image/png');
        link.click();
        showToast('📸 Снимок сохранен в Загрузки');
    }

    // Кнопка Копирования в буфер обмена
    btnCopy.addEventListener('click', copyToClipboard);
    async function copyToClipboard() {
        if (!lastAsciiText) return;
        try {
            await navigator.clipboard.writeText(lastAsciiText);
            showToast('✓ ASCII-арт скопирован в буфер обмена');
        } catch (err) {
            showToast('Ошибка копирования в буфер');
        }
    }

    // Полноэкранный режим
    btnFullscreen.addEventListener('click', () => {
        if (!document.fullscreenElement) {
            document.documentElement.requestFullscreen().catch(() => {});
        } else {
            document.exitFullscreen().catch(() => {});
        }
    });

    // Всплывающее Apple Toast уведомление
    let toastTimeout = null;
    function showToast(message) {
        toastMsg.textContent = message;
        toast.classList.remove('hidden');
        if (toastTimeout) clearTimeout(toastTimeout);
        toastTimeout = setTimeout(() => toast.classList.add('hidden'), 2200);
    }

    /**
     * 6. Поддержка горячих клавиш (EN и RU)
     */
    window.addEventListener('keydown', (e) => {
        const key = e.key.toLowerCase();
        if (key === ' ' || key === 'space') {
            e.preventDefault();
            togglePause();
        } else if (key === 'c' || key === 'с') {
            copyToClipboard();
        } else if (key === 's' || key === 'ы') {
            takeSnapshot();
        } else if (key === 'm' || key === 'ь') {
            btnMirror.click();
        } else if (key === 'f' || key === 'а') {
            btnFullscreen.click();
        } else if (key === '1') setMode('pixel');
        else if (key === '2') setMode('neon');
        else if (key === '3') setMode('matrix');
        else if (key === '4') setMode('silver');
        else if (key === '5') setMode('amber');
        else if (key === '6') setMode('invert');
    });

    // Старт приложения
    initCamera();
})();
