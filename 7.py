#reserve 7
import cv2
import numpy as np
import tkinter as tk
from tkinter import font as tkfont, colorchooser, filedialog, Menu, messagebox
import json
import os
from datetime import datetime
import time
from PIL import Image, ImageDraw, ImageFont
import threading
import sys


class SyntheticCapture:
    def __init__(self):
        self.t = 0
        self.w, self.h = 320, 240

    def isOpened(self):
        return True

    def read(self):
        self.t += 0.08
        x = np.linspace(0, 4 * np.pi, self.w)
        y = np.linspace(0, 4 * np.pi, self.h)
        xx, yy = np.meshgrid(x, y)
        r = np.uint8((np.sin(xx + self.t) + 1) * 127.5)
        g = np.uint8((np.cos(yy + self.t) + 1) * 127.5)
        b = np.uint8((np.sin(xx + yy + self.t) + 1) * 127.5)
        frame = np.stack([b, g, r], axis=-1)
        cx = int(self.w / 2 + 60 * np.cos(self.t))
        cy = int(self.h / 2 + 40 * np.sin(self.t))
        cv2.circle(frame, (cx, cy), 30, (255, 255, 255), -1)
        return True, frame

    def release(self):
        pass


class PerfectAsciiMirror:
    def __init__(self, root):
        self.root = root
        self.root.title("пиздец")

        # Центрируем окно на экране
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        self.window_size = 600
        x = (screen_width - self.window_size) // 2
        y = (screen_height - self.window_size) // 2
        self.root.geometry(f"{self.window_size}x{self.window_size}+{x}+{y}")
        self.root.resizable(False, False)

        # Расширенный набор символов для лучшей градации
        self.ascii_chars = " .'`^\", :;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZ*#MW&8%B@$"
        self.ascii_chars = self.ascii_chars[::-1]  # Инвертируем градиент

        # Размер ASCII-арта (квадрат N×N символов)
        self.ascii_size = 120
        self.vertical_compression = 0.55  # Коэффициент сжатия по вертикали
        self.font_size = 7
        self.font_family = "Courier"

        # Настройки по умолчанию
        self.settings = {
            "text_color": "white",
            "bg_color": "black",
            "color_mode": "monochrome",  # monochrome, red, green, blue, neon, pixel
            "pixel_color": False,
            "vertical_compression": self.vertical_compression,
            "font_size": self.font_size,
            "font_family": self.font_family
        }

        # Загрузка сохраненных настроек
        self.load_settings()
        self.vertical_compression = self.settings.get("vertical_compression", 0.55)
        self.font_size = self.settings.get("font_size", 7)
        self.font_family = self.settings.get("font_family", "Courier")

        # Создаем моноширинный шрифт с квадратными символами
        self.custom_font = tkfont.Font(
            family=self.font_family,
            size=self.font_size,
            weight="bold"
        )

        # Создаем текстовое поле
        self.text_widget = tk.Text(
            root,
            font=self.custom_font,
            bg=self.settings["bg_color"],
            fg=self.settings["text_color"],
            insertontime=0,
            borderwidth=0,
            highlightthickness=0,
            width=self.ascii_size,
            height=int(self.ascii_size * self.vertical_compression)  # Сохраняем ваши пропорции
        )
        self.text_widget.pack(expand=True, padx=20, pady=20)

        # Создаем метку для отображения FPS
        self.fps_label = tk.Label(root, text="FPS: --", bg="black", fg="white")
        self.fps_label.pack(side=tk.BOTTOM, fill=tk.X)

        # Создаем меню
        self.create_menu()

        # Настройка видеозахвата
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            self.cap = SyntheticCapture()

        # Переменные для обработки кадра
        self.current_frame = None
        self.current_ascii = ""
        self.current_colors = []
        self.configured_color_tags = set()
        self.frame_queue = []
        self.processing_thread = None
        self.stop_thread = False
        self.frame_count = 0
        self.fps = 0
        self.start_time = time.time()
        self.last_fps_update = time.time()
        self.last_frame_time = time.time()

        # Начало обработки видео
        self.update_frame()

        # Запускаем поток для обработки кадров
        self.start_processing_thread()

    def start_processing_thread(self):
        self.stop_thread = False
        self.processing_thread = threading.Thread(target=self.process_frame_thread, daemon=True)
        self.processing_thread.start()

    def process_frame_thread(self):
        while not self.stop_thread:
            if self.frame_queue:
                frame = self.frame_queue.pop(0)
                try:
                    # Обработка кадра
                    if self.settings["color_mode"] == "pixel":
                        # Для цветного режима сохраняем цветное изображение
                        ascii_art, colors = self.process_frame(frame, is_color=True)
                    else:
                        # Для других режимов используем ч/б
                        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                        ascii_art, colors = self.process_frame(gray)

                    # Сохраняем результаты для основного потока
                    self.current_frame = frame
                    self.current_ascii = ascii_art
                    self.current_colors = colors
                except Exception as e:
                    print(f"Ошибка обработки кадра в потоке: {e}")
            else:
                time.sleep(0.01)  # Небольшая пауза, если очередь пуста

    def create_menu(self):
        """Создаем меню приложения"""
        menubar = Menu(self.root)

        # Меню цвета
        color_menu = Menu(menubar, tearoff=0)
        color_menu.add_command(label="Белый", command=lambda: self.set_color("white"))
        color_menu.add_command(label="Красный", command=lambda: self.set_color("red"))
        color_menu.add_command(label="Зеленый", command=lambda: self.set_color("green"))
        color_menu.add_command(label="Синий", command=lambda: self.set_color("blue"))
        color_menu.add_command(label="Неоновый", command=lambda: self.set_color("neon"))
        color_menu.add_command(label="Цвет пикселя", command=lambda: self.set_color("pixel"))
        color_menu.add_command(label="Выбрать цвет...", command=self.choose_custom_color)

        # Подменю компрессии
        compression_menu = Menu(menubar, tearoff=0)
        compression_menu.add_command(label="Низкая (0.7)", command=lambda: self.set_compression(0.7))
        compression_menu.add_command(label="Средняя (0.55)", command=lambda: self.set_compression(0.55))
        compression_menu.add_command(label="Высокая (0.4)", command=lambda: self.set_compression(0.4))
        color_menu.add_cascade(label="Компрессия", menu=compression_menu)

        # Подменю шрифта
        font_menu = Menu(menubar, tearoff=0)
        font_menu.add_command(label="Увеличить шрифт", command=lambda: self.set_font_size(self.font_size + 1))
        font_menu.add_command(label="Уменьшить шрифт", command=lambda: self.set_font_size(self.font_size - 1))
        font_menu.add_command(label="Courier", command=lambda: self.set_font_family("Courier"))
        font_menu.add_command(label="Consolas", command=lambda: self.set_font_family("Consolas"))
        font_menu.add_command(label="Monospace", command=lambda: self.set_font_family("Monospace"))
        color_menu.add_cascade(label="Шрифт", menu=font_menu)

        menubar.add_cascade(label="Цвет", menu=color_menu)

        # Меню фона
        bg_menu = Menu(menubar, tearoff=0)
        bg_menu.add_command(label="Черный", command=lambda: self.set_bg_color("black"))
        bg_menu.add_command(label="Белый", command=lambda: self.set_bg_color("white"))
        bg_menu.add_command(label="Выбрать цвет...", command=self.choose_custom_bg_color)
        menubar.add_cascade(label="Фон", menu=bg_menu)

        # Меню фото
        photo_menu = Menu(menubar, tearoff=0)
        photo_menu.add_command(label="Сделать снимок (текст)", command=self.save_photo)
        photo_menu.add_command(label="Сохранить фото ASCII", command=self.save_ascii_photo)
        menubar.add_cascade(label="Фото", menu=photo_menu)

        self.root.config(menu=menubar)

    def set_font_family(self, family):
        """Устанавливает семейство шрифтов"""
        self.font_family = family
        self.settings["font_family"] = family
        self.custom_font.configure(family=family)
        self.save_settings()

    def set_font_size(self, size):
        """Устанавливает размер шрифта"""
        if 5 <= size <= 20:  # Ограничиваем размер шрифта
            self.font_size = size
            self.settings["font_size"] = size
            self.custom_font.configure(size=size)
            self.save_settings()

    def set_compression(self, value):
        """Устанавливает коэффициент вертикального сжатия"""
        self.vertical_compression = value
        self.settings["vertical_compression"] = value
        self.text_widget.config(height=int(self.ascii_size * value))
        self.save_settings()

    def set_color(self, color):
        """Устанавливает цвет текста"""
        self.settings["color_mode"] = color
        if color != "neon" and color != "pixel":
            self.text_widget.config(fg=color)
            self.settings["text_color"] = color
        self.save_settings()

    def set_bg_color(self, color):
        """Устанавливает цвет фона"""
        self.settings["bg_color"] = color
        self.text_widget.config(bg=color)
        self.fps_label.config(bg=color)
        self.save_settings()

    def choose_custom_color(self):
        """Позволяет пользователю выбрать произвольный цвет"""
        color = colorchooser.askcolor(title="Выберите цвет текста")
        if color[1]:
            self.settings["text_color"] = color[1]
            self.settings["color_mode"] = "custom"
            self.text_widget.config(fg=color[1])
            self.save_settings()

    def choose_custom_bg_color(self):
        """Позволяет пользователю выбрать произвольный цвет фона"""
        color = colorchooser.askcolor(title="Выберите цвет фона")
        if color[1]:
            self.settings["bg_color"] = color[1]
            self.text_widget.config(bg=color[1])
            self.fps_label.config(bg=color[1])
            self.save_settings()

    def save_photo(self):
        """Сохраняет текущий ASCII-арт в текстовый файл"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")],
            initialfile=f"ascii_photo_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        if filename:
            with open(filename, "w") as f:
                f.write(self.text_widget.get("1.0", tk.END))

    def save_ascii_photo(self):
        """Сохраняет ASCII-арт как изображение (с цветами, если есть)"""
        if self.current_ascii is None or not self.current_ascii:
            messagebox.showerror("Ошибка", "Нет данных для сохранения")
            return

        filename = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG файлы", "*.png"), ("JPEG файлы", "*.jpg"), ("Все файлы", "*.*")],
            initialfile=f"ascii_image_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        if not filename:
            return

        # Добавляем расширение, если его нет
        if not filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            filename += ".png"

        try:
            # Определяем размер изображения на основе количества символов
            char_width = 10
            char_height = 15
            width = self.ascii_size * char_width
            height = int(self.ascii_size * self.vertical_compression) * char_height

            # Создаем изображение для рисования
            img = Image.new("RGB", (width, height), self.settings["bg_color"])
            draw = ImageDraw.Draw(img)

            # Используем моноширинный шрифт
            try:
                font = ImageFont.truetype("cour.ttf", 12)  # Попробуем стандартный шрифт
            except:
                try:
                    font = ImageFont.truetype("courbd.ttf", 12)  # Попробуем жирный
                except:
                    font = ImageFont.load_default()  # Запасной вариант

            # Разбиваем ASCII-арт на строки
            lines = self.current_ascii.strip().split("\n")

            # Убедимся, что у нас достаточно строк
            if len(lines) < self.ascii_size:
                lines += [""] * (self.ascii_size - len(lines))

            # Рисуем символы с цветами
            for y in range(min(len(lines), int(self.ascii_size * self.vertical_compression))):
                line = lines[y]
                for x in range(min(len(line), self.ascii_size)):
                    char = line[x] if x < len(line) else " "

                    # Получаем цвет пикселя
                    if (self.settings["color_mode"] == "pixel" and
                            self.current_colors and
                            y < len(self.current_colors) and
                            x < len(self.current_colors[y])):

                        color = self.current_colors[y][x]
                    else:
                        color = self.settings["text_color"]

                    # Рисуем символ
                    try:
                        draw.text((x * char_width, y * char_height), char, fill=color, font=font)
                    except:
                        # Если не удалось нарисовать с выбранным цветом, используем белый
                        draw.text((x * char_width, y * char_height), char, fill="white", font=font)

            # Сохраняем изображение
            img.save(filename)
            messagebox.showinfo("Успех", f"Изображение сохранено:\n{filename}")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить изображение:\n{str(e)}")

    def save_settings(self):
        """Сохраняет настройки в файл"""
        with open("ascii_mirror_settings.json", "w") as f:
            json.dump(self.settings, f)

    def load_settings(self):
        """Загружает настройки из файла"""
        try:
            if os.path.exists("ascii_mirror_settings.json"):
                with open("ascii_mirror_settings.json", "r") as f:
                    loaded_settings = json.load(f)
                    # Применяем только существующие настройки
                    for key in self.settings:
                        if key in loaded_settings:
                            self.settings[key] = loaded_settings[key]
        except Exception as e:
            print(f"Ошибка загрузки настроек: {e}")

    def process_frame(self, frame, is_color=False):
        """Обработка кадра с идеально квадратным отображением"""
        # Зеркальное отражение
        frame = cv2.flip(frame, 1)

        # Создаем квадратный кадр (центрированный)
        h, w = frame.shape[:2]
        size = min(h, w)
        start_x = (w - size) // 2
        start_y = (h - size) // 2
        square_frame = frame[start_y:start_y + size, start_x:start_x + size]

        # Применяем вертикальное сжатие
        new_width = self.ascii_size
        new_height = int(self.ascii_size * self.vertical_compression)

        # Уменьшаем шум с помощью размытия
        blurred = cv2.GaussianBlur(square_frame, (3, 3), 0)

        resized = cv2.resize(blurred, (new_width, new_height))

        # Конвертация в ASCII с улучшенной передачей градаций
        ascii_art = ""
        num_chars = len(self.ascii_chars)
        colors = []  # Матрица цветов для каждого символа

        if is_color:
            # Для цветного режима: получаем цвета из цветного изображения
            resized_color = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
            # Конвертируем в серое для ASCII
            gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        else:
            # Для других режимов: работаем с серым изображением
            gray = resized
            # Если изображение цветное, конвертируем для получения цветов
            if len(resized.shape) == 3:
                resized_color = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
            else:
                # Создаем псевдо-цветное изображение (все пиксели белые)
                resized_color = np.stack((gray, gray, gray), axis=-1)

        # Для каждой строки в обработанном изображении
        for i in range(new_height):
            ascii_line = ""
            color_row = []
            for j in range(new_width):
                # Получаем яркость пикселя
                pixel = gray[i, j]
                normalized = pixel / 255.0
                adjusted = normalized ** 0.5
                index = min(int(adjusted * (num_chars - 1)), num_chars - 1)
                char = self.ascii_chars[index]
                ascii_line += char

                # Получаем цвет пикселя
                if len(resized_color.shape) == 3:  # Если изображение цветное
                    r, g, b = resized_color[i, j]
                else:  # Если серое
                    r = g = b = resized_color[i, j]

                # Квантизация для высокой производительности и плавной группировки тегов
                r, g, b = int(r), int(g), int(b)
                qr = (r >> 3) << 3
                qg = (g >> 3) << 3
                qb = (b >> 3) << 3
                hex_color = f"#{qr:02x}{qg:02x}{qb:02x}"
                color_row.append(hex_color)

            ascii_art += ascii_line + "\n"
            colors.append(color_row)

        return ascii_art, colors

    def update_frame(self):
        """Обновление кадра с отображением FPS"""
        try:
            current_time = time.time()

            # Рассчет FPS
            elapsed_since_last = current_time - self.last_frame_time
            if elapsed_since_last > 0:
                current_fps = 1.0 / elapsed_since_last
                # Экспоненциальное скользящее среднее для сглаживания FPS
                self.fps = 0.9 * self.fps + 0.1 * current_fps if self.fps > 0 else current_fps
                self.fps_label.config(text=f"FPS: {self.fps:.1f}")
            self.last_frame_time = current_time

            ret, frame = self.cap.read()
            if ret:
                # Добавляем кадр в очередь для обработки в потоке
                if len(self.frame_queue) < 2:  # Ограничиваем размер очереди
                    self.frame_queue.append(frame.copy())

                # Обновление происходит только при наличии обработанных данных
                if self.current_ascii:
                    # Обновляем текстовое поле
                    self.text_widget.config(state="normal")
                    self.text_widget.delete("1.0", tk.END)

                    # Режим цветных пикселей
                    if self.settings["color_mode"] == "pixel":
                        # Формируем строку с цветными символами батчами с кэшированием тегов
                        lines = self.current_ascii.split("\n")
                        max_i = min(len(lines), int(self.ascii_size * self.vertical_compression))
                        for i in range(max_i):
                            if i < len(self.current_colors):
                                line = lines[i]
                                max_j = min(len(line), self.ascii_size)
                                current_run_color = None
                                current_run_chars = []
                                for j in range(max_j):
                                    char = line[j]
                                    color = self.current_colors[i][j]
                                    if color not in self.configured_color_tags:
                                        self.text_widget.tag_config(color, foreground=color)
                                        self.configured_color_tags.add(color)
                                    if color == current_run_color:
                                        current_run_chars.append(char)
                                    else:
                                        if current_run_chars:
                                            self.text_widget.insert(tk.END, "".join(current_run_chars), current_run_color)
                                        current_run_color = color
                                        current_run_chars = [char]
                                if current_run_chars:
                                    self.text_widget.insert(tk.END, "".join(current_run_chars), current_run_color)
                                if i < max_i - 1:
                                    self.text_widget.insert(tk.END, "\n")
                    else:
                        # Обычный режим
                        self.text_widget.insert(tk.END, self.current_ascii)

                    # Центрирование
                    self.text_widget.tag_configure("center", justify="center")
                    self.text_widget.tag_add("center", "1.0", tk.END)
                    self.text_widget.config(state="disabled")

                    # Неоновый эффект
                    if self.settings["color_mode"] == "neon":
                        colors = ["#ff00ff", "#00ffff", "#ffff00"]
                        current_color = colors[int(time.time() * 3) % len(colors)]
                        self.text_widget.config(fg=current_color)

                # Ограничиваем частоту обновления для цветного режима
                if self.settings["color_mode"] == "pixel":
                    delay = 67  # ~15 FPS
                else:
                    delay = 33  # ~30 FPS

                self.root.after(delay, self.update_frame)
            else:
                self.root.after(33, self.update_frame)
        except Exception as e:
            print(f"Ошибка обновления кадра: {e}")
            self.root.after(33, self.update_frame)

    def __del__(self):
        self.stop_thread = True
        if hasattr(self, 'cap') and self.cap.isOpened():
            self.cap.release()
        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=1.0)


if __name__ == "__main__":
    root = tk.Tk()
    app = PerfectAsciiMirror(root)
    root.mainloop()