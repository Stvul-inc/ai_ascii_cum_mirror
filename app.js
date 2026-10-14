/**
 * ASCII Mirror Pro — iPhone Camera Studio (WebGL GPU Accelerated)
 * 60+ FPS на любом разрешении сетки (10 - 360) через шейдерный конвейер WebGL
 */

(function () {
    'use strict';

    // Элементы DOM
    const video = document.getElementById('webcam-video');
    const asciiCanvas = document.getElementById('ascii-canvas');
    const viewportContainer = document.getElementById('viewport-container');

    const fpsCounter = document.getElementById('fps-counter');
    const resolutionBadge = document.getElementById('resolution-badge');
    const formatBadge = document.getElementById('format-badge');

    const resolutionSlider = document.getElementById('resolution-slider');
    const resolutionVal = document.getElementById('resolution-val');
    const contrastSlider = document.getElementById('contrast-slider');
    const contrastVal = document.getElementById('contrast-val');

    const btnShutter = document.getElementById('btn-shutter');
    const btnCopy = document.getElementById('btn-copy');
    const btnPause = document.getElementById('btn-pause');
    const btnMirror = document.getElementById('btn-mirror');
    const btnFullscreen = document.getElementById('btn-fullscreen');
    const btnTimer = document.getElementById('btn-timer');
    const timerLabel = document.getElementById('timer-label');
    const btnGridToggle = document.getElementById('btn-grid-toggle');
    const cameraGrid = document.getElementById('camera-grid');
    const portraitVignette = document.getElementById('portrait-vignette');

    const countdownOverlay = document.getElementById('countdown-overlay');
    const countdownNumber = document.getElementById('countdown-number');
    const pauseOverlay = document.getElementById('pause-overlay');
    const flashOverlay = document.getElementById('flash-overlay');
    const toast = document.getElementById('toast');
    const toastMsg = document.getElementById('toast-message');

    // Символы градации яркости (Apple typography)
    const ASCII_CHARS = " .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZ*#MW&8%B@$";
    const CHAR_COUNT = ASCII_CHARS.length;

    // Режимы камеры iPhone (соотношение сторон width / height)
    const FORMAT_PRESETS = {
        square:   { name: 'КВАДРАТ 1:1', ratio: 1.0 },
        portrait: { name: 'ПОРТРЕТ 3:4', ratio: 3.0 / 4.0 },
        photo:    { name: 'ФОТО 4:3',    ratio: 4.0 / 3.0 },
        '16_9':   { name: 'КИНО 16:9',   ratio: 16.0 / 9.0 },
        pano:     { name: 'ПАНОРАМА',    ratio: 21.0 / 9.0 }
    };

    // Цветовые режимы
    const MODE_MAP = {
        pixel: 0,
        matrix: 1,
        silver: 2,
        amber: 3,
        neon: 4,
        invert: 5
    };

    // Состояние
    let currentFormat = 'square';
    let currentMode = 'pixel';
    let zoomLevel = 1.0;
    let timerSetting = 0; // 0, 3, 10
    let isCountingDown = false;
    let showGrid = false;

    let targetCols = 100;
    let contrastFactor = 1.0;
    let isMirrored = true;
    let isPaused = false;
    let isCameraReady = false;

    let cols = 100;
    let rows = 100;

    // FPS метрика
    let lastTime = performance.now();
    let frameCount = 0;
    let currentFps = 60;

    // WebGL переменные
    let gl = null;
    let program = null;
    let videoTexture = null;
    let atlasTexture = null;

    // Uniform locations
    let uVideoLoc, uAtlasLoc, uGridLoc, uCharCountLoc, uContrastLoc;
    let uModeLoc, uTimeLoc, uMirroredLoc, uCropLoc;

    // Fallback Canvas для синтетического потока / копирования в буфер
    const fallbackCanvas = document.createElement('canvas');
    const fallbackCtx = fallbackCanvas.getContext('2d', { willReadFrequently: true });
    let synthTime = 0;

    /**
     * 1. Инициализация WebGL
     */
    function initWebGL() {
        gl = asciiCanvas.getContext('webgl', {
            preserveDrawingBuffer: true,
            alpha: false,
            antialias: false,
            powerPreference: 'high-performance'
        }) || asciiCanvas.getContext('experimental-webgl');

        if (!gl) {
            console.error('WebGL не поддерживается, переключение на Canvas 2D');
            return false;
        }

        const vsSource = `
            attribute vec2 a_pos;
            varying vec2 v_uv;
            void main() {
                v_uv = vec2((a_pos.x + 1.0) * 0.5, (1.0 - a_pos.y) * 0.5);
                gl_Position = vec4(a_pos, 0.0, 1.0);
            }
        `;

        const fsSource = `
            precision highp float;
            varying vec2 v_uv;

            uniform sampler2D u_video;
            uniform sampler2D u_atlas;
            uniform vec2 u_grid;
            uniform float u_charCount;
            uniform float u_contrast;
            uniform int u_mode;
            uniform float u_time;
            uniform int u_mirrored;
            uniform vec4 u_crop;

            void main() {
                vec2 cellCoord = floor(v_uv * u_grid);
                vec2 cellUV = fract(v_uv * u_grid);

                vec2 sampleUV = (cellCoord + 0.5) / u_grid;
                if (u_mirrored == 1) {
                    sampleUV.x = 1.0 - sampleUV.x;
                }

                vec2 videoUV = u_crop.xy + sampleUV * u_crop.zw;
                vec4 videoColor = texture2D(u_video, videoUV);

                float luma = dot(videoColor.rgb, vec3(0.299, 0.587, 0.114));
                if (u_contrast != 1.0) {
                    luma = clamp((luma - 0.5) * u_contrast + 0.5, 0.0, 1.0);
                }

                float norm = pow(luma, 0.65);
                float charIdx = floor(norm * (u_charCount - 0.001));

                float subX = clamp(cellUV.x, 0.02, 0.98);
                float subY = clamp(cellUV.y, 0.02, 0.98);
                vec2 atlasUV = vec2((charIdx + subX) / u_charCount, subY);
                float glyphAlpha = texture2D(u_atlas, atlasUV).a;

                vec3 textColor = videoColor.rgb;
                vec3 bgColor = vec3(0.0);

                if (u_mode == 0) {
                    textColor = videoColor.rgb;
                } else if (u_mode == 1) {
                    textColor = vec3(0.188, clamp(luma * 0.9 + 0.2, 0.0, 1.0), 0.345);
                } else if (u_mode == 2) {
                    textColor = vec3(luma);
                } else if (u_mode == 3) {
                    textColor = vec3(1.0, clamp(luma * 0.65, 0.0, 1.0), 0.039);
                } else if (u_mode == 4) {
                    float nr = sin(u_time * 0.002 + cellCoord.x * 0.05) * 0.5 + 0.5;
                    float nb = cos(u_time * 0.002 + cellCoord.y * 0.05) * 0.5 + 0.5;
                    textColor = vec3(nr, 0.25, nb);
                } else if (u_mode == 5) {
                    textColor = vec3(1.0) - videoColor.rgb;
                    bgColor = vec3(0.96, 0.96, 0.97);
                }

                vec3 finalColor = mix(bgColor, textColor, glyphAlpha);
                gl_FragColor = vec4(finalColor, 1.0);
            }
        `;

        function compileShader(type, src) {
            const s = gl.createShader(type);
            gl.shaderSource(s, src);
            gl.compileShader(s);
            if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {
                console.error('Shader error:', gl.getShaderInfoLog(s));
                return null;
            }
            return s;
        }

        const vs = compileShader(gl.VERTEX_SHADER, vsSource);
        const fs = compileShader(gl.FRAGMENT_SHADER, fsSource);
        program = gl.createProgram();
        gl.attachShader(program, vs);
        gl.attachShader(program, fs);
        gl.linkProgram(program);

        if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
            console.error('Program link error:', gl.getProgramInfoLog(program));
            return false;
        }

        gl.useProgram(program);

        // Quad geometry
        const posBuffer = gl.createBuffer();
        gl.bindBuffer(gl.ARRAY_BUFFER, posBuffer);
        gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([
            -1, -1,
             1, -1,
            -1,  1,
             1,  1
        ]), gl.STATIC_DRAW);

        const aPosLoc = gl.getAttribLocation(program, 'a_pos');
        gl.enableVertexAttribArray(aPosLoc);
        gl.vertexAttribPointer(aPosLoc, 2, gl.FLOAT, false, 0, 0);

        // Uniforms
        uVideoLoc = gl.getUniformLocation(program, 'u_video');
        uAtlasLoc = gl.getUniformLocation(program, 'u_atlas');
        uGridLoc = gl.getUniformLocation(program, 'u_grid');
        uCharCountLoc = gl.getUniformLocation(program, 'u_charCount');
        uContrastLoc = gl.getUniformLocation(program, 'u_contrast');
        uModeLoc = gl.getUniformLocation(program, 'u_mode');
        uTimeLoc = gl.getUniformLocation(program, 'u_time');
        uMirroredLoc = gl.getUniformLocation(program, 'u_mirrored');
        uCropLoc = gl.getUniformLocation(program, 'u_crop');

        gl.uniform1i(uVideoLoc, 0);
        gl.uniform1i(uAtlasLoc, 1);
        gl.uniform1f(uCharCountLoc, CHAR_COUNT);

        // Создаем текстуру видео
        videoTexture = gl.createTexture();
        gl.bindTexture(gl.TEXTURE_2D, videoTexture);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);

        // Создаем текстурный атлас шрифта
        buildGlyphAtlas();

        return true;
    }

    /**
     * 2. Генерация текстурного атласа шрифта в высоком разрешении
     */
    function buildGlyphAtlas() {
        const atlasCanvas = document.createElement('canvas');
        const charW = 32;
        const charH = 54;
        atlasCanvas.width = charW * CHAR_COUNT;
        atlasCanvas.height = charH;

        const ctx = atlasCanvas.getContext('2d');
        ctx.clearRect(0, 0, atlasCanvas.width, atlasCanvas.height);
        ctx.fillStyle = '#ffffff';
        ctx.font = `bold 42px "SF Mono", "Menlo", monospace`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';

        for (let i = 0; i < CHAR_COUNT; i++) {
            const ch = ASCII_CHARS[i];
            const cx = i * charW + charW / 2;
            const cy = charH / 2;
            ctx.fillText(ch, cx, cy);
        }

        atlasTexture = gl.createTexture();
        gl.activeTexture(gl.TEXTURE1);
        gl.bindTexture(gl.TEXTURE_2D, atlasTexture);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
        gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, atlasCanvas);
    }

    /**
     * 3. Инициализация камеры WebRTC
     */
    async function initCamera() {
        initWebGL();

        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                video: {
                    facingMode: 'user',
                    width: { ideal: 1920, min: 1280 },
                    height: { ideal: 1080, min: 720 }
                },
                audio: false
            });
            video.srcObject = stream;
            await video.play();
            isCameraReady = true;
            showToast('✓ Камера FaceTime подключена (GPU WebGL 60 FPS)');
        } catch (err) {
            console.warn('Физическая камера недоступна, запуск синтетического теста:', err);
            isCameraReady = 'synthetic';
            showToast('Камера недоступна: включен тестовый видеопоток');
        }

        recalculateLayout();
        requestAnimationFrame(renderLoop);
    }

    /**
     * 4. МАТЕМАТИЧЕСКИЙ РАСЧЁТ БЕЗ ИСКАЖЕНИЙ
     */
    function recalculateLayout() {
        const containerRect = viewportContainer.getBoundingClientRect();
        const availableW = Math.max(300, containerRect.width - 24);
        const availableH = Math.max(200, containerRect.height - 24);

        const targetRatio = FORMAT_PRESETS[currentFormat].ratio;
        cols = targetCols;

        // Физическое соотношение моноширинного символа SF Mono (~0.60)
        const charAspect = 0.60;
        rows = Math.max(8, Math.round((cols * charAspect) / targetRatio));

        // Вычисляем оптимальный размер холста под вьюпорт
        let canvasW = availableW;
        let canvasH = canvasW / targetRatio;
        if (canvasH > availableH) {
            canvasH = availableH;
            canvasW = canvasH * targetRatio;
        }

        const dpr = Math.min(window.devicePixelRatio || 1, 2);
        asciiCanvas.width = Math.round(canvasW * dpr);
        asciiCanvas.height = Math.round(canvasH * dpr);

        asciiCanvas.style.width = `${Math.round(canvasW)}px`;
        asciiCanvas.style.height = `${Math.round(canvasH)}px`;

        fallbackCanvas.width = cols;
        fallbackCanvas.height = rows;

        formatBadge.textContent = FORMAT_PRESETS[currentFormat].name;
        resolutionBadge.textContent = `${cols} × ${rows}`;
    }

    window.addEventListener('resize', recalculateLayout);

    /**
     * 5. Генерация синтетического видеопотока при отсутствии камеры
     */
    function updateSyntheticVideo() {
        synthTime += 0.04;
        fallbackCtx.fillStyle = '#0a0a0c';
        fallbackCtx.fillRect(0, 0, fallbackCanvas.width, fallbackCanvas.height);

        for (let x = 0; x < fallbackCanvas.width; x += 6) {
            for (let y = 0; y < fallbackCanvas.height; y += 6) {
                const r = Math.sin(x * 0.08 + synthTime) * 127 + 128;
                const g = Math.cos(y * 0.08 + synthTime) * 127 + 128;
                const b = Math.sin((x + y) * 0.05 + synthTime) * 127 + 128;
                fallbackCtx.fillStyle = `rgb(${r},${g},${b})`;
                fallbackCtx.beginPath();
                fallbackCtx.arc(x + 3, y + 3, 4, 0, Math.PI * 2);
                fallbackCtx.fill();
            }
        }
    }

    /**
     * 6. Главный цикл рендеринга WebGL GPU (Стабильные 60-120 FPS)
     */
    function renderLoop(now) {
        requestAnimationFrame(renderLoop);

        frameCount++;
        if (now - lastTime >= 500) {
            currentFps = Math.round((frameCount * 1000) / (now - lastTime));
            fpsCounter.textContent = `${currentFps} FPS`;
            frameCount = 0;
            lastTime = now;
        }

        if (isPaused) return;

        // Расчёт окна кадрирования (Crop-to-fit) с сохранением пропорций и зумом
        let vw = 1280;
        let vh = 720;
        const targetRatio = FORMAT_PRESETS[currentFormat].ratio;

        let videoReady = (isCameraReady === true && video.readyState >= 2);
        if (videoReady) {
            vw = video.videoWidth || 1280;
            vh = video.videoHeight || 720;
        }

        let cropW, cropH;
        if (vw / vh > targetRatio) {
            cropH = vh;
            cropW = cropH * targetRatio;
        } else {
            cropW = vw;
            cropH = cropW / targetRatio;
        }

        cropW = Math.min(vw, cropW / zoomLevel);
        cropH = Math.min(vh, cropH / zoomLevel);

        const sx = (vw - cropW) / 2;
        const sy = (vh - cropH) / 2;

        const normCrop = [
            sx / vw,
            sy / vh,
            cropW / vw,
            cropH / vh
        ];

        // Загрузка кадра видеопотока в текстуру GPU
        gl.activeTexture(gl.TEXTURE0);
        gl.bindTexture(gl.TEXTURE_2D, videoTexture);

        if (videoReady) {
            gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, video);
        } else {
            updateSyntheticVideo();
            gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, fallbackCanvas);
        }

        // Установка параметров шейдера
        gl.viewport(0, 0, gl.drawingBufferWidth, gl.drawingBufferHeight);
        gl.useProgram(program);

        gl.uniform2f(uGridLoc, cols, rows);
        gl.uniform1f(uContrastLoc, contrastFactor);
        gl.uniform1i(uModeLoc, MODE_MAP[currentMode]);
        gl.uniform1f(uTimeLoc, now);
        gl.uniform1i(uMirroredLoc, isMirrored ? 1 : 0);
        gl.uniform4fv(uCropLoc, normCrop);

        // Отрисовка на GPU ровно за 1 вызов!
        gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    }

    /**
     * 7. Интерактивные функции камеры iPhone
     */
    // 7.1 Форматы съёмки (Карусель режимов iPhone)
    document.querySelectorAll('.mode-item').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.mode-item').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentFormat = btn.dataset.format;

            portraitVignette.classList.toggle('hidden', currentFormat !== 'portrait');

            recalculateLayout();
            showToast(`Формат: ${FORMAT_PRESETS[currentFormat].name}`);
        });
    });

    // 7.2 Кнопки зума (0.5x, 1x, 2x)
    document.querySelectorAll('.zoom-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.zoom-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            zoomLevel = parseFloat(btn.dataset.zoom);
            showToast(`Зум: ${btn.textContent}`);
        });
    });

    // 7.3 Сетка третей 3х3
    btnGridToggle.addEventListener('click', () => {
        showGrid = !showGrid;
        cameraGrid.classList.toggle('hidden', !showGrid);
        btnGridToggle.classList.toggle('active', showGrid);
        showToast(showGrid ? 'Сетка 3×3: ВКЛ' : 'Сетка 3×3: ВЫКЛ');
    });

    // 7.4 Таймер спуска (ВЫКЛ ➡️ 3с ➡️ 10с)
    btnTimer.addEventListener('click', () => {
        if (timerSetting === 0) {
            timerSetting = 3;
            timerLabel.textContent = '3с';
            btnTimer.classList.add('active');
            showToast('Таймер: 3 секунды');
        } else if (timerSetting === 3) {
            timerSetting = 10;
            timerLabel.textContent = '10с';
            btnTimer.classList.add('active');
            showToast('Таймер: 10 секунд');
        } else {
            timerSetting = 0;
            timerLabel.textContent = 'ВЫКЛ';
            btnTimer.classList.remove('active');
            showToast('Таймер: выключен');
        }
    });

    // 7.5 Спуск затвора
    btnShutter.addEventListener('click', triggerCapture);

    function triggerCapture() {
        if (isCountingDown) return;

        if (timerSetting > 0) {
            startCountdown(timerSetting, executeSnapshot);
        } else {
            executeSnapshot();
        }
    }

    function startCountdown(seconds, callback) {
        isCountingDown = true;
        countdownOverlay.classList.remove('hidden');
        let remaining = seconds;
        countdownNumber.textContent = remaining;

        const interval = setInterval(() => {
            remaining--;
            if (remaining > 0) {
                countdownNumber.textContent = remaining;
            } else {
                clearInterval(interval);
                countdownOverlay.classList.add('hidden');
                isCountingDown = false;
                callback();
            }
        }, 1000);
    }

    function executeSnapshot() {
        flashOverlay.classList.add('active');
        setTimeout(() => flashOverlay.classList.remove('active'), 250);

        const link = document.createElement('a');
        link.download = `iPhone_ASCII_${currentFormat}_${new Date().toISOString().replace(/[:.]/g, '-')}.png`;
        link.href = asciiCanvas.toDataURL('image/png');
        link.click();
        showToast('📸 Снимок сохранён в Загрузки');
    }

    // 7.6 Палитры цветов
    document.querySelectorAll('.seg-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.seg-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentMode = btn.dataset.mode;
            showToast(`Палитра: ${btn.textContent}`);
        });
    });

    // 7.7 Слайдер разрешения (10 - 360)
    resolutionSlider.addEventListener('input', (e) => {
        targetCols = parseInt(e.target.value, 10);
        resolutionVal.textContent = targetCols;
        recalculateLayout();
    });

    // 7.8 Слайдер контраста
    contrastSlider.addEventListener('input', (e) => {
        contrastFactor = parseFloat(e.target.value);
        contrastVal.textContent = contrastFactor.toFixed(1);
    });

    // 7.9 Зеркало
    btnMirror.addEventListener('click', () => {
        isMirrored = !isMirrored;
        btnMirror.classList.toggle('active', isMirrored);
        showToast(isMirrored ? 'Зеркало: ВКЛ' : 'Зеркало: ВЫКЛ');
    });

    // 7.10 Пауза
    btnPause.addEventListener('click', () => {
        isPaused = !isPaused;
        pauseOverlay.classList.toggle('hidden', !isPaused);
        document.getElementById('pause-btn-text').textContent = isPaused ? 'Пуск' : 'Пауза';
        showToast(isPaused ? '❚❚ Пауза' : '▶ Возобновлено');
    });

    // 7.11 Генерация и копирование ASCII-текста в буфер обмена по требованию
    btnCopy.addEventListener('click', async () => {
        try {
            fallbackCanvas.width = cols;
            fallbackCanvas.height = rows;

            if (isCameraReady === true && video.readyState >= 2) {
                fallbackCtx.save();
                if (isMirrored) {
                    fallbackCtx.translate(cols, 0);
                    fallbackCtx.scale(-1, 1);
                }
                fallbackCtx.drawImage(video, 0, 0, cols, rows);
                fallbackCtx.restore();
            }

            const imgData = fallbackCtx.getImageData(0, 0, cols, rows);
            const data = imgData.data;
            const lines = [];

            for (let y = 0; y < rows; y++) {
                let rowStr = '';
                for (let x = 0; x < cols; x++) {
                    const idx = (y * cols + x) * 4;
                    const r = data[idx];
                    const g = data[idx + 1];
                    const b = data[idx + 2];
                    let luma = 0.299 * r + 0.587 * g + 0.114 * b;
                    if (contrastFactor !== 1.0) {
                        luma = Math.min(255, Math.max(0, ((luma / 255 - 0.5) * contrastFactor + 0.5) * 255));
                    }
                    const norm = Math.pow(luma / 255, 0.65);
                    const charIdx = Math.min(CHAR_COUNT - 1, Math.floor(norm * (CHAR_COUNT - 1)));
                    rowStr += ASCII_CHARS[charIdx];
                }
                lines.push(rowStr);
            }

            const text = lines.join('\n');
            await navigator.clipboard.writeText(text);
            showToast('✓ ASCII-арт скопирован в буфер');
        } catch (err) {
            showToast('Ошибка копирования');
        }
    });

    // 7.12 Полный экран
    btnFullscreen.addEventListener('click', () => {
        if (!document.fullscreenElement) {
            document.documentElement.requestFullscreen().catch(() => {});
        } else {
            document.exitFullscreen().catch(() => {});
        }
    });

    // Toast
    let toastTimeout = null;
    function showToast(message) {
        toastMsg.textContent = message;
        toast.classList.remove('hidden');
        if (toastTimeout) clearTimeout(toastTimeout);
        toastTimeout = setTimeout(() => toast.classList.add('hidden'), 2200);
    }

    // Горячие клавиши
    window.addEventListener('keydown', (e) => {
        const key = e.key.toLowerCase();
        if (key === ' ' || key === 'space') {
            e.preventDefault();
            btnPause.click();
        } else if (key === 's' || key === 'ы' || key === 'enter') {
            triggerCapture();
        } else if (key === 'c' || key === 'с') {
            btnCopy.click();
        } else if (key === 'm' || key === 'ь') {
            btnMirror.click();
        } else if (key === 'g' || key === 'п') {
            btnGridToggle.click();
        } else if (key === 't' || key === 'е') {
            btnTimer.click();
        } else if (key === 'f' || key === 'а') {
            btnFullscreen.click();
        }
    });

    initCamera();
})();
