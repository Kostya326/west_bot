import asyncio
import logging
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    ReplyKeyboardRemove
)

from dotenv import load_dotenv  # ← вот здесь должно быть ровно так

load_dotenv()  # ← загружает .env, если есть

# ──────────────────────────────────────────────
#               НАСТРОЙКИ
# ──────────────────────────────────────────────

TOKEN = "8222867191:AAHai1v7mGYiQwUtJjxFjdC3TX-UqU8Xd6E"


ADMIN_ID = 456296772

import asyncio
import time


SLOTS = [
    "10:00–12:00",
    "12:00–14:00",
    "14:00–16:00",
    "16:00–18:00",
    "18:00–20:00"
]

CERAMIC_START = "16:00"
CERAMIC_END   = "20:00"

kb_services = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🧼 Мойка", callback_data="service:wash")],
    [InlineKeyboardButton(text="✨ Полировка", callback_data="service:polish")],
    [InlineKeyboardButton(text="🛡️ Керамика", callback_data="service:ceramic")],
    [InlineKeyboardButton(text="🧼 Химчистка", callback_data="service:clean")],
    [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
])

# Хранилище записей (пока в памяти)
bookings = {}  # пример ключа: "2026-01-23_10:00–12:00_A" → {"user_id": 123, "service": "wash", ...}

user_data = {}  # {user_id: {"service": ..., "date": ..., "slot": ..., "box": ..., "body": ...}}

# Русские названия услуг
SERVICE_NAMES = {
    "wash": "Мойка",
    "polish": "Полировка",
    "ceramic": "Керамика",
    "clean": "Химчистка"  # химчистка
}

# Русские названия кузовов
BODY_NAMES = {
    "sedan": "Седан",
    "crossover": "Кроссовер",
    "suv": "Внедорожник"
}

# ──────────────────────────────────────────────
#               БОТ
# ──────────────────────────────────────────────

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
dp = Dispatcher()

@dp.message(CommandStart())
async def cmd_start(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Начать запись", callback_data="start_booking")]
    ])

    await message.answer(
        "Привет! Я бот для записи в детейлтнг-центр West Detail.🚗🧼\n"
        "Нажми кнопку ниже, чтобы начать.",
        reply_markup=kb
    )


@dp.callback_query(F.data == "start_booking")
async def show_services(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🧼 Мойка", callback_data="service:wash")],
            [InlineKeyboardButton(text="✨ Полировка", callback_data="service:polish")],
            [InlineKeyboardButton(text="🛡️ Керамика", callback_data="service:ceramic")],
            [InlineKeyboardButton(text="🧼 Химчистка", callback_data="service:clean")], ]
    )

    await callback.message.edit_text(
        "Выберите услугу.\n\n"
        "💡 Цена варьируется от типа кузова и выбранных работ.",
        reply_markup=kb
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("service:"))
async def show_body(callback: CallbackQuery):
    service = callback.data.split(":")[1]

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🚗 Седан — от 2000 ₽",
                callback_data=f"body:{service}:sedan"
            )
        ],
        [
            InlineKeyboardButton(
                text="🚙 Кроссовер — от 2500 ₽",
                callback_data=f"body:{service}:crossover"
            )
        ],
        [
            InlineKeyboardButton(
                text="🛻 Внедорожник — от 3000 ₽",
                callback_data=f"body:{service}:suv"
            )
        ],
        [
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
        ]
    ])

    await callback.message.edit_text(
        "Выберите тип кузова и стоимость услуги:",
        reply_markup=kb
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("body:"))
async def choose_date(callback: CallbackQuery):
    parts = callback.data.split(":")
    if len(parts) < 3:
        await callback.message.edit_text("Ошибка: неверный запрос.", reply_markup=None)
        await callback.answer()
        return

    service = parts[1]
    body = parts[2]

    today = datetime.now()
    weekdays_ru = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

    date_buttons = []

    for i in range(7):
        dt = today + timedelta(days=i)
        date_key = dt.strftime("%Y-%m-%d")

        # Проверяем, есть ли хоть один свободный слот на эту дату
        has_free_slot = False

        if service == "ceramic":
            slot = "16:00–20:00"
            key_a = f"{date_key}_{slot}_A"
            key_b = f"{date_key}_{slot}_B"
            if key_a not in bookings and key_b not in bookings:
                has_free_slot = True
        else:
            for slot in SLOTS:
                key_a = f"{date_key}_{slot}_A"
                key_b = f"{date_key}_{slot}_B"

                # Пропускаем слоты после 16:00, если стоит керамика
                if slot >= "16:00–18:00" and any(k.startswith(f"{date_key}_16:00–20:00_") for k in bookings):
                    continue

                # Если хотя бы один бокс свободен — дата жива
                if key_a not in bookings or key_b not in bookings:
                    has_free_slot = True
                    break  # нашли свободный — хватит, не проверяем дальше

        if has_free_slot:
            weekday_idx = dt.weekday()
            day_str = f"{dt.day:02d}.{dt.month:02d} ({weekdays_ru[weekday_idx]})"
            date_buttons.append(
                InlineKeyboardButton(
                    text=day_str,
                    callback_data=f"date:{service}:{body}:{i}"
                )
            )

    # Формируем клавиатуру
    if date_buttons:
        kb_rows = []
        for i in range(0, len(date_buttons), 2):
            row = date_buttons[i:i+2]
            kb_rows.append(row)

        kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)

        await callback.message.edit_text(
            "Выбери дату:",
            reply_markup=kb
        )
    else:
        await callback.message.edit_text(
            "❌ На ближайшие 7 дней нет свободных слотов.",
            reply_markup=None
        )

    await callback.answer() 

@dp.callback_query(lambda c: c.data.startswith("date:"))
async def choose_slot(callback: CallbackQuery):
    parts = callback.data.split(":")
    if len(parts) < 4:
        await callback.message.edit_text("Ошибка: неверный запрос.", reply_markup=None)
        await callback.answer()
        return

    service = parts[1]
    body = parts[2]
    day_offset = int(parts[3])

    chosen_date = datetime.now() + timedelta(days=day_offset)
    date_key = chosen_date.strftime("%Y-%m-%d")

    kb = InlineKeyboardMarkup(inline_keyboard=[])

    if service == "ceramic":
        slot = "16:00–20:00"
        key_a = f"{date_key}_{slot}_A"
        key_b = f"{date_key}_{slot}_B"
        if key_a not in bookings and key_b not in bookings:
            kb.inline_keyboard.append([
                InlineKeyboardButton(
                    text=f"{slot} (керамика — весь день)",
                    callback_data=f"slot:{service}:{date_key}:{body}:{slot}"
                )
            ])
    else:
        for slot in SLOTS:
            key_a = f"{date_key}_{slot}_A"
            key_b = f"{date_key}_{slot}_B"

            # Пропускаем слоты после 16:00, если стоит керамика
            if slot >= "16:00–18:00" and any(k.startswith(f"{date_key}_16:00–20:00_") for k in bookings):
                continue

            # Показываем кнопку ТОЛЬКО если есть хотя бы один свободный бокс
            if key_a in bookings and key_b in bookings:
                continue  # оба заняты — НЕ показываем кнопку

            kb.inline_keyboard.append([
                InlineKeyboardButton(
                    text=slot,
                    callback_data=f"slot:{service}:{date_key}:{body}:{slot}"
                )
            ])

    # Кнопка "Назад" — всегда
    kb.inline_keyboard.append([
        InlineKeyboardButton(
            text="⬅️ Назад к датам",
            callback_data=f"back_to_date:{service}:{body}"
        )
    ])

    if len(kb.inline_keyboard) > 1:  # >1 — значит есть хотя бы один слот (кроме "Назад")
        await callback.message.edit_text(
            f"Выбери слот на {chosen_date.strftime('%d.%m.%Y')}:",
            reply_markup=kb
        )
    else:
        # Нет свободных слотов — только сообщение + кнопка "Назад"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="⬅️ Назад к датам",
                callback_data=f"back_to_date:{service}:{body}"
            )]
        ])
        await callback.message.edit_text(
            "❌ На эту дату нет свободных слотов.",
            reply_markup=kb
        )

    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("back_to_date:"))
async def back_to_date(callback: CallbackQuery):
    parts = callback.data.split(":")
    if len(parts) < 3:
        await callback.message.edit_text("Ошибка: неверный запрос.", reply_markup=None)
        await callback.answer()
        return

    service = parts[1]
    body = parts[2]

    # Показываем выбор даты заново
    today = datetime.now()
    weekdays_ru = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

    kb = InlineKeyboardMarkup(inline_keyboard=[])

    for i in range(7):
        dt = today + timedelta(days=i)
        date_key = dt.strftime("%Y-%m-%d")

        has_free_slot = False

        if service == "ceramic":
            slot = "16:00–20:00"
            key_a = f"{date_key}_{slot}_A"
            key_b = f"{date_key}_{slot}_B"
            if key_a not in bookings and key_b not in bookings:
                has_free_slot = True
        else:
            for slot in SLOTS:
                key_a = f"{date_key}_{slot}_A"
                key_b = f"{date_key}_{slot}_B"

                if slot >= "16:00–18:00" and any(k.startswith(f"{date_key}_16:00–20:00_") for k in bookings):
                    continue

                if key_a not in bookings or key_b not in bookings:
                    has_free_slot = True
                    break

        if has_free_slot:
            weekday_idx = dt.weekday()
            day_str = f"{dt.day:02d}.{dt.month:02d} ({weekdays_ru[weekday_idx]})"
            kb.inline_keyboard.append([
                InlineKeyboardButton(
                    text=day_str,
                    callback_data=f"date:{service}:{body}:{i}"
                )
            ])

    if kb.inline_keyboard:
        await callback.message.edit_text("Выбери дату:", reply_markup=kb)
    else:
        await callback.message.edit_text("❌ Нет свободных дат.", reply_markup=None)

    await callback.answer("Вернулся к выбору даты")
    
@dp.callback_query(lambda c: c.data.startswith("slot:"))
async def book_final(callback: CallbackQuery):
    parts = callback.data.split(":")
    if len(parts) < 5:
        await callback.message.edit_text("Ошибка: неверный запрос.")
        await callback.answer()
        return

    service = parts[1]
    date_key = parts[2]
    body = parts[3]
    slot = parts[4]

    # Ключи боксов
    key_a = f"{date_key}_{slot}_A"
    key_b = f"{date_key}_{slot}_B"

    # Выбираем свободный бокс
    box = None
    if key_a not in bookings:
        box = "A"
    elif key_b not in bookings:
        box = "B"
    else:
        # Слот занят — возвращаем назад с кнопкой
        kb_back = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="⬅️ Назад к слотам",
                callback_data=f"date:{service}:{body}:0"  # 0 — сегодня, или храни day_offset
            )]
        ])
        await callback.message.edit_text(
            "❌ Слот полностью занят. Выберите другое время.",
            reply_markup=kb_back
        )
        await callback.answer()
        return

    # Сохраняем запись
    key = f"{date_key}_{slot}_{box}"
    bookings[key] = {
        "user_id": callback.from_user.id,
        "service": service,
        "body": body,
        "date": date_key,
        "slot": slot,
        "box": box
    }

    # Если керамика — блокируем остаток дня
    if service == "ceramic":
        for s in SLOTS:
            if s >= "16:00–18:00":
                for b in ["A", "B"]:
                    block_key = f"{date_key}_{s}_{b}"
                    if block_key not in bookings:
                        bookings[block_key] = {"blocked_by_ceramic": True}

    # Переход к вводу данных
    user_id = callback.from_user.id
    user_data[user_id] = {
        "service": service,
        "body": body,
        "date": date_key,
        "slot": slot,
        "box": box
    }

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ])

    await callback.message.edit_text(
        "Осталось совсем чуть-чуть! 📩\n"
        "Пришлите свои данные:\n\n"
        "• марка и модель\n"
        "• госномер\n"
        "• телефон\n"
        "• имя\n\n"
        "Всё — в одном сообщении.",
        reply_markup=kb
    )
    await callback.answer()

@dp.message()
async def save_details(message: Message):
    user_id = message.from_user.id

    if user_id not in user_data:
        return  # не в процессе записи — игнорируем

    data = user_data[user_id]

    # Разбиваем введённый текст по строкам
    text = message.text.strip()
    lines = [line.strip() for line in text.split("\n") if line.strip()]

    # Достаём данные (если строк меньше — "не указано")
    car   = lines[0] if len(lines) >= 1 else "не указано"
    plate = lines[1] if len(lines) >= 2 else "не указано"
    phone = lines[2] if len(lines) >= 3 else "не указано"
    name  = lines[3] if len(lines) >= 4 else "не указано"

    # Формируем ключ записи
    key = f"{data['date']}_{data['slot']}_{data['box']}"

    # Сохраняем в bookings
    bookings[key] = {
        "user_id": user_id,
        "service": data["service"],
        "body": data["body"],
        "date": data["date"],
        "slot": data["slot"],
        "box": data["box"],
        "car": car,
        "plate": plate,
        "phone": phone,
        "name": name
    }

    # Кнопка "Новая запись" — запускает /start заново
    kb_new = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Новая запись", callback_data="new_record")]
    ])

    # Подтверждение клиенту + кнопка "Новая запись"
    await message.answer(
        "Благодарим за обращение! 🌟\n"
        "Наш менеджер свяжется с вами для подтверждения записи.\n\n"
        f"Услуга: {SERVICE_NAMES.get(data['service'], data['service'])}\n"
        f"Кузов: {BODY_NAMES.get(data['body'], data['body'])}\n"
        f"Дата: {data['date']}\n"
        f"Время: {data['slot']} ({data['box']})\n\n"
        f"Машина: {car}\n"
        f"Госномер: {plate}\n"
        f"Телефон: {phone}\n"
        f"Имя: {name if name else 'не указано'}\n\n"
        "До встречи!",
        reply_markup=kb_new
    )

    # Уведомление админу (только на 456296772)
    await bot.send_message(
        456296772,
        "🔥 НОВАЯ ЗАПИСЬ:\n\n"
        f"Услуга: {SERVICE_NAMES.get(data['service'], data['service'])}\n"
        f"Кузов: {BODY_NAMES.get(data['body'], data['body'])}\n"
        f"Дата: {data['date']}\n"
        f"Время: {data['slot']} ({data['box']})\n\n"
        f"Машина: {car}\n"
        f"Госномер: {plate}\n"
        f"Телефон: {phone}\n"
        f"Имя: {name if name else 'не указано'}\n"
        f"ID клиента: {user_id}"
    )

    # Очищаем временные данные
    del user_data[user_id]

@dp.callback_query(lambda c: c.data == "new_record")
async def new_record(callback: CallbackQuery):
    # Запускаем выбор услуг заново
    await show_services(callback)
    await callback.answer("Новая запись начата")

async def send_reminders():
    while True:
        now = datetime.now()
        current_date = now.strftime("%Y-%m-%d")
        current_time = now.strftime("%H:%M")

        for key, booking in list(bookings.items()):
            if "blocked_by_ceramic" in booking:
                continue

            date = booking["date"]
            slot = booking["slot"]
            user_id = booking["user_id"]

            if date == current_date:
                start_time = slot.split("–")[0].strip()  # "10:00"
                remind_time = (datetime.strptime(start_time, "%H:%M") - timedelta(hours=1)).strftime("%H:%M")

                if current_time == remind_time:
                    await bot.send_message(
                        user_id,
                        f"Привет! Через час у вас запись:\n"
                        f"Услуга: {SERVICE_NAMES.get(booking['service'], booking['service'])}\n"
                        f"Кузов: {BODY_NAMES.get(booking['body'], booking['body'])}\n"
                        f"Время: {slot}\n\n"
                        f"Не опаздывайте! 🚗✨"
                    )

        await asyncio.sleep(60)


async def main():
    # Запускаем напоминания в фоне
    asyncio.create_task(send_reminders())
    
    # Запускаем бота
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
