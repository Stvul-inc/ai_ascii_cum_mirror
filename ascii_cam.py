import cv2
import numpy as np
import time
import subprocess
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont


class AppleAsciiMirror:
    def __init__(self, camera_index=0):
        self.window_name = "ASCII Mirror Pro"
        self.camera_index = camera_index

        # Символы градации яркости (Apple style typography)
        self.ascii_chars = " .'`^\", :;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZ*#MW&8%B@$"
        self.num_chars = len(self.ascii_chars)

        # Режимы плотности (разрешения) сетки
        self.density_presets = [
            ("Compact", 80, 44),
            ("Balanced", 100, 55),
            ("Ultra", 120, 66),
        ]
        self.density_idx = 1
        self.density_name, self.grid_w, self.grid_h = self.density_presets[self.density_idx]

        # Режимы цветопередачи
        self.color_modes = [
            ("pixel", "TrueColor RGB", (10, 132, 255)),     # Apple Blue
            ("neon", "Cyber Neon", (255, 64, 255)),        # Neon Magenta/Cyan
            ("matrix", "Matrix Terminal", (48, 209, 88)),   # Phosphor Green
            ("silver", "Silver Monochrome", (240, 240, 242)), # White
            ("amber", "Amber Sunset", (255, 159, 10)),      # Apple Orange/Amber
            ("invert", "Negative Invert", (191, 90, 242)),  # Purple
        ]
        self.mode_idx = 0
        self.color_mode, self.color_label, self.color_accent = self.color_modes[self.mode_idx]

        # Настройки шрифта
        self.char_w = 8
        self.char_h = 14
        self.font = ImageFont.load_default()

        # Предварительная растеризация глифов (быстрый кэш)
        self.glyphs = []
        for ch in self.ascii_chars:
            im = Image.new("L", (self.char_w, self.char_h), 0)
            d = ImageDraw.Draw(im)
            d.text((0, 0), ch, fill=255, font=self.font)
            self.glyphs.append(np.array(im) > 80)

        # Параметры интерфейса
        self.header_h = 44
        self.dock_h = 60
        self.is_mirrored = True
        self.is_paused = False
        self.paused_frame = None

        # Вспышка и всплывающие уведомления
        self.flash_start = 0
        self.flash_duration = 0.22
        self.toast_msg = ""
        self.toast_timer = 0

        # Состояние мыши
        self.mouse_x = -1
        self.mouse_y = -1
        self.clicked_button = None
        self.buttons = []
        self.should_quit = False

        self.update_dimensions()

        # Создаем окно
        cv2.namedWindow(self.window_name, cv2.WINDOW_AUTOSIZE)
        cv2.setMouseCallback(self.window_name, self.on_mouse)

        # Выводим минималистичный загрузочный сплэш
        splash = np.full((self.out_h, self.out_w, 3), (18, 18, 20), dtype=np.uint8)
        cv2.putText(splash, "ASCII Mirror Pro", (self.out_w // 2 - 110, self.out_h // 2 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (245, 245, 247), 2, cv2.LINE_AA)
        cv2.putText(splash, "Initializing FaceTime HD Camera...", (self.out_w // 2 - 150, self.out_h // 2 + 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (152, 152, 157), 1, cv2.LINE_AA)
        cv2.imshow(self.window_name, splash)
        cv2.waitKey(1)

        # Подключение камеры через AVFoundation
        self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_AVFOUNDATION)
        if not self.cap.isOpened():
            self.cap = cv2.VideoCapture(1, cv2.CAP_AVFOUNDATION)

        self.fps = 60.0
        self.last_time = time.time()
        self.last_ascii_text = ""

    def update_dimensions(self):
        self.video_w = self.grid_w * self.char_w
        self.video_h = self.grid_h * self.char_h
        self.out_w = self.video_w
        self.out_h = self.video_h + self.header_h + self.dock_h
        self.layout_dock_buttons()

    def layout_dock_buttons(self):
        btn_defs = [
            ("mode", "🎨 Mode", 110),
            ("density", "🔲 Density", 110),
            ("snap", "📸 Snap", 100),
            ("copy", "📋 Copy", 100),
            ("pause", "⏸ Pause", 100),
            ("flip", "🔄 Mirror", 100),
            ("quit", "✕ Quit", 90),
        ]
        total_btn_w = sum(b[2] for b in btn_defs)
        spacing = 10
        total_w = total_btn_w + spacing * (len(btn_defs) - 1)
        start_x = max(15, (self.out_w - total_w) // 2)

        cur_x = start_x
        y1 = self.header_h + self.video_h + 10
        y2 = y1 + 38

        self.buttons = []
        for key, title, width in btn_defs:
            self.buttons.append({
                "id": key,
                "title": title,
                "rect": (cur_x, y1, cur_x + width, y2)
            })
            cur_x += width + spacing

    def on_mouse(self, event, x, y, flags, param):
        self.mouse_x = x
        self.mouse_y = y
        if event == cv2.EVENT_LBUTTONDOWN:
            for btn in self.buttons:
                x1, y1, x2, y2 = btn["rect"]
                if x1 <= x <= x2 and y1 <= y <= y2:
                    self.handle_action(btn["id"])
                    break

    def handle_action(self, action_id):
        if action_id == "mode":
            self.mode_idx = (self.mode_idx + 1) % len(self.color_modes)
            self.color_mode, self.color_label, self.color_accent = self.color_modes[self.mode_idx]
            self.show_toast(f"Mode: {self.color_label}")
        elif action_id == "density":
            self.density_idx = (self.density_idx + 1) % len(self.density_presets)
            self.density_name, self.grid_w, self.grid_h = self.density_presets[self.density_idx]
            self.update_dimensions()
            self.show_toast(f"Density: {self.density_name} ({self.grid_w}x{self.grid_h})")
        elif action_id == "snap":
            self.save_snapshot()
        elif action_id == "copy":
            self.copy_ascii_to_clipboard()
        elif action_id == "pause":
            self.is_paused = not self.is_paused
            self.show_toast("Video PAUSED" if self.is_paused else "Video RESUMED")
        elif action_id == "flip":
            self.is_mirrored = not self.is_mirrored
            self.show_toast("Mirror: ON" if self.is_mirrored else "Mirror: OFF")
        elif action_id == "quit":
            self.should_quit = True

    def show_toast(self, text):
        self.toast_msg = text
        self.toast_timer = time.time()

    def copy_ascii_to_clipboard(self):
        if not self.last_ascii_text:
            return
        try:
            p = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE)
            p.communicate(self.last_ascii_text.encode('utf-8'))
            self.show_toast("✓ ASCII Art Copied to Clipboard!")
        except Exception as e:
            self.show_toast(f"Copy error: {e}")

    def save_snapshot(self):
        if self.current_canvas is not None:
            # Обрезаем только ASCII-вьюпорт
            view = self.current_canvas[self.header_h:self.header_h + self.video_h, :self.video_w]
            filename = f"ascii_shot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            cv2.imwrite(filename, view)
            self.flash_start = time.time()  # Вспышка затвора
            self.show_toast(f"✓ Saved: {filename}")

    def process_ascii(self, frame):
        if self.is_mirrored:
            frame = cv2.flip(frame, 1)

        # Центрирование квадрата
        h, w = frame.shape[:2]
        size = min(h, w)
        sx = (w - size) // 2
        sy = (h - size) // 2
        square = frame[sy:sy + size, sx:sx + size]

        # Размытие и сжатие
        blurred = cv2.GaussianBlur(square, (3, 3), 0)
        resized_bgr = cv2.resize(blurred, (self.grid_w, self.grid_h))
        gray = cv2.cvtColor(resized_bgr, cv2.COLOR_BGR2GRAY)

        # Гамма-коррекция яркости
        norm = gray.astype(np.float32) / 255.0
        adjusted = np.sqrt(norm)
        indices = np.clip((adjusted * (self.num_chars - 1)).astype(np.int32), 0, self.num_chars - 1)

        # Формирование текстового ASCII для буфера обмена
        lines = []
        for i in range(self.grid_h):
            row_chars = [self.ascii_chars[indices[i, j]] for j in range(self.grid_w)]
            lines.append("".join(row_chars))
        self.last_ascii_text = "\n".join(lines)

        # Выбор цветовой палитры
        if self.color_mode == "pixel":
            colors = resized_bgr
        elif self.color_mode == "white":
            colors = np.full((self.grid_h, self.grid_w, 3), (240, 240, 242), dtype=np.uint8)
        elif self.color_mode == "matrix":
            colors = np.full((self.grid_h, self.grid_w, 3), (48, 209, 88), dtype=np.uint8)
        elif self.color_mode == "amber":
            colors = np.full((self.grid_h, self.grid_w, 3), (10, 159, 255), dtype=np.uint8)
        elif self.color_mode == "neon":
            # Неоновый динамический перелив
            t = time.time() * 2
            b = np.uint8((np.sin(t) + 1) * 127)
            r = np.uint8((np.cos(t) + 1) * 127)
            colors = np.full((self.grid_h, self.grid_w, 3), (b, 240, r), dtype=np.uint8)
        elif self.color_mode == "invert":
            # Инвертированные цвета
            colors = 255 - resized_bgr
        else:
            colors = resized_bgr

        # Отрисовка в холст
        ascii_canvas = np.full((self.video_h, self.video_w, 3), (10, 10, 12), dtype=np.uint8)
        for i in range(self.grid_h):
            y = i * self.char_h
            for j in range(self.grid_w):
                x = j * self.char_w
                mask = self.glyphs[indices[i, j]]
                ascii_canvas[y:y + self.char_h, x:x + self.char_w][mask] = colors[i, j]

        return ascii_canvas

    def draw_apple_ui(self, canvas, ascii_viewport):
        # 1. Вставка вьюпорта
        canvas[self.header_h:self.header_h + self.video_h, :self.video_w] = ascii_viewport

        # 2. Верхний статус-бар (macOS Header)
        cv2.rectangle(canvas, (0, 0), (self.out_w, self.header_h), (22, 22, 24), -1)
        cv2.line(canvas, (0, self.header_h - 1), (self.out_w, self.header_h - 1), (44, 44, 46), 1)

        # Зеленая пульсирующая точка LIVE
        dot_color = (48, 209, 88) if (not self.is_paused) else (142, 142, 147)
        cv2.circle(canvas, (24, self.header_h // 2), 5, dot_color, -1, cv2.LINE_AA)
        live_label = "LIVE" if (not self.is_paused) else "PAUSED"
        cv2.putText(canvas, live_label, (36, self.header_h // 2 + 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, dot_color, 1, cv2.LINE_AA)

        cv2.putText(canvas, "|", (90, self.header_h // 2 + 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (60, 60, 64), 1, cv2.LINE_AA)

        # Название приложения
        cv2.putText(canvas, "ASCII Mirror Pro", (105, self.header_h // 2 + 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (245, 245, 247), 1, cv2.LINE_AA)

        # Центральная плашка: текущий режим
        mode_pill = f"  {self.color_label}  "
        (tw, th), _ = cv2.getTextSize(mode_pill, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
        px1 = (self.out_w - tw) // 2 - 8
        px2 = px1 + tw + 16
        py1 = 8
        py2 = self.header_h - 8
        cv2.rectangle(canvas, (px1, py1), (px2, py2), (36, 36, 38), -1)
        cv2.rectangle(canvas, (px1, py1), (px2, py2), (60, 60, 64), 1)
        cv2.putText(canvas, mode_pill, (px1 + 4, self.header_h // 2 + 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, self.color_accent, 1, cv2.LINE_AA)

        # Правая сторона: FPS и сетка
        meta_info = f"{self.density_name}  {self.fps:.0f} FPS"
        cv2.putText(canvas, meta_info, (self.out_w - 140, self.header_h // 2 + 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (142, 142, 147), 1, cv2.LINE_AA)

        # 3. Нижний плавающий Dock (macOS Floating Pill Dock)
        cv2.rectangle(canvas, (0, self.header_h + self.video_h), (self.out_w, self.out_h), (22, 22, 24), -1)
        cv2.line(canvas, (0, self.header_h + self.video_h), (self.out_w, self.header_h + self.video_h), (44, 44, 46), 1)

        # Рисуем стильные кнопки дока
        for btn in self.buttons:
            x1, y1, x2, y2 = btn["rect"]
            is_hover = (x1 <= self.mouse_x <= x2 and y1 <= self.mouse_y <= y2)

            # Цвет заливки кнопки (Apple Dark UI)
            if is_hover:
                bg_color = (58, 58, 60)
                border_color = (120, 120, 128)
            else:
                bg_color = (36, 36, 38)
                border_color = (58, 58, 60)

            # Выделение паузы или выхода
            if btn["id"] == "pause" and self.is_paused:
                bg_color = (30, 80, 150)
                border_color = (10, 132, 255)
            elif btn["id"] == "quit" and is_hover:
                bg_color = (40, 40, 110)
                border_color = (80, 80, 200)

            # Кнопка с мягким скруглением
            cv2.rectangle(canvas, (x1, y1), (x2, y2), bg_color, -1)
            cv2.rectangle(canvas, (x1, y1), (x2, y2), border_color, 1)

            # Текст кнопки
            title = btn["title"]
            (tw, th), _ = cv2.getTextSize(title, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
            tx = x1 + (x2 - x1 - tw) // 2
            ty = y1 + (y2 - y1 + th) // 2
            text_color = (255, 255, 255) if is_hover else (220, 220, 225)
            cv2.putText(canvas, title, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.45, text_color, 1, cv2.LINE_AA)

        # 4. Всплывающее уведомление (Apple Toast Banner)
        if time.time() - self.toast_timer < 2.0:
            toast_text = f"  {self.toast_msg}  "
            (tw, th), _ = cv2.getTextSize(toast_text, cv2.FONT_HERSHEY_SIMPLEX, 0.52, 1)
            tx1 = (self.out_w - tw) // 2 - 12
            tx2 = tx1 + tw + 24
            ty1 = self.header_h + 12
            ty2 = ty1 + 34
            cv2.rectangle(canvas, (tx1, ty1), (tx2, ty2), (30, 30, 32), -1)
            cv2.rectangle(canvas, (tx1, ty1), (tx2, ty2), (80, 80, 88), 1)
            cv2.putText(canvas, toast_text, (tx1 + 10, ty1 + 22),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (48, 209, 88), 1, cv2.LINE_AA)

        # 5. Эффект вспышки затвора камеры Apple (White Flash)
        dt_flash = time.time() - self.flash_start
        if dt_flash < self.flash_duration:
            alpha = 1.0 - (dt_flash / self.flash_duration)
            viewport_rect = canvas[self.header_h:self.header_h + self.video_h, :self.video_w]
            white = np.full_like(viewport_rect, 255)
            cv2.addWeighted(white, alpha * 0.7, viewport_rect, 1.0 - (alpha * 0.7), 0, viewport_rect)

    def run(self):
        self.current_canvas = None

        while not self.should_quit:
            # Получение кадра
            if not self.is_paused or self.paused_frame is None:
                ret, frame = self.cap.read()
                if ret:
                    self.paused_frame = frame
                else:
                    time.sleep(0.01)
                    continue
            else:
                frame = self.paused_frame

            # FPS
            now = time.time()
            dt = now - self.last_time
            if dt > 0:
                self.fps = 0.9 * self.fps + 0.1 * (1.0 / dt)
            self.last_time = now

            # Обработка ASCII
            ascii_viewport = self.process_ascii(frame)

            # Отрисовка Apple UI
            canvas = np.full((self.out_h, self.out_w, 3), (18, 18, 20), dtype=np.uint8)
            self.draw_apple_ui(canvas, ascii_viewport)
            self.current_canvas = canvas

            cv2.imshow(self.window_name, canvas)

            # Горячие клавиши (RU / EN)
            key = cv2.waitKey(1)
            if key != -1:
                k_code = key & 0xFFFF
                k_char = chr(k_code) if (0 < k_code < 65536) else ""

                if k_code in (27, ord('q'), ord('Q'), 1081, 1049) or k_char in ('q', 'Q', 'й', 'Й'):
                    break
                elif k_code in (32, 10, 13, ord('c'), ord('C'), 1089, 1057) or k_char in ('c', 'C', 'с', 'С', ' '):
                    self.handle_action("mode")
                elif k_code in (ord('s'), ord('S'), 1099, 1067) or k_char in ('s', 'S', 'ы', 'Ы'):
                    self.handle_action("snap")
                elif k_code in (ord('d'), ord('D'), 1074, 1042) or k_char in ('d', 'D', 'в', 'В'):
                    self.handle_action("density")
                elif k_code in (ord('p'), ord('P'), 1079, 1047) or k_char in ('p', 'P', 'з', 'З'):
                    self.handle_action("pause")
                elif k_code in (ord('m'), ord('M'), 1100, 1068) or k_char in ('m', 'M', 'ь', 'Ь'):
                    self.handle_action("flip")
                elif k_code in (ord('y'), ord('Y'), 1085, 1053) or k_char in ('y', 'Y', 'н', 'Н'):
                    self.handle_action("copy")

        self.cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    mirror = AppleAsciiMirror()
    mirror.run()
