/**
 * ASCII Mirror Pro — iPhone Camera Studio (WebGL GPU + Vector SVG Engine)
 * 60+ FPS на любом разрешении сетки (10 - 360) + живой SVG-режим + экспорт PNG / SVG / PDF
 */

(function () {
    'use strict';

    // Элементы DOM
    const video = document.getElementById('webcam-video');
    const asciiCanvas = document.getElementById('ascii-canvas');
    const asciiSvg = document.getElementById('ascii-svg');
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

    // Каноничная шкала яркости: от тусклой точки '.' до яркой 'O' и '@'
    const ASCII_CHARS = "   ....::::----++++****ooooOOOO0000####%%%%@@@@";
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
    let currentEngine = 'webgl'; // 'webgl' или 'svg'
    let exportFormat = 'png';    // 'png', 'svg', 'pdf'
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

    // Fallback Canvas для синтетики, SVG-рендеринга и экспорта
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
            console.warn('WebGL недоступен, автоматическое переключение на SVG');
            switchEngine('svg');
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

                float norm = clamp(pow(luma, 0.85), 0.0, 1.0);
                float charIdx = floor(norm * (u_charCount - 0.001));

                float subX = clamp(cellUV.x, 0.02, 0.98);
                float subY = clamp(cellUV.y, 0.02, 0.98);
                vec2 atlasUV = vec2((charIdx + subX) / u_charCount, subY);
                float glyphAlpha = texture2D(u_atlas, atlasUV).a;

                vec3 textColor = videoColor.rgb;
                vec3 bgColor = vec3(0.0);

                // Режим 0: истинные, натуральные цвета веб-камеры
                if (u_mode == 0) {
                    textColor = videoColor.rgb;
                } else if (u_mode == 1) {
                    textColor = vec3(0.0, 1.0, 0.25);
                } else if (u_mode == 2) {
                    textColor = vec3(1.0, 1.0, 1.0);
                } else if (u_mode == 3) {
                    textColor = vec3(1.0, 0.72, 0.05);
                } else if (u_mode == 4) {
                    float nr = sin(u_time * 0.002 + cellCoord.x * 0.05) * 0.5 + 0.5;
                    float nb = cos(u_time * 0.002 + cellCoord.y * 0.05) * 0.5 + 0.5;
                    textColor = normalize(vec3(nr, 0.35, nb));
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

        videoTexture = gl.createTexture();
        gl.bindTexture(gl.TEXTURE_2D, videoTexture);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);

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
     * 3. Переключение движка рендеринга: GPU (WebGL) <-> Вектор (SVG)
     */
    function switchEngine(engine) {
        currentEngine = engine;
        document.querySelectorAll('.engine-btn').forEach(b => {
            b.classList.toggle('active', b.dataset.engine === engine);
        });

        if (engine === 'svg') {
            asciiCanvas.classList.add('hidden');
            asciiSvg.classList.remove('hidden');
            showToast('📐 Векторный режим SVG активирован');
        } else {
            asciiSvg.classList.add('hidden');
            asciiCanvas.classList.remove('hidden');
            showToast('⚡️ Аппаратный WebGL 60 FPS активирован');
        }
        recalculateLayout();
    }

    /**
     * 4. Инициализация камеры WebRTC
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
            showToast('✓ Камера FaceTime подключена');
        } catch (err) {
            console.warn('Физическая камера недоступна, включен синтетический поток:', err);
            isCameraReady = 'synthetic';
            showToast('Камера недоступна: включен тестовый видеопоток');
        }

        recalculateLayout();
        requestAnimationFrame(renderLoop);
    }

    /**
     * 5. Точный расчёт пропорций без искажений
     */
    function recalculateLayout() {
        const isCamMode = document.body.classList.contains('cam-mode');
        const containerRect = viewportContainer.getBoundingClientRect();
        const availableW = isCamMode ? window.innerWidth : Math.max(300, containerRect.width - 24);
        const availableH = isCamMode ? window.innerHeight : Math.max(200, containerRect.height - 24);

        const targetRatio = FORMAT_PRESETS[currentFormat].ratio;
        cols = targetCols;

        const charAspect = 0.60;
        rows = Math.max(8, Math.round((cols * charAspect) / targetRatio));

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

        asciiSvg.style.width = `${Math.round(canvasW)}px`;
        asciiSvg.style.height = `${Math.round(canvasH)}px`;

        fallbackCanvas.width = cols;
        fallbackCanvas.height = rows;

        if (formatBadge) formatBadge.textContent = FORMAT_PRESETS[currentFormat].name;
        if (resolutionBadge) resolutionBadge.textContent = `${cols} × ${rows}`;
    }

    window.addEventListener('resize', recalculateLayout);

    /**
     * 6. Синтетический поток при отсутствии веб-камеры
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
     * 7. Извлечение кадра и данных пикселей
     */
    function extractFrameData() {
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

        fallbackCanvas.width = cols;
        fallbackCanvas.height = rows;

        if (videoReady) {
            fallbackCtx.save();
            if (isMirrored) {
                fallbackCtx.translate(cols, 0);
                fallbackCtx.scale(-1, 1);
            }
            fallbackCtx.drawImage(video, sx, sy, cropW, cropH, 0, 0, cols, rows);
            fallbackCtx.restore();
        } else {
            updateSyntheticVideo();
        }

        return fallbackCtx.getImageData(0, 0, cols, rows).data;
    }

    /**
     * 8. Расчёт символов и цветов кадра с батчингом повторений
     */
    function getFrameCharactersAndColors(now) {
        const data = extractFrameData();
        const rowsData = [];
        const timeSec = (now || performance.now()) * 0.002;
        const isLight = (currentMode === 'invert');
        const bgColor = isLight ? '#f5f5f7' : '#000000';
        const bgRgb = isLight ? [0.96, 0.96, 0.97] : [0.0, 0.0, 0.0];

        for (let y = 0; y < rows; y++) {
            const rowRuns = [];
            let curColor = null;
            let curRgb = null;
            let curText = '';

            for (let x = 0; x < cols; x++) {
                const idx = (y * cols + x) * 4;
                const r = data[idx];
                const g = data[idx + 1];
                const b = data[idx + 2];

                let luma = 0.299 * r + 0.587 * g + 0.114 * b;
                if (contrastFactor !== 1.0) {
                    luma = Math.min(255, Math.max(0, ((luma / 255 - 0.5) * contrastFactor + 0.5) * 255));
                }

                const norm = Math.min(1.0, Math.max(0.0, Math.pow(luma / 255, 0.85)));
                const charIdx = Math.min(CHAR_COUNT - 1, Math.floor(norm * (CHAR_COUNT - 1)));
                const ch = ASCII_CHARS[charIdx];

                let cr, cg, cb;
                if (currentMode === 'pixel') {
                    cr = r; cg = g; cb = b;
                } else if (currentMode === 'matrix') {
                    cr = 0; cg = 255; cb = 65;
                } else if (currentMode === 'silver') {
                    cr = 255; cg = 255; cb = 255;
                } else if (currentMode === 'amber') {
                    cr = 255; cg = 184; cb = 13;
                } else if (currentMode === 'neon') {
                    cr = Math.round(Math.sin(timeSec + x * 0.05) * 127 + 128);
                    cg = 90;
                    cb = Math.round(Math.cos(timeSec + y * 0.05) * 127 + 128);
                } else if (currentMode === 'invert') {
                    cr = 255 - r; cg = 255 - g; cb = 255 - b;
                }

                const colorStr = `rgb(${cr},${cg},${cb})`;

                if (colorStr !== curColor) {
                    if (curText) {
                        rowRuns.push({ text: curText, color: curColor, rgb: curRgb });
                    }
                    curColor = colorStr;
                    curRgb = [cr / 255, cg / 255, cb / 255];
                    curText = ch;
                } else {
                    curText += ch;
                }
            }

            if (curText) {
                rowRuns.push({ text: curText, color: curColor, rgb: curRgb });
            }
            rowsData.push(rowRuns);
        }

        return { rowsData, bgColor, bgRgb };
    }

    /**
     * 9. Живой рендеринг в векторный SVG
     */
    function renderLiveSVG(now) {
        const { rowsData, bgColor } = getFrameCharactersAndColors(now);
        const charAspect = 0.60;
        const cellW = 10;
        const cellH = Math.round(cellW / charAspect);
        const finalW = cols * cellW;
        const finalH = rows * cellH;

        let svgInner = `<rect width="100%" height="100%" fill="${bgColor}"/>`;
        svgInner += `<style>text { font-family: "SF Mono", "Menlo", monospace; font-size: ${cellH}px; font-weight: bold; }</style>`;

        for (let y = 0; y < rows; y++) {
            const py = (y + 1) * cellH - Math.round(cellH * 0.2);
            svgInner += `<text x="0" y="${py}" xml:space="preserve">`;
            for (const run of rowsData[y]) {
                const escaped = run.text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
                svgInner += `<tspan fill="${run.color}">${escaped}</tspan>`;
            }
            svgInner += `</text>`;
        }

        asciiSvg.setAttribute('viewBox', `0 0 ${finalW} ${finalH}`);
        asciiSvg.innerHTML = svgInner;
    }

    /**
     * 10. Главный цикл рендеринга
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

        if (currentEngine === 'svg') {
            renderLiveSVG(now);
            return;
        }

        // WebGL GPU Рендеринг
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

        gl.activeTexture(gl.TEXTURE0);
        gl.bindTexture(gl.TEXTURE_2D, videoTexture);

        if (videoReady) {
            gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, video);
        } else {
            updateSyntheticVideo();
            gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, fallbackCanvas);
        }

        gl.viewport(0, 0, gl.drawingBufferWidth, gl.drawingBufferHeight);
        gl.useProgram(program);

        gl.uniform2f(uGridLoc, cols, rows);
        gl.uniform1f(uContrastLoc, contrastFactor);
        gl.uniform1i(uModeLoc, MODE_MAP[currentMode]);
        gl.uniform1f(uTimeLoc, now);
        gl.uniform1i(uMirroredLoc, isMirrored ? 1 : 0);
        gl.uniform4fv(uCropLoc, normCrop);

        gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    }

    /**
     * 11. Генерация векторного файла SVG
     */
    function generateVectorSVG() {
        const { rowsData, bgColor } = getFrameCharactersAndColors();
        const charAspect = 0.60;
        const cellW = 12;
        const cellH = Math.round(cellW / charAspect);
        const finalW = cols * cellW;
        const finalH = rows * cellH;

        let svg = `<?xml version="1.0" encoding="UTF-8"?>\n`;
        svg += `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${finalW} ${finalH}" width="${finalW}" height="${finalH}">\n`;
        svg += `  <rect width="100%" height="100%" fill="${bgColor}"/>\n`;
        svg += `  <style>\n    text { font-family: "SF Mono", "Menlo", "Courier New", monospace; font-size: ${cellH}px; font-weight: bold; }\n  </style>\n`;

        for (let y = 0; y < rows; y++) {
            const py = (y + 1) * cellH - Math.round(cellH * 0.2);
            svg += `  <text x="0" y="${py}" xml:space="preserve">`;
            for (const run of rowsData[y]) {
                const escaped = run.text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
                svg += `<tspan fill="${run.color}">${escaped}</tspan>`;
            }
            svg += `</text>\n`;
        }

        svg += `</svg>`;
        return svg;
    }

    /**
     * 12. Генерация полиграфического векторного PDF 1.4
     */
    function generateVectorPDF() {
        const { rowsData, bgRgb } = getFrameCharactersAndColors();
        const charAspect = 0.60;
        const ptFontSize = 10;
        const ptCharW = ptFontSize * charAspect;
        const ptRowH = ptFontSize * 1.25;
        const ptW = cols * ptCharW;
        const ptH = rows * ptRowH;

        let stream = `q\n${bgRgb[0].toFixed(3)} ${bgRgb[1].toFixed(3)} ${bgRgb[2].toFixed(3)} rg\n0 0 ${ptW.toFixed(1)} ${ptH.toFixed(1)} re f\nQ\nBT\n/F1 ${ptFontSize} Tf\n`;

        for (let y = 0; y < rows; y++) {
            const pdfY = ptH - (y + 1) * ptRowH + (ptRowH - ptFontSize) * 0.5;
            let curX = 0;

            for (const run of rowsData[y]) {
                const esc = run.text.replace(/\\/g, '\\\\').replace(/\(/g, '\\(').replace(/\)/g, '\\)');
                stream += `${run.rgb[0].toFixed(3)} ${run.rgb[1].toFixed(3)} ${run.rgb[2].toFixed(3)} rg\n1 0 0 1 ${curX.toFixed(1)} ${pdfY.toFixed(1)} Tm\n(${esc}) Tj\n`;
                curX += run.text.length * ptCharW;
            }
        }

        stream += 'ET\n';
        const streamLen = new TextEncoder().encode(stream).length;

        const objs = [];
        objs.push(`1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n`);
        objs.push(`2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n`);
        objs.push(`3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${ptW.toFixed(1)} ${ptH.toFixed(1)}] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n`);
        objs.push(`4 0 obj\n<< /Length ${streamLen} >>\nstream\n${stream}endstream\nendobj\n`);
        objs.push(`5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Courier-Bold >>\nendobj\n`);

        let pdf = '%PDF-1.4\n';
        const xref = [0];
        for (let i = 0; i < objs.length; i++) {
            xref.push(pdf.length);
            pdf += objs[i];
        }
        const xrefStart = pdf.length;
        pdf += `xref\n0 ${objs.length + 1}\n0000000000 65535 f \n`;
        for (let i = 1; i <= objs.length; i++) {
            pdf += String(xref[i]).padStart(10, '0') + ' 00000 n \n';
        }
        pdf += `trailer\n<< /Size ${objs.length + 1} /Root 1 0 R >>\nstartxref\n${xrefStart}\n%%EOF`;
        return pdf;
    }

    /**
     * 13. Спуск затвора со вспышкой и сохранением выбранного формата (PNG / SVG / PDF)
     */
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

        const timestamp = new Date().toISOString().replace(/[:.]/g, '-');

        if (exportFormat === 'png') {
            const link = document.createElement('a');
            link.download = `iPhone_ASCII_${currentFormat}_${timestamp}.png`;
            link.href = asciiCanvas.toDataURL('image/png');
            link.click();
            showToast('📸 Снимок PNG сохранён');
        } else if (exportFormat === 'svg') {
            const svgData = generateVectorSVG();
            const blob = new Blob([svgData], { type: 'image/svg+xml;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.download = `iPhone_ASCII_${currentFormat}_${timestamp}.svg`;
            link.href = url;
            link.click();
            setTimeout(() => URL.revokeObjectURL(url), 2000);
            showToast('📐 Векторный SVG сохранён');
        } else if (exportFormat === 'pdf') {
            const pdfData = generateVectorPDF();
            const blob = new Blob([pdfData], { type: 'application/pdf' });
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.download = `iPhone_ASCII_${currentFormat}_${timestamp}.pdf`;
            link.href = url;
            link.click();
            setTimeout(() => URL.revokeObjectURL(url), 2000);
            showToast('📄 Полиграфический PDF сохранён');
        }
    }

    /**
     * 14. Обработчики интерфейса
     */
    // 14.1 Переключатель движка: GPU vs SVG
    document.querySelectorAll('.engine-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            switchEngine(btn.dataset.engine);
        });
    });

    // 14.2 Переключатель формата экспорта: PNG / SVG / PDF
    document.querySelectorAll('.export-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.export-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            exportFormat = btn.dataset.export;
            showToast(`Формат съёмки: ${exportFormat.toUpperCase()}`);
        });
    });

    // 14.3 Форматы съёмки iPhone
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

    // 14.4 Кнопки зума (0.5x, 1x, 2x)
    document.querySelectorAll('.zoom-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.zoom-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            zoomLevel = parseFloat(btn.dataset.zoom);
            showToast(`Зум: ${btn.textContent}`);
        });
    });

    // 14.5 Сетка третей 3х3
    btnGridToggle.addEventListener('click', () => {
        showGrid = !showGrid;
        cameraGrid.classList.toggle('hidden', !showGrid);
        btnGridToggle.classList.toggle('active', showGrid);
        showToast(showGrid ? 'Сетка 3×3: ВКЛ' : 'Сетка 3×3: ВЫКЛ');
    });

    // 14.6 Таймер спуска
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

    // 14.7 Кнопка затвора
    btnShutter.addEventListener('click', triggerCapture);

    // 14.8 Палитры цветов
    document.querySelectorAll('.seg-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.seg-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentMode = btn.dataset.mode;
            showToast(`Палитра: ${btn.textContent}`);
        });
    });

    // 14.9 Слайдер разрешения (10 - 360)
    resolutionSlider.addEventListener('input', (e) => {
        targetCols = parseInt(e.target.value, 10);
        resolutionVal.textContent = targetCols;
        recalculateLayout();
    });

    // 14.10 Слайдер контраста
    contrastSlider.addEventListener('input', (e) => {
        contrastFactor = parseFloat(e.target.value);
        contrastVal.textContent = contrastFactor.toFixed(1);
    });

    // 14.11 Зеркало
    btnMirror.addEventListener('click', () => {
        isMirrored = !isMirrored;
        btnMirror.classList.toggle('active', isMirrored);
        showToast(isMirrored ? 'Зеркало: ВКЛ' : 'Зеркало: ВЫКЛ');
    });

    // 14.12 Пауза
    btnPause.addEventListener('click', () => {
        isPaused = !isPaused;
        pauseOverlay.classList.toggle('hidden', !isPaused);
        document.getElementById('pause-btn-text').textContent = isPaused ? 'Пуск' : 'Пауза';
        showToast(isPaused ? '❚❚ Пауза' : '▶ Возобновлено');
    });

    // 14.13 Копирование ASCII-текста в буфер обмена
    btnCopy.addEventListener('click', async () => {
        try {
            const { rowsData } = getFrameCharactersAndColors();
            const text = rowsData.map(row => row.map(run => run.text).join('')).join('\n');
            await navigator.clipboard.writeText(text);
            showToast('✓ ASCII-арт скопирован в буфер');
        } catch (err) {
            showToast('Ошибка копирования');
        }
    });

    // 14.14 Полный экран
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
            if (isAdhdActive && flappyState === 'playing') {
                jumpFlappy();
            } else {
                btnPause.click();
            }
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

    /* ==========================================================================
       15. РЕЖИМ СДВГ / BRAINROT (Игры, залипалово, реклама рунета)
       Изолированный режим: по умолчанию ВЫКЛЮЧЕН, не трогает основной код
       ========================================================================== */
    const appContainer = document.getElementById('app-container');
    const btnAdhdToggle = document.getElementById('btn-adhd-toggle');
    const adhdLeftPanel = document.getElementById('adhd-left-panel');
    const adhdRightPanel = document.getElementById('adhd-right-panel');
    const scamOverlay = document.getElementById('scam-overlay');

    const flappyCanvas = document.getElementById('flappy-canvas');
    const flappyCtx = flappyCanvas ? flappyCanvas.getContext('2d') : null;
    const flappyScoreBadge = document.getElementById('flappy-score-badge');
    const flappyOverlay = document.getElementById('flappy-overlay');
    const flappyMsg = document.getElementById('flappy-msg');
    const btnFlappyRestart = document.getElementById('btn-flappy-restart');

    const satisfyCanvas = document.getElementById('satisfy-canvas');
    const satisfyCtx = satisfyCanvas ? satisfyCanvas.getContext('2d') : null;

    let isAdhdActive = false;
    let flappyAnimId = null;
    let satisfyAnimId = null;
    let scamIntervalId = null;
    let satisfyMode = 'balls';

    // 15.1 Тумблер СДВГ-режима
    if (btnAdhdToggle) {
        btnAdhdToggle.addEventListener('click', () => {
            isAdhdActive = !isAdhdActive;
            btnAdhdToggle.classList.toggle('active', isAdhdActive);
            appContainer.classList.toggle('adhd-active', isAdhdActive);

            if (isAdhdActive) {
                adhdLeftPanel.classList.remove('hidden');
                adhdRightPanel.classList.remove('hidden');
                scamOverlay.classList.remove('hidden');
                startFlappyGame();
                startSatisfySimulation();
                startScamPopups();
                showToast('🧠 Режим СДВГ активирован!');
            } else {
                adhdLeftPanel.classList.add('hidden');
                adhdRightPanel.classList.add('hidden');
                scamOverlay.classList.add('hidden');
                stopFlappyGame();
                stopSatisfySimulation();
                stopScamPopups();
                showToast('🧠 Режим СДВГ выключен');
            }

            // Пересчитываем вьюпорт камеры под доступную ширину
            setTimeout(recalculateLayout, 50);
        });
    }

    // 15.2 Интерактивная игра: Flappy ASCII
    let bird = { x: 40, y: 140, vy: 0, r: 8 };
    let pipes = [];
    let flappyScore = 0;
    let flappyState = 'idle'; // 'idle' | 'playing' | 'dead'
    let lastPipeTime = 0;

    function initFlappy() {
        bird.y = 140;
        bird.vy = 0;
        pipes = [];
        flappyScore = 0;
        flappyState = 'idle';
        if (flappyScoreBadge) flappyScoreBadge.textContent = 'Счёт: 0';
        if (flappyOverlay) flappyOverlay.classList.remove('hidden');
        if (flappyMsg) flappyMsg.textContent = 'Кликни для прыжка';
        drawFlappyScene();
    }

    function jumpFlappy() {
        if (flappyState === 'idle') {
            flappyState = 'playing';
            if (flappyOverlay) flappyOverlay.classList.add('hidden');
            bird.vy = -5.0;
        } else if (flappyState === 'playing') {
            bird.vy = -5.0;
        } else if (flappyState === 'dead') {
            initFlappy();
            flappyState = 'playing';
            if (flappyOverlay) flappyOverlay.classList.add('hidden');
            bird.vy = -5.0;
        }
    }

    if (flappyCanvas) {
        flappyCanvas.addEventListener('mousedown', jumpFlappy);
    }
    if (btnFlappyRestart) {
        btnFlappyRestart.addEventListener('click', (e) => {
            e.stopPropagation();
            initFlappy();
        });
    }

    function updateFlappy() {
        if (flappyState !== 'playing') {
            drawFlappyScene();
            return;
        }

        bird.vy += 0.32;
        bird.y += bird.vy;

        // Генерация труб каждые 1.4 секунды
        const now = performance.now();
        if (now - lastPipeTime > 1400) {
            const gap = 88;
            const topH = Math.floor(Math.random() * (flappyCanvas.height - gap - 80)) + 30;
            pipes.push({ x: flappyCanvas.width, top: topH, gap: gap, passed: false });
            lastPipeTime = now;
        }

        // Движение труб
        for (let i = pipes.length - 1; i >= 0; i--) {
            const p = pipes[i];
            p.x -= 2.0;

            // Проверка счёта
            if (!p.passed && p.x + 30 < bird.x) {
                p.passed = true;
                flappyScore++;
                if (flappyScoreBadge) flappyScoreBadge.textContent = `Счёт: ${flappyScore}`;
            }

            // Коллизия с трубами
            if (bird.x + bird.r > p.x && bird.x - bird.r < p.x + 30) {
                if (bird.y - bird.r < p.top || bird.y + bird.r > p.top + p.gap) {
                    gameOverFlappy();
                    return;
                }
            }

            if (p.x < -40) {
                pipes.splice(i, 1);
            }
        }

        // Коллизия с границами
        if (bird.y + bird.r >= flappyCanvas.height || bird.y - bird.r <= 0) {
            gameOverFlappy();
            return;
        }

        drawFlappyScene();
    }

    function gameOverFlappy() {
        flappyState = 'dead';
        if (flappyOverlay) flappyOverlay.classList.remove('hidden');
        if (flappyMsg) flappyMsg.textContent = `💀 Проиграл! Счёт: ${flappyScore}. Кликни!`;
        drawFlappyScene();
    }

    function drawFlappyScene() {
        if (!flappyCtx) return;
        flappyCtx.fillStyle = '#08080c';
        flappyCtx.fillRect(0, 0, flappyCanvas.width, flappyCanvas.height);

        // Трубы
        for (const p of pipes) {
            flappyCtx.fillStyle = '#30d158';
            flappyCtx.fillRect(p.x, 0, 30, p.top);
            flappyCtx.fillRect(p.x - 2, p.top - 10, 34, 10);

            const botY = p.top + p.gap;
            flappyCtx.fillRect(p.x, botY, 30, flappyCanvas.height - botY);
            flappyCtx.fillRect(p.x - 2, botY, 34, 10);
        }

        // Птичка (пиксельный ASCII-дрон)
        flappyCtx.save();
        flappyCtx.translate(bird.x, bird.y);
        const angle = Math.min(Math.PI / 4, Math.max(-Math.PI / 4, bird.vy * 0.08));
        flappyCtx.rotate(angle);

        flappyCtx.fillStyle = '#ffd60a';
        flappyCtx.fillRect(-8, -6, 16, 12);
        flappyCtx.fillStyle = '#ffffff';
        flappyCtx.fillRect(2, -4, 4, 4);
        flappyCtx.fillStyle = '#000000';
        flappyCtx.fillRect(4, -3, 2, 2);
        flappyCtx.fillStyle = '#ff9f0a';
        flappyCtx.fillRect(6, -1, 5, 4);
        flappyCtx.restore();
    }

    function flappyLoop() {
        if (!isAdhdActive) return;
        updateFlappy();
        flappyAnimId = requestAnimationFrame(flappyLoop);
    }

    function startFlappyGame() {
        initFlappy();
        cancelAnimationFrame(flappyAnimId);
        flappyAnimId = requestAnimationFrame(flappyLoop);
    }

    function stopFlappyGame() {
        cancelAnimationFrame(flappyAnimId);
    }

    // 15.3 СДВГ-залипалово (Неоновые прыгающие шарики & 3D туннель)
    const balls = [];
    const BALL_COLORS = ['#ff2d55', '#00f3ff', '#ffd60a', '#30d158', '#bf5af2', '#ff9f0a'];
    let mouseX = -1000;
    let mouseY = -1000;

    function initSatisfyBalls() {
        balls.length = 0;
        for (let i = 0; i < 55; i++) {
            balls.push({
                x: Math.random() * (satisfyCanvas.width - 20) + 10,
                y: Math.random() * (satisfyCanvas.height - 20) + 10,
                vx: (Math.random() - 0.5) * 4,
                vy: (Math.random() - 0.5) * 4,
                r: Math.random() * 5 + 4,
                color: BALL_COLORS[i % BALL_COLORS.length]
            });
        }
    }

    if (satisfyCanvas) {
        satisfyCanvas.addEventListener('mousemove', (e) => {
            const rect = satisfyCanvas.getBoundingClientRect();
            mouseX = e.clientX - rect.left;
            mouseY = e.clientY - rect.top;
        });
        satisfyCanvas.addEventListener('mouseleave', () => {
            mouseX = -1000;
            mouseY = -1000;
        });
    }

    document.querySelectorAll('.satisfy-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.satisfy-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            satisfyMode = btn.dataset.satisfy;
        });
    });

    let tunnelAngle = 0;
    function renderSatisfySimulation() {
        if (!satisfyCtx) return;

        if (satisfyMode === 'balls') {
            satisfyCtx.fillStyle = 'rgba(8, 8, 12, 0.25)';
            satisfyCtx.fillRect(0, 0, satisfyCanvas.width, satisfyCanvas.height);

            for (const b of balls) {
                b.vy += 0.15; // гравитация
                b.x += b.vx;
                b.y += b.vy;

                // Взаимодействие с курсором (разлёт)
                const dx = b.x - mouseX;
                const dy = b.y - mouseY;
                const dist = Math.sqrt(dx * dx + dy * dy);
                if (dist < 65 && dist > 0) {
                    const force = (65 - dist) * 0.25;
                    b.vx += (dx / dist) * force;
                    b.vy += (dy / dist) * force;
                }

                // Отскок от стен
                if (b.x - b.r < 0) { b.x = b.r; b.vx *= -0.92; }
                if (b.x + b.r > satisfyCanvas.width) { b.x = satisfyCanvas.width - b.r; b.vx *= -0.92; }
                if (b.y - b.r < 0) { b.y = b.r; b.vy *= -0.92; }
                if (b.y + b.r > satisfyCanvas.height) { b.y = satisfyCanvas.height - b.r; b.vy *= -0.88; }

                satisfyCtx.fillStyle = b.color;
                satisfyCtx.beginPath();
                satisfyCtx.arc(b.x, b.y, b.r, 0, Math.PI * 2);
                satisfyCtx.fill();
            }
        } else if (satisfyMode === 'tunnel') {
            satisfyCtx.fillStyle = 'rgba(8, 8, 12, 0.18)';
            satisfyCtx.fillRect(0, 0, satisfyCanvas.width, satisfyCanvas.height);

            tunnelAngle += 0.035;
            const cx = satisfyCanvas.width / 2;
            const cy = satisfyCanvas.height / 2;

            for (let i = 1; i <= 14; i++) {
                const r = (i * 12 + ((performance.now() * 0.05) % 12));
                const hue = (i * 25 + performance.now() * 0.08) % 360;
                satisfyCtx.strokeStyle = `hsl(${hue}, 100%, 60%)`;
                satisfyCtx.lineWidth = 2.5;

                satisfyCtx.save();
                satisfyCtx.translate(cx, cy);
                satisfyCtx.rotate(tunnelAngle + i * 0.15);
                satisfyCtx.strokeRect(-r, -r, r * 2, r * 2);
                satisfyCtx.restore();
            }
        }

        if (isAdhdActive) {
            satisfyAnimId = requestAnimationFrame(renderSatisfySimulation);
        }
    }

    function startSatisfySimulation() {
        initSatisfyBalls();
        cancelAnimationFrame(satisfyAnimId);
        satisfyAnimId = requestAnimationFrame(renderSatisfySimulation);
    }

    function stopSatisfySimulation() {
        cancelAnimationFrame(satisfyAnimId);
    }

    // 15.4 Вирусные скам-баннеры и реклама рунета 2000-х
    const SCAM_TEMPLATES = [
        {
            type: 'scam-garage',
            title: '🚗 ПРОДАМ ГАРАЖ В МЫТИЩАХ',
            desc: 'С ямой, погребом и банками солений 1998 года! Документы утеряны, дед уехал.',
            cta: 'Купить гараж за 15 000 ₽',
            toast: '🚗 Вы успешно забронировали гараж! Дед уже выехал на встречу.'
        },
        {
            type: 'scam-win',
            title: '💰 ВЫ ВЫИГРАЛИ 1 000 000 РУБЛЕЙ!',
            desc: 'Ваш браузер признан победителем 777-й всенародной лотереи! Не закрывайте вкладку.',
            cta: 'Забрать 1 000 000 ₽',
            toast: '💰 Миллион отправлен Почтой России. Ожидайте 40 лет.'
        },
        {
            type: 'scam-virus',
            title: '🚨 ВАШ АЙФОН ЗАРАЖЁН (13 ВИРУСОВ)!',
            desc: 'Обнаружен троян "FaceTime_Horse.exe". Аккумулятор вздуется через 30 секунд!',
            cta: 'Очистить телефон',
            toast: '🚨 Вирусы испугались и самоудалились из системы.'
        },
        {
            type: 'scam-doctor',
            title: '🍋 ВРАЧИ СКРЫВАЛИ 50 ЛЕТ!',
            desc: 'Каждое утро натощак пейте обычный советский... Читать далее пока не запретили.',
            cta: 'Узнать копеечный рецепт',
            toast: '🍋 Рецепт: просто выспитесь и пейте больше воды.'
        },
        {
            type: 'scam-singles',
            title: '🔥 ОДИНОКИЕ ASCII-СИМВОЛЫ',
            desc: 'Красивые скобочки () и фигурные скобки {} в 200 метрах ищут парного программиста!',
            cta: 'Познакомиться сейчас',
            toast: '🔥 Символ "}" застенчиво подмигнул вам в консоли!'
        }
    ];

    function spawnScamBanner() {
        if (!isAdhdActive || !scamOverlay) return;

        // Ограничиваем максимум 4 баннера на экране
        const currentBanners = scamOverlay.querySelectorAll('.scam-banner');
        if (currentBanners.length >= 4) {
            currentBanners[0].remove();
        }

        const tmpl = SCAM_TEMPLATES[Math.floor(Math.random() * SCAM_TEMPLATES.length)];
        const banner = document.createElement('div');
        banner.className = `scam-banner ${tmpl.type}`;

        const posX = Math.floor(Math.random() * (window.innerWidth - 320));
        const posY = Math.floor(Math.random() * (window.innerHeight - 200)) + 40;

        banner.style.left = `${Math.max(10, posX)}px`;
        banner.style.top = `${Math.max(60, posY)}px`;

        banner.innerHTML = `
            <div class="scam-close" title="Закрыть">✕</div>
            <div class="scam-title">${tmpl.title}</div>
            <div class="scam-desc">${tmpl.desc}</div>
            <button class="scam-cta">${tmpl.cta}</button>
        `;

        // Клик по крестику
        const closeBtn = banner.querySelector('.scam-close');
        closeBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            banner.remove();
        });

        // Клик по баннеру
        banner.addEventListener('click', () => {
            showToast(tmpl.toast);
            banner.remove();
        });

        scamOverlay.appendChild(banner);
    }

    function startScamPopups() {
        stopScamPopups();
        spawnScamBanner();
        scamIntervalId = setInterval(spawnScamBanner, 4800);
    }

    function stopScamPopups() {
        if (scamIntervalId) clearInterval(scamIntervalId);
        if (scamOverlay) scamOverlay.innerHTML = '';
    }

    /* ==========================================================================
       16. СИСТЕМНАЯ ВИРТУАЛЬНАЯ КАМЕРА MACOS (WEBSOCKET СТРИМЕР В PYTHON ДЕМОН)
       ========================================================================== */
    const btnVcamToggle = document.getElementById('btn-vcam-toggle');
    const vcamLabel = document.getElementById('vcam-label');
    let isVcamActive = false;
    let vcamSocket = null;
    let vcamIntervalId = null;

    function startVcamStream() {
        if (vcamSocket && vcamSocket.readyState === WebSocket.OPEN) return;

        showToast('Подключение к серверу вирткамеры...');
        try {
            vcamSocket = new WebSocket('ws://localhost:8081/ws');
            vcamSocket.binaryType = 'arraybuffer';

            vcamSocket.onopen = () => {
                isVcamActive = true;
                if (btnVcamToggle) btnVcamToggle.classList.add('active');
                if (vcamLabel) vcamLabel.textContent = 'В эфире';
                showToast('🎥 Вирткамера: поток активен на ws://localhost:8081');

                // Передаём кадры холста с частотой ~30 FPS
                vcamIntervalId = setInterval(() => {
                    if (!vcamSocket || vcamSocket.readyState !== WebSocket.OPEN) return;
                    if (isPaused) return;

                    asciiCanvas.toBlob((blob) => {
                        if (blob && vcamSocket && vcamSocket.readyState === WebSocket.OPEN) {
                            blob.arrayBuffer().then(buf => {
                                if (vcamSocket && vcamSocket.readyState === WebSocket.OPEN) {
                                    vcamSocket.send(buf);
                                }
                            });
                        }
                    }, 'image/jpeg', 0.85);
                }, 33);
            };

            vcamSocket.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    if (data.type === 'status' && data.msg) {
                        showToast(data.msg);
                    }
                } catch (e) {}
            };

            vcamSocket.onclose = () => {
                stopVcamStream(false);
            };

            vcamSocket.onerror = (err) => {
                console.warn('Vcam socket error:', err);
                stopVcamStream(false);
                showToast('⚠️ Сервер вирткамеры не найден. Запустите: python virtual_cam_server.py');
            };
        } catch (e) {
            console.error('Ошибка инициализации вирткамеры:', e);
            stopVcamStream(false);
            showToast('⚠️ Ошибка подключения к вирткамере');
        }
    }

    function stopVcamStream(userInitiated = true) {
        isVcamActive = false;
        if (vcamIntervalId) {
            clearInterval(vcamIntervalId);
            vcamIntervalId = null;
        }
        if (vcamSocket) {
            try { vcamSocket.close(); } catch (e) {}
            vcamSocket = null;
        }
        if (btnVcamToggle) btnVcamToggle.classList.remove('active');
        if (vcamLabel) vcamLabel.textContent = 'Вирткамера';
        if (userInitiated) {
            showToast('🎥 Трансляция в вирткамеру остановлена');
        }
    }

    if (btnVcamToggle) {
        btnVcamToggle.addEventListener('click', () => {
            if (isVcamActive) {
                stopVcamStream(true);
            } else {
                startVcamStream();
            }
        });
    }

    // Обработка параметров URL (?mode=cam или ?stream=clean для чистого захвата в OBS)
    const urlParams = new URLSearchParams(window.location.search);
    if ((urlParams.has('mode') && urlParams.get('mode') === 'cam') || urlParams.has('stream')) {
        document.body.classList.add('cam-mode');
        if (urlParams.has('format') && FORMAT_PRESETS[urlParams.get('format')]) {
            currentFormat = urlParams.get('format');
        } else {
            currentFormat = '16_9';
        }
        if (urlParams.has('mode_color') && MODE_MAP[urlParams.get('mode_color')] !== undefined) {
            currentMode = urlParams.get('mode_color');
        }
        if (urlParams.has('res')) {
            targetCols = Math.max(10, Math.min(360, parseInt(urlParams.get('res'), 10) || 120));
        }
    }

    initCamera();

    // Автоматический запуск стриминга в локальный демон вирткамеры (если открыто в основном окне)
    if (!document.body.classList.contains('cam-mode')) {
        setTimeout(() => {
            if (!isVcamActive) startVcamStream();
        }, 1500);
    }
})();

