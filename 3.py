# reserve 3

import cv2
import tkinter as tk
from tkinter import font as tkfont, colorchooser, filedialog, Menu
import json
import os
from datetime import datetime
import time
from PIL import Image, ImageDraw, ImageFont


class PerfectAsciiMirror:
    def __init__(self, root):
        self.root = root
        self.root.title("пиздец")

        # Фиксируем квадратное окно
        self.window_size = 600
        self.root.geometry(f"{self.window_size}x{self.window_size}")
        self.root.resizable(False, False)

        # Расширенный набор символов для лучшей градации
        self.ascii_chars = " .'`^\",:;Il!i><~+_-?][}{1)(|\\/*#&8%B@$"
        self.ascii_chars = self.ascii_chars[::-1]  # Инвертируем градиент

        # Размер ASCII-арта (квадрат N×N символов)
        self.ascii_size = 150

        # Настройки по умолчанию
        self.settings = {
            "text_color": "white",
            "bg_color": "black",
            "color_mode": "monochrome",  # monochrome, red, green, blue, neon, pixel
            "pixel_color": False
        }

        # Загрузка сохраненных настроек
        self.load_settings()

        # Создаем моноширинный шрифт с квадратными символами
        self.custom_font = tkfont.Font(
            family="Courier",
            size=5,
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
            height=self.ascii_size*0.55  # Сохраняем ваши пропорции
        )
        self.text_widget.pack(expand=True, padx=20, pady=20)

        # Создаем меню
        self.create_menu()

        # Настройка видеозахвата
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            self.text_widget.insert(tk.END, "Camera Error!")
            return

        # Переменные для обработки кадра
        self.current_frame = None
        self.current_ascii = ""
        self.current_colors = []

        # Начало обработки видео
        self.update_frame()

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
        if not self.current_frame or not self.current_ascii:
            return

        filename = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG файлы", "*.png"), ("Все файлы", "*.*")],
            initialfile=f"ascii_image_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        if not filename:
            return

        # Создаем изображение для рисования
        char_width = 8  # Примерная ширина символа
        char_height = 12  # Примерная высота символа
        width = self.ascii_size * char_width
        height = self.ascii_size * char_height

        img = Image.new("RGB", (width, height), self.settings["bg_color"])
        draw = ImageDraw.Draw(img)
        font = ImageFont.load_default()

        # Разбиваем ASCII-арт на строки
        lines = self.current_ascii.split("\n")

        # Рисуем символы с цветами
        for y, line in enumerate(lines):
            for x, char in enumerate(line):
                if x < self.ascii_size and y < self.ascii_size:
                    # Получаем цвет пикселя
                    if self.settings["color_mode"] == "pixel" and self.current_colors:
                        color = self.current_colors[y][x]
                    else:
                        color = self.settings["text_color"]

                    # Рисуем символ
                    draw.text((x * char_width, y * char_height), char, fill=color, font=font)

        img.save(filename)

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

    def process_frame(self, frame):
        """Обработка кадра с идеально квадратным отображением"""
        # Зеркальное отражение
        frame = cv2.flip(frame, 1)

        # Создаем квадратный кадр (центрированный)
        h, w = frame.shape[:2]
        size = min(h, w)
        start_x = (w - size) // 2
        start_y = (h - size) // 2
        square_frame = frame[start_y:start_y + size, start_x:start_x + size]

        # Ресайз с учетом пропорций
        new_size = self.ascii_size
        resized = cv2.resize(square_frame, (new_size, new_size))
        resized_color = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)  # Для цветного режима

        # Конвертация в ASCII с улучшенной передачей градаций
        ascii_art = ""
        num_chars = len(self.ascii_chars)
        colors = []  # Матрица цветов для каждого символа

        # Для каждой строки в обработанном изображении
        for i, row in enumerate(resized):
            color_row = []
            ascii_line = ""
            # Для каждого пикселя в строке
            for j, pixel in enumerate(row):
                # Нормализация и улучшенное преобразование
                normalized = pixel / 255.0
                # Нелинейное преобразование для лучшего восприятия
                adjusted = normalized ** 0.5
                # Преобразование в индекс символа
                index = min(int(adjusted * (num_chars - 1)), num_chars - 1)
                char = self.ascii_chars[index]
                ascii_line += char

                # Сохраняем цвет пикселя в формате #RRGGBB
                b, g, r = resized_color[i, j]
                hex_color = f"#{r:02x}{g:02x}{b:02x}"
                color_row.append(hex_color)

            ascii_art += ascii_line + "\n"
            colors.append(color_row)

        return ascii_art, colors

    def update_frame(self):
        """Обновление кадра"""
        try:
            ret, frame = self.cap.read()
            if ret:
                # Обработка кадра
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                ascii_art, colors = self.process_frame(gray)

                # Сохраняем текущий кадр и ASCII-арт для сохранения фото
                self.current_frame = frame
                self.current_ascii = ascii_art
                self.current_colors = colors

                # Обновляем текстовое поле
                self.text_widget.config(state="normal")
                self.text_widget.delete("1.0", tk.END)

                # Режим цветных пикселей: добавляем символы с цветами
                if self.settings["color_mode"] == "pixel":
                    lines = ascii_art.split("\n")
                    for i, line in enumerate(lines):
                        if i < len(colors):
                            for j, char in enumerate(line):
                                if j < len(colors[i]):
                                    color = colors[i][j]
                                    self.text_widget.insert(tk.END, char)
                                    self.text_widget.tag_add(f"color_{i}_{j}", f"{i + 1}.{j}", f"{i + 1}.{j + 1}")
                                    self.text_widget.tag_config(f"color_{i}_{j}", foreground=color)
                            self.text_widget.insert(tk.END, "\n")
                else:
                    # Обычный режим
                    self.text_widget.insert(tk.END, ascii_art)

                # Центрирование
                self.text_widget.tag_configure("center", justify="center")
                self.text_widget.tag_add("center", "1.0", tk.END)
                self.text_widget.config(state="disabled")

                # Неоновый эффект (циклическое изменение цвета)
                if self.settings["color_mode"] == "neon":
                    colors = ["#ff00ff", "#00ffff", "#ffff00"]
                    current_color = colors[int(time.time() * 3) % len(colors)]
                    self.text_widget.config(fg=current_color)
        except Exception as e:
            print(f"Ошибка обработки кадра: {e}")

        self.root.after(30, self.update_frame)

    def __del__(self):
        if hasattr(self, 'cap') and self.cap.isOpened():
            self.cap.release()


if __name__ == "__main__":
    root = tk.Tk()
    app = PerfectAsciiMirror(root)
    root.mainloop()