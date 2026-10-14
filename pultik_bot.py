import asyncio
import logging
import sys
import os
import subprocess
import time
from logging import exception

from aiogram import Bot, Dispatcher, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from pprint import pprint

process_script = None
process = None
process_web = None
import datetime
from datetime import timedelta

check_mode_active = False
from aiogram import Bot, Dispatcher, types
from aiogram import Bot, F, Router

admin_id = ['1470467787', '1583882824', '7638002945']
natalia_id = ['1822927560']
import datetime

TOKEN = "7638002945:AAFOZXoydszUByQpjGSPpytP81WrH28OV58"
bot = Bot(token=TOKEN)
dp = Dispatcher()
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery

router = Router()
dp.include_router(router)


def not_converted(s):
    output = []
    if s == 3:
        output = [0]
    if s > 3:
        for i in range(0, s - 3 + 1):
            output.append(-i)
    if s < 3:
        for i in range(0, s + 5):
            output.append(-i)
    return len(output)


@router.message(Command("start"))
async def start(message: Message):
    if str(message.from_user.id) in admin_id:
        help_text = (
            "<b>👋 Привет! Я ваш помощник-бот. Вот список доступных команд:</b>\n\n"
            "<b>Команды для управления скриптами:</b>\n"
        )

        # Создаем кнопки с использованием именованных аргументов
        keyboard_buttons = [
            [
                InlineKeyboardButton(text="вкл скрипт", callback_data='startscript'),
                InlineKeyboardButton(text="вкл отчёт", callback_data='scriptcheckmode'),
                InlineKeyboardButton(text="выкл отчёт", callback_data='stopscriptcheckmode'),
            ],
            [
                InlineKeyboardButton(text="вкл бота", callback_data='startbot'),
                InlineKeyboardButton(text="сост бота", callback_data='botstatus'),
                InlineKeyboardButton(text="выкл бота", callback_data='stopbot'),
            ],
            [
                InlineKeyboardButton(text="отчёт по всем компонентам", callback_data='check'),
            ],
        ]

        # Создаем InlineKeyboardMarkup с кнопками
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

        await message.answer(help_text, parse_mode='HTML', reply_markup=keyboard)
    elif str(message.from_user.id) in natalia_id:
        help_text = (
            "<b>Здравствуйте, Наталья! Я ваш помощник-бот. Вот список доступных команд:</b>\n\n"
            "<b>Команды для управления ботом:</b>\n"
        )
        keyboard_buttons = [
            [
                InlineKeyboardButton(text="Запустить бота", callback_data='startbot'),
                InlineKeyboardButton(text="Статус бота", callback_data='botstatus'),
                InlineKeyboardButton(text="Остановить бота", callback_data='stopbot'),
            ]
        ]
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

        await message.answer(help_text, parse_mode='HTML', reply_markup=keyboard)
    else:
        await message.answer(f"У Вас нет доступа.")


@router.callback_query(F.data.in_(
    ['startscript', 'scriptstatus', 'scriptcheckmode', 'stopscriptcheckmode', 'startbot', 'botstatus', 'stopbot',
     'check']))
async def process_callback(callback_query: CallbackQuery):
    command = callback_query.data
    user_id = callback_query.from_user.id

    if str(user_id) in admin_id:
        await callback_query.answer()
        if command == 'startscript':
            await startscript(callback_query.message)
        elif command == 'scriptstatus':
            await scriptstatus(callback_query.message)
        elif command == 'scriptcheckmode':
            await scriptcheckmode(callback_query.message)
        elif command == 'stopscriptcheckmode':
            await stopscriptcheckmode(callback_query.message)
        elif command == 'startbot':
            await startbot(callback_query.message)
        elif command == 'botstatus':
            await botstatus(callback_query.message)
        elif command == 'stopbot':
            await stopbot(callback_query.message)
        elif command == 'check':
            await check(callback_query.message)

        await callback_query.answer()  # Убираем уведомление о нажатии кнопки
    elif str(user_id) in natalia_id:
        if command == 'startbot':
            await startbot(callback_query.message)
        elif command == 'botstatus':
            await botstatus(callback_query.message)
        elif command == 'stopbot':
            await stopbot(callback_query.message)
    else:
        await callback_query.answer("У Вас нет доступа.")


@dp.message(Command('startscript'))
async def startscript(message: Message):
    global process_script

    # Проверка прав доступа
    if str(message.from_user.id) not in admin_id:
        await message.answer(f"У Вас нет доступа. Ваш ID: {message.from_user.id}")
        return

    # Проверка состояния процесса
    if process_script is not None and process_script.poll() is None:
        await message.answer("Скрипт уже запущен.")
        return

    try:
        # Запуск скрипта
        venv_python = "/home/dev/ExampleApp/.venv/bin/python"
        script_path = "/home/dev/GigaAM_API/keep_txts.py"

        process_script = subprocess.Popen(
            [venv_python, script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            bufsize=1,
            universal_newlines=True
        )
        stdout, stderr = process_script.communicate()
        # Даем время на запуск
        await asyncio.sleep(3)
        if stdout: await message.answer(f"```Output\n{stdout[-4000:]}\n```", parse_mode='Markdown')
        if stderr: await message.answer(f"```Error\n{stderr[-4000:]}\n```", parse_mode='Markdown')
        if process_script is not None:
            await message.answer(f"Скрипт запущен")

        else:
            await message.answer("Не удалось запустить скрипт")

    except Exception as e:
        await message.answer(f"Ошибка при запуске скрипта: {str(e)}")
        process_script = None


@dp.message(Command('stopscript'))
async def stopscript(message: Message):
    global process_script

    # Проверка прав доступа
    if str(message.from_user.id) not in admin_id:
        await message.answer(f"У Вас нет доступа. Ваш ID: {message.from_user.id}")
        return

    # Проверка состояния процесса
    if process_script is None or process_script.poll() is not None:
        await message.answer("Скрипт не запущен.")
        return

    try:
        process_script.terminate()


    except Exception as e:
        await message.answer(f"Ошибка при остановке скрипта: {str(e)}")
        process_script = None


@dp.message(Command('scriptstatus'))
async def scriptstatus(message: Message):
    global process_script

    # Проверка прав доступа
    if str(message.from_user.id) not in admin_id:
        await message.answer(f"У Вас нет доступа. Ваш ID: {message.from_user.id}")
        return

    # Проверка состо яния процесса
    try:
        if process_script is None:
            status = "Скрипт никогда не запускался"
        elif process_script.poll() is None:
            status = "Скрипт запущен"
            returncode = process_script.returncode
            status = f"Скрипт завершился с кодом: {returncode}"
        else:
            returncode = process_script.returncode
            status = f"Скрипт завершился с кодом: {returncode}"

        await message.answer(status)

    except Exception as e:
        await message.answer(f"Ошибка при проверке статуса: {str(e)}")


@dp.message(Command('scriptcheckmode'))
async def scriptcheckmode(message: Message):
    global check_mode_active
    if str(message.from_user.id) in admin_id:
        if not check_mode_active:
            check_mode_active = True
            await message.answer("Режим проверки скрипта активирован.")
            asyncio.create_task(check_script_status())
        else:
            await message.answer("Режим проверки скрипта уже активен.")
    else:
        await message.answer("У Вас нет доступа.")


@dp.message(Command('stopscriptcheckmode'))
async def stopscriptcheckmode(message: Message):
    global check_mode_active
    if str(message.from_user.id) in admin_id:
        check_mode_active = False
        await message.answer("Режим проверки скрипта остановлен.")
    else:
        user_id = message.from_user.id
        await message.answer(f"У Вас нет доступа. Ваш ID: {user_id}")


async def check_script_status():
    global process_script, check_mode_active
    while check_mode_active:
        if process_script is not None and process_script.poll() is None:
            await bot.send_message(admin_id[0], f"{report()}\nСкрипт все еще запущен.", parse_mode='HTML')
        else:
            await bot.send_message(admin_id[0], f"{report()}\nСкрипт не запущен.", parse_mode='HTML')
        process_script.terminate()
        venv_python = "/home/dev/ExampleApp/.venv/bin/python"
        script_path = "/home/dev/GigaAM_API/keep_txts.py"
        process_script = subprocess.Popen(
            [venv_python, script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            bufsize=1,
            universal_newlines=True
        )
        stdout, stderr = process_script.communicate()
        await asyncio.sleep(900)


@dp.message(Command('startbot'))
async def startbot(message: Message):
    global process
    if str(message.from_user.id) in admin_id or str(message.from_user.id) in natalia_id:
        if not process:
            venv_python = "/home/dev/Calls_TG_Bot/venv/bin/python"
            script_path = "/home/dev/Calls_TG_Bot/bot.py"
            process = subprocess.Popen(
                [venv_python, script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            await message.answer("Бот запущен на 30 минут.")
        else:
            await message.answer("Бот уже запущен.")
    else:
        await message.answer("У Вас нет доступа.")
    await asyncio.sleep(1800)
    if process:
        process.terminate()
        await message.answer("Бот остановлен.")


@dp.message(Command('botstatus'))
async def botstatus(message: Message):
    global process
    if str(message.from_user.id) in admin_id or str(message.from_user.id) in natalia_id:
        if process is not None:
            await message.answer("Бот запущен.")
        else:
            await message.answer("Бот не запущен.")
    else:
        user_id = message.from_user.id
        await message.answer(f"У Вас нет доступа. Ваш ID: {user_id}")


@dp.message(Command('stopbot'))
async def stopbot(message: Message):
    global process
    if str(message.from_user.id) in admin_id or str(message.from_user.id) in natalia_id:
        if process:
            process.terminate()  # Остановка процесса
            process = None
            botenabled = False
            await message.answer("Бот остановлен.")
        else:
            await message.answer("Бот не запущен.")
    else:
        user_id = message.from_user.id
        await message.answer(f"У Вас нет доступа. Ваш ID: {user_id}")


@dp.message(Command('check'))
async def check(message: Message):
    if str(message.from_user.id) in admin_id:
        answer = f'Сейчас {str(datetime.datetime.now())[:-10]}:\n'
        global process, process_web, process_script
        if process is not None and process.poll() is None:
            answer += '• Бот запущен\n'
        else:
            answer += '• Бот не запущен\n'
        if process_script is not None and process_script.poll() is None:
            answer += '• Скрипт запущен\n'
        else:
            answer += '• Скрипт не запущен\n'
        answer += '\n<code>' + str(report()) + '\n</code>'
        await message.answer(answer)
    else:
        user_id = message.from_user.id
        await message.answer(f"У Вас нет доступа. Ваш ID: {user_id}")


@dp.message(Command('scriptpid'))
async def scriptpid(message: Message):
    if process_script:
        await message.answer(f"PID процесса: {process_script.pid}")
    else:
        await message.answer("Процесс не запущен")


@dp.message(Command('botlogs'))
async def botlogs(message: Message):
    try:
        with open('/home/dev/calls_bot_for_me/bot.log', 'r') as f:
            logs = f.read()[-4000:]  # Последние 4000 символов
            await message.answer(f"Логи:\n```Run\n{logs}\n```", parse_mode='Markdown')
    except Exception as e:
        await message.answer(f"Ошибка чтения логов: ```Run\n{e}\n```", parse_mode='Markdown')


import paramiko


def connect_to_sftp(hostname, username, password, remote_path):
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # Добавляет неизвестный хост в известные
        ssh.connect(hostname, username=username, password=password)
        sftp = ssh.open_sftp()
        if len(remote_path) > 3:
            if remote_path[1] == '/': remote_path = remote_path[1:]
        sftp.chdir(remote_path)  # Переходим в указанную директорию.  Обработка ошибок ниже.
        return sftp
    except paramiko.AuthenticationException:
        print("Ошибка аутентификации. Проверьте имя пользователя и пароль.")
        return None
    except paramiko.SSHException as e:
        print(f"Ошибка SSH: {e}")
        return None
    except FileNotFoundError:
        print(f"Директория {remote_path} не найдена на сервере.")
        return None
    except IOError as e:
        print(f"Ошибка ввода-вывода: {e}")
        return None


def report():
    report = f'Отчёт за {str(datetime.datetime.now())[:-7]}\n'
    hour = str(datetime.datetime.today()).split(' ')[1].split(':')[0]
    a = not_converted(datetime.datetime.now().weekday())
    if int(hour) < 9:
        yesterday = datetime.datetime.now() - timedelta(days=1)
        year = yesterday.strftime("%Y")
        month = yesterday.strftime("%m")
        day = yesterday.strftime("%d")

        # Формируем remote_path
        if int(day) > 10:
            remote_path = f"/{year}/{month}/{int(day)}/"
        else:
            remote_path = f"/{year}/{month}/0{int(day)}/"
    else:
        today = datetime.datetime.now()
        year = today.strftime("%Y")
        month = today.strftime("%m")
        day = today.strftime("%d")
        if int(day) > 9:
            remote_path = f"/{year}/{month}/{int(day)}/"
        else:
            remote_path = f"/{year}/{month}/0{int(day)}/"
    os.makedirs('/media/dev/TEXTFILES' + remote_path, exist_ok=True)
    recognized_all = os.listdir('/media/dev/TEXTFILES' + remote_path)
    sftp_client = connect_to_sftp("192.168.1.150", "monitor", "Audio4analy6!6", remote_path)
    files = sftp_client.listdir()
    for i in files:
        if not 'in-' in i or '_t' in i:
            files.pop(files.index(i))
    txtfiles = [i[:-4] for i in os.listdir(f'/media/dev/TEXTFILES{remote_path}')] + os.listdir(
        f'/media/dev/TEXTFILES/error_audiofiles/OutOfMemoryError{remote_path}') + os.listdir(
        f'/media/dev/TEXTFILES/error_audiofiles/IndexError{remote_path}')
    files = list(set(files) - set(txtfiles))
    # print(files)
    # flush()
    all = 1
    if files:
        for i in files:
            if 'in-' in i and not '_t' in i and not 'mp3' in i: all += 1

    recognized = []
    for file in recognized_all:
        if 'in-' in file: recognized.append(file)
    recognized = len(recognized)
    try:
        inderr_audios = len(os.listdir('/media/dev/TEXTFILES/error_audiofiles/IndexError' + remote_path))
    except FileNotFoundError:
        inderr_audios = 0
    try:
        memerr_audios = len(os.listdir('/media/dev/TEXTFILES/error_audiofiles/OutOfMemoryError' + remote_path))
    except FileNotFoundError:
        memerr_audios = 0
    try:
        sftp_client = connect_to_sftp("192.168.1.150", "monitor", "Audio4analy6!6", remote_path)
        calls_list = sftp_client.listdir()
        calls_count = len(calls_list)
        for i in calls_list:
            if not 'in-' in i:
                calls_count -= 1
    except Exception as e:
        calls_count = e
    report += f'<b>Всего звонков:</b> {all}\n<b>Обработано звонков:</b> {len(txtfiles)}\n<b>Распознано звонков:</b> {len(os.listdir('/media/dev/TEXTFILES/' + remote_path))}\n<b>Требует ручной обработки:</b> {memerr_audios}\n'

    if inderr_audios != 0: report += f'<b>IndexError:</b> {inderr_audios}\n'
    '''call_count_list= {}
    sftp_client = connect_to_sftp("192.168.1.150", "monitor", "Audio4analy6!6", remote_path)
    for i in range(7):
        yesterday = datetime.datetime.now() - timedelta(days=i)
        year = yesterday.strftime("%Y")
        month = yesterday.strftime("%m")
        day = yesterday.strftime("%d")
        if int(day) >= 10:
            remote_path = f"/{year}/{month}/{int(day)}/"
        else:
            remote_path = f"/{year}/{month}/0{int(day)}/"
        try:
            calls_list_len = len(sftp_client.listdir(remote_path))
            call_count_list[remote_path]=calls_list_len
        except Exception as e:
            print(f"Ошибка при получении списка файлов из {remote_path}: {e}")
    sftp_client.close()'''

    for i in range(7):
        sftp_client = connect_to_sftp("192.168.1.150", "monitor", "Audio4analy6!6", remote_path)
        filess = sftp_client.listdir()
        all_in_files = []
        for filee in filess:
            if 'in-' in filee and not '_t' in filee and not 'mp3' in filee:
                all_in_files.append(i)
        txtfiles = [i[:-4] for i in os.listdir(f'/media/dev/TEXTFILES{remote_path}')] + os.listdir(
            f'/media/dev/TEXTFILES/error_audiofiles/OutOfMemoryError{remote_path}') + os.listdir(
            f'/media/dev/TEXTFILES/error_audiofiles/IndexError{remote_path}')
        left_in_files = list(set(all_in_files) - set(txtfiles))
        sftp_client = connect_to_sftp("192.168.1.150", "monitor", "Audio4analy6!6", remote_path)
        files = sftp_client.listdir()
        for file in files:
            if not 'in-' in file or '_t' in file:
                files.pop(files.index(file))
        txtfiles = [
                       j[:-4] for j in os.listdir(f'/media/dev/TEXTFILES{remote_path}')] + os.listdir(
            f'/media/dev/TEXTFILES/error_audiofiles/OutOfMemoryError{remote_path}') + os.listdir(
            f'/media/dev/TEXTFILES/error_audiofiles/IndexError{remote_path}')
        files = list(set(files) - set(txtfiles))
        # print(files)
        # flush()
        all = 0
        if files:
            for file in files:
                if 'in-' in file and not '_t' in file and not 'mp3' in file: all += 1
        bad_disk_files = []
        a -= 1
        if a >= 0: report += '(NC) '
        yesterday = datetime.datetime.now() - timedelta(days=i)
        year = yesterday.strftime("%Y")
        month = yesterday.strftime("%m")
        day = yesterday.strftime("%d")
        if int(day) >= 10:
            remote_path = f"/{year}/{month}/{int(day)}/"
        else:
            remote_path = f"/{year}/{month}/0{int(day)}/"
        os.makedirs('/media/dev/TEXTFILES' + remote_path, exist_ok=True)
        all_disk_files = [i[:-4] for i in os.listdir('/media/dev/TEXTFILES' + remote_path)]
        try:
            all_disk_files += os.listdir('/media/dev/TEXTFILES/error_audiofiles/IndexError' + remote_path)
        except FileNotFoundError:
            inderr_audios = 0
        try:
            bad_disk_files += os.listdir('/media/dev/TEXTFILES/error_audiofiles/OutOfMemoryError' + remote_path)
        except FileNotFoundError:
            memerr_audios = 0
        all_serv_files = []
        try:
            sftp_client = connect_to_sftp("192.168.1.150", "monitor", "Audio4analy6!6", remote_path)
            all_serv_files = sftp_client.listdir()
        except AttributeError:
            all_serv_files = set()
        bad_files = []
        for i in all_disk_files:
            if '_' in i or 'out' in i or 'internal-' in i: bad_files.append(i)
        for i in all_serv_files:
            if '_' in i or 'out' in i or 'internal-' in i: bad_files.append(i)

        '''try:
            sftp_client = connect_to_sftp("192.168.1.150", "monitor", "Audio4analy6!6", remote_path)
            calls_list = sftp_client.listdir()
            calls_count = len(set(calls_list) - set(bad_files))
        except Exception as e:
            calls_count = e'''
        try:
            inderr_audios = len(
                set(os.listdir('/media/dev/TEXTFILES/error_audiofiles/IndexError' + remote_path)) - set(bad_files))
        except FileNotFoundError:
            inderr_audios = 0
        try:
            memerr_audios = len(
                set(os.listdir('/media/dev/TEXTFILES/error_audiofiles/OutOfMemoryError' + remote_path)) - set(
                    bad_files))
        except FileNotFoundError:
            memerr_audios = 0
        try:
            calls_count / 1

            report += f'{day}.{month} - {inderr_audios} {memerr_audios} {len(all_in_files) - len(left_in_files)}/{len(all_in_files)}\n'
            # report += f'({len((set(all_serv_files) - set(all_disk_files)) - set(bad_files))})\n'  # -(set(all_disk_files)-set(bad_files))}\n'
            # print(remote_path+str(set(all_serv_files) - set(all_disk_files)) - set(bad_files))
        except TypeError:
            report += f'{day}.{month} - {inderr_audios} {memerr_audios} {inderr_audios + memerr_audios + len(set(os.listdir('/media/dev/TEXTFILES' + remote_path)) - set(bad_files))}/0\n'
        print(str((set(all_serv_files) - set(all_disk_files)) - set(bad_files)) + '\n\n\n')
    return report


'''    os.makedirs('/media/dev/TEXTFILES' + remote_path, exist_ok=True)
    recognized = len(os.listdir('/media/dev/TEXTFILES' + remote_path))
    try:
        inderr_audios = len(os.listdir('/media/dev/TEXTFILES/error_audiofiles/IndexError'+remote_path))
    except FileNotFoundError:
        inderr_audios = 0
    try:
        memerr_audios = len(os.listdir('/media/dev/TEXTFILES/error_audiofiles/OutOfMemoryError'+remote_path))
    except FileNotFoundError:
        memerr_audios = 0
    try:
        sftp_client = connect_to_sftp("192.168.1.150", "monitor", "Audio4analy6!6", remote_path)
        calls_list = sftp_client.listdir()
        calls_count = len(calls_list)
    except Exception as e:
        calls_count = e
    report+=f'<b>Всего звонков:</b> {calls_count}\n<b>Обработано звонков:</b> {recognized+inderr_audios+memerr_audios}\n<b>Распознано звонков:</b> {recognized}\n<b>Требует ручной обработки:</b> {memerr_audios}\n'
    if inderr_audios!=0: report+= f'<b>IndexError:</b> {inderr_audios}\n'
    for i in range(7):
        a-=1
        if a>=0: report+='(NC) '
        yesterday = datetime.datetime.now() - timedelta(days=i)
        year = yesterday.strftime("%Y")
        month = yesterday.strftime("%m")
        day = yesterday.strftime("%d")
        if int(day) >= 10: remote_path = f"/{year}/{month}/{int(day)}/"
        else: remote_path = f"/{year}/{month}/0{int(day)}/"
        os.makedirs('/media/dev/TEXTFILES'+remote_path,exist_ok=True)
        all_disk_files = [i[:-4] for i in os.listdir('/media/dev/TEXTFILES' + remote_path)]
        try:
            all_disk_files+=os.listdir('/media/dev/TEXTFILES/error_audiofiles/IndexError' + remote_path)
        except FileNotFoundError:
            inderr_audios = 0
        try:
            all_disk_files+=os.listdir('/media/dev/TEXTFILES/error_audiofiles/OutOfMemoryError' + remote_path)
        except FileNotFoundError:
            memerr_audios = 0
        all_serv_files = []
        try:
            sftp_client = connect_to_sftp("192.168.1.150", "monitor", "Audio4analy6!6", remote_path)
            all_serv_files = sftp_client.listdir()
        except FileNotFoundError:
            all_serv_files=set()
        bad_files=[]
        for i in all_disk_files:
            if '_' in i: bad_files.append(i)
        for i in all_serv_files:
            if '_' in i: bad_files.append(i)

        try:
            sftp_client = connect_to_sftp("192.168.1.150", "monitor", "Audio4analy6!6", remote_path)
            calls_list = sftp_client.listdir()
            calls_count = len(set(calls_list)-set(bad_files))
        except Exception as e:
            calls_count=e
        try:
            inderr_audios = len(set(os.listdir('/media/dev/TEXTFILES/error_audiofiles/IndexError' + remote_path))-set(bad_files))
        except FileNotFoundError:
            inderr_audios = 0
        try:
            memerr_audios = len(set(os.listdir('/media/dev/TEXTFILES/error_audiofiles/OutOfMemoryError' + remote_path))-set(bad_files))
        except FileNotFoundError:
            memerr_audios = 0
        try:
            calls_count/1

            report += f'{day}.{month} - {inderr_audios} {memerr_audios}  {len(set(all_disk_files)-set(bad_files))}/{str(len(set(all_serv_files)-set(bad_files)))}'
            report += f'({len(set(all_serv_files)-set(all_disk_files))})\n'#-(set(all_disk_files)-set(bad_files))}\n'
        except TypeError:
            report +=f'{day}.{month} - {inderr_audios + memerr_audios + len(set(os.listdir('/media/dev/TEXTFILES' + remote_path))-set(bad_files))}/0\n'
'''


def report_day(remote_path):
    report = f'Отчёт за {str(remote_path.replace('/', '-')[1:-1])}\n'
    hour = str(datetime.datetime.today()).split(' ')[1].split(':')[0]
    os.makedirs('/media/dev/TEXTFILES' + remote_path, exist_ok=True)
    recognized = len(os.listdir('/media/dev/TEXTFILES' + remote_path))
    try:
        inderr_audios = len(os.listdir('/media/dev/TEXTFILES/error_audiofiles/IndexError' + remote_path))
    except FileNotFoundError:
        inderr_audios = 0
    try:
        memerr_audios = len(os.listdir('/media/dev/TEXTFILES/error_audiofiles/OutOfMemoryError' + remote_path))
    except FileNotFoundError:
        memerr_audios = 0
    try:
        sftp_client = connect_to_sftp("192.168.1.150", "monitor", "Audio4analy6!6", remote_path)
        calls_list = sftp_client.listdir()
        calls_count = len(calls_list)
    except Exception as e:
        calls_count = e
    report += f'<b>Всего звонков:</b> {calls_count}\n<b>Обработано звонков:</b> {recognized + inderr_audios + memerr_audios}\n<b>Распознано звонков:</b> {recognized}\n<b>Требует ручной обработки:</b> {memerr_audios}'
    if inderr_audios != 0: report += f'\n<b>IndexError:</b> {inderr_audios}'
    return report


import re


@router.message(F.text.contains("отчёт"))
async def send_report(message: Message):
    if 'отчёт' in message.text and '/' in message.text:
        remote_path = message.text[message.text.index('/'):message.text.index('/') + 12]
        try:
            connect_to_sftp("192.168.1.150", "monitor", "Audio4analy6!6", remote_path)
        except FileNotFoundError:
            await message.answer('Директория не найдена.')
        await message.answer(report_day(remote_path))


from pathlib import Path


async def main() -> None:
    # Initialize Bot instance with default bot properties which will be passed to all API calls
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    global process_gigaam_api
    BASE_DIR = Path(__file__).parent.absolute()
    with open("bot_api.log", "w") as log_file:
        process_gigaam_api = subprocess.Popen(
            ['/home/dev/ExampleApp/.venv/bin/python', '/home/dev/GigaAM_API/run.py'],
            cwd=BASE_DIR,
            stdout=log_file,
            stderr=log_file,
            text=True,
            encoding='utf-8',
            bufsize=1,
            universal_newlines=True
        )
    global process_script
    await bot.send_message(admin_id[0], "Сервер перезагрузился.", parse_mode='HTML')
    logging.basicConfig(
        filename='/home/dev/calls_bot_for_me/script.log',
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    if datetime.datetime.now().weekday() < 5 and int(
            str(datetime.datetime.now()).split(" ")[1].split(":")[0]) >= 9 and int(
            str(datetime.datetime.now()).split(" ")[1].split(":")[0]) <= 16:
        try:
            global process_script

            try:
                process_script.terminate()

            except Exception as e:
                process_script = None
            global process
            if not process:
                venv_python = "/home/dev/Calls_TG_Bot/venv/bin/python"
                script_path = "/home/dev/Calls_TG_Bot/bot.py"
                process = subprocess.Popen(
                    [venv_python, script_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                await bot.send_message(admin_id[0], text="Бот запущен.")
            else:
                await bot.send_message(admin_id[0], text="Бот уже запущен.")
        except Exception as e:
            await bot.send_message(admin_id[0], text=f"Ошибка при запуске бота:\n{e}")
    else:
        try:
            # Запуск скрипта

            venv_python = "/home/dev/ExampleApp/.venv/bin/python"
            script_path = "/home/dev/GigaAM_API/keep_txts.py"

            process_script = subprocess.Popen(
                [venv_python, script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                bufsize=1,
                universal_newlines=True
            )

            # Даем время на запуск
            await asyncio.sleep(3)
            logging.info(f"Вывод: {process_script.stdout}")
            if process_script is not None:
                await bot.send_message(admin_id[0], "Скрипт запущен")
                asyncio.create_task(check_script_status())
            else:
                await bot.send_message(admin_id[0], "Не удалось запустить скрипт")


        except Exception as e:
            logging.error(f"Код ошибки: {e.returncode}")
            logging.error(f"Вывод ошибки: {e.stderr}")
            await bot.send_message(admin_id[0], f"Ошибка при запуске скрипта: {str(e)}")
            process_script = None
    # And the run events dispatching
    await dp.start_polling(bot)


def all_calls(remote_path):
    sftp_client = connect_to_sftp("192.168.1.150", "monitor", "Audio4analy6!6", remote_path)

    all = sftp_client.listdir()
    result = []
    for i in all:
        if 'in-' in i:
            result.append(i)
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())