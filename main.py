import asyncio
import logging
import sys
import os
import subprocess
import time
from logging import exception
from aiogram import Bot, Dispatcher, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ContentType
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from pprint import pprint
from aiogram import Bot, Dispatcher, types
from aiogram import Bot, F, Router
import datetime
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
import cv2
import numpy as np


token = "8277104926:AAGeQnKwKIIEOZIjq6NT2DuqkoRffwijLO0"

bot = Bot(token=token)
dp = Dispatcher()

router = Router()
dp.include_router(router)

@router.message(Command("start"))
async def start(message: Message):
    await message.answer("hi", parse_mode='HTML')

dir = "/tmp"
@router.message(ContentType.VIDEO)
async def video(message: Message):
    video = message.video
    video_id = video.file_id

    file = await bot.get_file(video_id)
    file_path = file.file_path
    download_path = os.path.join(dir, f"{video_id}.mp4")
    await bot.download_file(file_path, destination=download_path)

    cap = cv2.VideoCapture(download_path)

    frames = []
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # OpenCV возвращает кадр как numpy-массив (BGR)
        frames.append(frame)  # frame.shape = (height, width, 3)

    cap.release()

    video_frames = np.array(frames)





async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())