import cv2
import numpy as np
import time
import os
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

class NativeAsciiMirror:
    def __init__(self, camera_index=0, width=120, height_ratio=0.55):
        self.window_name = "Perfect ASCII Mirror"
        self.camera_index = camera_index
        self.grid_w = width
        self.grid_h = int(width * height_ratio)

        # Символы градации яркости (от темного к светлому)
        self.ascii_chars = " .'`^\", :;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZ*#MW&8%B@$"
        self.num_chars = len(self.ascii_chars)

        # Режимы цвета
        self.modes = ["pixel", "neon", "matrix", "white"]
        self.mode_names = {
            "pixel": "Цветные пиксели (RGB)",
            "neon": "Неон",
            "matrix": "Матрица (Зеленый)",
            "white": "Монохром (Белый)"
        }
        self.color_mode = "pixel"
        self.neon_colors = [
            (255, 0, 255),  # Magenta
            (255, 255, 0),  # Cyan
            (0, 255, 255),  # Yellow
        ]

        # Подготовка шрифта и растрового атласа глифов
        self.char_w = 8
        self.char_h = 14
        self.font = ImageFont.load_default()

        self.glyphs = []
        for ch in self.ascii_chars:
            im = Image.new("L", (self.char_w, self.char_h), 0)
            d = ImageDraw.Draw(im)
            d.text((0, 0), ch, fill=255, font=self.font)
            self.glyphs.append(np.array(im) > 80)

        # Размеры видеосетки и панели кнопок
        self.video_w = self.grid_w * self.char_w
        self.video_h = self.grid_h * self.char_h
        self.toolbar_h = 50
        self.out_w = self.video_w
        self.out_h = self.video_h + self.toolbar_h

        # Интерактивные кнопки внизу экрана (x1, y1, x2, y2)
        btn_y1 = self.video_h + 8
        btn_y2 = self.out_h - 8
        self.buttons = {
            "color": (20, btn_y1, 260, btn_y2),
            "save": (280, btn_y1, 460, btn_y2),
            "quit": (self.out_w - 140, btn_y1, self.out_w - 20, btn_y2),
        }

        # Создаем обычное окно БЕЗ TOPMOST (не поверх всех окон)
        cv2.namedWindow(self.window_name, cv2.WINDOW_AUTOSIZE)

        # Первичная заставка
        splash = np.zeros((self.out_h, self.out_w, 3), dtype=np.uint8)
        cv2.putText(splash, "Starting Camera...", (self.out_w // 2 - 120, self.out_h // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        cv2.imshow(self.window_name, splash)
        cv2.waitKey(1)

        # Подключаем мышь для кликабельных кнопок
        cv2.setMouseCallback(self.window_name, self.on_mouse)

        # Инициализация камеры AVFoundation
        self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_AVFOUNDATION)
        if not self.cap.isOpened():
            self.cap = cv2.VideoCapture(1, cv2.CAP_AVFOUNDATION)

        self.fps = 0
        self.last_time = time.time()
        self.save_feedback_timer = 0
        self.should_quit = False

    def toggle_color_mode(self):
        cur_idx = self.modes.index(self.color_mode) if self.color_mode in self.modes else 0
        self.color_mode = self.modes[(cur_idx + 1) % len(self.modes)]
        print(f"[РЕЖИМ] Переключено на: {self.mode_names[self.color_mode]}")

    def on_mouse(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            for btn_name, (bx1, by1, bx2, by2) in self.buttons.items():
                if bx1 <= x <= bx2 and by1 <= y <= by2:
                    if btn_name == "color":
                        self.toggle_color_mode()
                    elif btn_name == "save":
                        self.save_snapshot_flag = True
                    elif btn_name == "quit":
                        self.should_quit = True

    def process_frame(self, frame):
        # Зеркальное отображение
        frame = cv2.flip(frame, 1)

        # Центрирование кадра
        h, w = frame.shape[:2]
        size = min(h, w)
        sx = (w - size) // 2
        sy = (h - size) // 2
        square = frame[sy:sy + size, sx:sx + size]

        # Размытие и сжатие
        blurred = cv2.GaussianBlur(square, (3, 3), 0)
        resized_bgr = cv2.resize(blurred, (self.grid_w, self.grid_h))
        gray = cv2.cvtColor(resized_bgr, cv2.COLOR_BGR2GRAY)

        # Вычисление индекса символа
        norm = gray.astype(np.float32) / 255.0
        adjusted = np.sqrt(norm)
        indices = np.clip((adjusted * (self.num_chars - 1)).astype(np.int32), 0, self.num_chars - 1)

        # Цвета
        if self.color_mode == "pixel":
            colors = resized_bgr
        elif self.color_mode == "white":
            colors = np.full((self.grid_h, self.grid_w, 3), (255, 255, 255), dtype=np.uint8)
        elif self.color_mode == "matrix":
            colors = np.full((self.grid_h, self.grid_w, 3), (0, 255, 70), dtype=np.uint8)
        elif self.color_mode == "neon":
            c = self.neon_colors[int(time.time() * 3) % len(self.neon_colors)]
            colors = np.full((self.grid_h, self.grid_w, 3), c, dtype=np.uint8)
        else:
            colors = resized_bgr

        # Быстрый векторный рендеринг глифов
        canvas = np.zeros((self.out_h, self.out_w, 3), dtype=np.uint8)
        for i in range(self.grid_h):
            y = i * self.char_h
            for j in range(self.grid_w):
                x = j * self.char_w
                glyph_mask = self.glyphs[indices[i, j]]
                canvas[y:y + self.char_h, x:x + self.char_w][glyph_mask] = colors[i, j]

        return canvas

    def draw_toolbar(self, canvas):
        # Фоновая панель инструментов
        cv2.rectangle(canvas, (0, self.video_h), (self.out_w, self.out_h), (25, 25, 25), -1)
        cv2.line(canvas, (0, self.video_h), (self.out_w, self.video_h), (60, 60, 60), 1)

        # Кнопка 1: Цвет/Режим
        bx1, by1, bx2, by2 = self.buttons["color"]
        cv2.rectangle(canvas, (bx1, by1), (bx2, by2), (55, 55, 55), -1)
        cv2.rectangle(canvas, (bx1, by1), (bx2, by2), (120, 120, 120), 1)
        cv2.putText(canvas, f"Mode: {self.color_mode.upper()} [C]", (bx1 + 10, by1 + 23),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

        # Кнопка 2: Сохранить
        bx1, by1, bx2, by2 = self.buttons["save"]
        cv2.rectangle(canvas, (bx1, by1), (bx2, by2), (55, 55, 55), -1)
        cv2.rectangle(canvas, (bx1, by1), (bx2, by2), (120, 120, 120), 1)
        save_label = "SAVED! OK" if (time.time() - self.save_feedback_timer < 1.5) else "SAVE PHOTO [S]"
        save_color = (0, 255, 0) if (time.time() - self.save_feedback_timer < 1.5) else (255, 255, 255)
        cv2.putText(canvas, save_label, (bx1 + 10, by1 + 23),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, save_color, 1)

        # Кнопка 3: Закрыть
        bx1, by1, bx2, by2 = self.buttons["quit"]
        cv2.rectangle(canvas, (bx1, by1), (bx2, by2), (40, 40, 90), -1)
        cv2.rectangle(canvas, (bx1, by1), (bx2, by2), (100, 100, 180), 1)
        cv2.putText(canvas, "QUIT [Q]", (bx1 + 20, by1 + 23),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 255), 1)

        # FPS
        cv2.putText(canvas, f"FPS: {self.fps:.1f}", (self.out_w // 2 - 30, by1 + 23),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (160, 160, 160), 1)

    def save_snapshot(self, canvas):
        crop = canvas[:self.video_h, :self.video_w]
        filename = f"ascii_snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        cv2.imwrite(filename, crop)
        self.save_feedback_timer = time.time()
        print(f"[УСПЕХ] Снимок сохранён: {filename}")

    def run(self):
        self.save_snapshot_flag = False
        print("[INFO] Окно запущено. Кнопки кликабельны мышью. Клавиши: Пробел/C, S, Q.")

        while not self.should_quit:
            ret, frame = self.cap.read()
            if not ret:
                time.sleep(0.01)
                continue

            now = time.time()
            dt = now - self.last_time
            if dt > 0:
                self.fps = 0.9 * self.fps + 0.1 * (1.0 / dt) if self.fps > 0 else 1.0 / dt
            self.last_time = now

            canvas = self.process_frame(frame)
            self.draw_toolbar(canvas)

            if self.save_snapshot_flag:
                self.save_snapshot(canvas)
                self.save_snapshot_flag = False

            cv2.imshow(self.window_name, canvas)

            # Чтение клавиш (с поддержкой русской раскладки, латиницы и пробела)
            key = cv2.waitKey(1)
            if key != -1:
                k_code = key & 0xFFFF
                k_char = chr(k_code) if (0 < k_code < 65536) else ""

                # Выход: Q, q, й, Й, Esc (27)
                if k_code in (27, ord('q'), ord('Q'), 1081, 1049) or k_char in ('q', 'Q', 'й', 'Й'):
                    break
                # Переключение цвета: C, c, с, С (русская эс), Пробел (32), Enter (10, 13)
                elif k_code in (32, 10, 13, ord('c'), ord('C'), 1089, 1057) or k_char in ('c', 'C', 'с', 'С', ' '):
                    self.toggle_color_mode()
                # Сохранить: S, s, ы, Ы
                elif k_code in (ord('s'), ord('S'), 1099, 1067) or k_char in ('s', 'S', 'ы', 'Ы'):
                    self.save_snapshot(canvas)

        self.cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    mirror = NativeAsciiMirror()
    mirror.run()
