# reserve 1

import cv2
import numpy as np
import tkinter as tk
from tkinter import font as tkfont


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
        #self.ascii_chars = " .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$"
        self.ascii_chars = self.ascii_chars[::-1]  # Инвертируем градиент

        # Размер ASCII-арта (квадрат N×N символов)
        self.ascii_size = 150

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
            bg="black",
            fg="white",
            insertontime=0,
            borderwidth=0,
            highlightthickness=0,
            width=self.ascii_size,
            height=self.ascii_size*0.55
        )
        self.text_widget.pack(expand=True, padx=20, pady=20)

        # Настройка видеозахвата
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            self.text_widget.insert(tk.END, "Camera Error!")
            return

        # Начало обработки видео
        self.update_frame()

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

        # Конвертация в ASCII с улучшенной передачей градаций
        ascii_art = ""
        num_chars = len(self.ascii_chars)

        # Для каждой строки в обработанном изображении
        for row in resized:
            # Для каждого пикселя в строке
            for pixel in row:
                # Нормализация и улучшенное преобразование
                normalized = pixel / 255.0
                # Нелинейное преобразование для лучшего восприятия
                adjusted = normalized ** 0.5
                # Преобразование в индекс символа
                index = min(int(adjusted * (num_chars - 1)), num_chars - 1)
                ascii_art += self.ascii_chars[index]
            ascii_art += "\n"
        return ascii_art

    def update_frame(self):
        """Обновление кадра"""
        ret, frame = self.cap.read()
        if ret:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            ascii_art = self.process_frame(gray)

            self.text_widget.delete(1.0, tk.END)
            self.text_widget.insert(tk.END, ascii_art)
            self.text_widget.tag_configure("center", justify="center")
            self.text_widget.tag_add("center", 1.0, tk.END)

        self.root.after(30, self.update_frame)

    def __del__(self):
        if self.cap and self.cap.isOpened():
            self.cap.release()


if __name__ == "__main__":
    root = tk.Tk()
    app = PerfectAsciiMirror(root)
    root.mainloop()