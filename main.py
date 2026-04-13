import asyncio
import logging
import aiosqlite
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode as PM

# ---------- КОНФИГ ----------
ADMIN_ID = 8564814746
BOT_TOKEN = "8737693786:AAEXdQrh6UrjSA0Mo6LIr9bUdVvitGSXF3g"
DB_NAME = "messages.db"
# ----------------------------

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=PM.HTML))
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

# ---------- БАЗА ДАННЫХ (обновлена: добавлено поле full_name) ----------
async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS mapping (
                admin_message_id INTEGER PRIMARY KEY,
                original_sender_id INTEGER,
                original_sender_username TEXT,
                original_sender_fullname TEXT
            )
        """)
        
        # Если таблица уже существовала — добавляем колонку full_name (для совместимости)
        try:
            await db.execute("ALTER TABLE mapping ADD COLUMN original_sender_fullname TEXT")
        except:
            pass  # колонка уже есть
            
        await db.commit()

async def save_mapping(admin_msg_id: int, sender_id: int, username: str, full_name: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO mapping VALUES (?, ?, ?, ?)",
            (admin_msg_id, sender_id, username, full_name)
        )
        await db.commit()

async def get_sender_info(admin_msg_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT original_sender_id, original_sender_username, original_sender_fullname FROM mapping WHERE admin_message_id = ?",
            (admin_msg_id,)
        ) as cursor:
            return await cursor.fetchone()

# ---------- КЛАВИАТУРА ----------
def get_admin_panel(user_id: int, username: str, full_name: str):
    # Передаём все данные через разделитель :::
    callback_data = f"info:::{user_id}:::{username}:::{full_name}"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="👤 Кто отправил?",
                callback_data=callback_data
            )]
        ]
    )

# ---------- ХЕНДЛЕРЫ ----------
@dp.message(Command("start"))
async def start_cmd(message: Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("⚙️ Режим администратора. Ожидаю анонимные сообщения...")
    else:
        await message.answer("🤖 Привет! Напиши мне сообщение, и я передам его анонимно. Ответ придёт сюда же.")

@dp.message(F.from_user.id != ADMIN_ID)
async def handle_user_message(message: Message):
    if not message.text:
        await message.answer("❌ Пока принимаю только текст. Отправь текстовое сообщение.")
        return

    # Собираем полное имя
    full_name = message.from_user.full_name or "Имя не указано"
    
    admin_text = (
        f"📩 <b>Новое анонимное сообщение</b>\n\n"
        f"{message.text}\n\n"
        f"<i>Для ответа свайпни вслево!</i>"
    )

    sent_msg = await bot.send_message(
        ADMIN_ID,
        admin_text,
        reply_markup=get_admin_panel(
            message.from_user.id, 
            message.from_user.username or "", 
            full_name
        )
    )

    await save_mapping(
        sent_msg.message_id, 
        message.from_user.id, 
        message.from_user.username or "", 
        full_name
    )
    await message.answer("✅ Сообщение отправлено анонимно. Жди ответ.")

@dp.callback_query(F.data.startswith("info:::"))
async def show_sender_info(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    parts = callback.data.split(":::")
    user_id = parts[1]
    username = parts[2] if len(parts) > 2 and parts[2] else "скрыт"
    full_name = parts[3] if len(parts) > 3 else "не указано"
    
    # Формируем красивое сообщение
    message_text = f"👤 ID: {user_id}\n"
    message_text += f"📛 Username: @{username}\n" if username != "скрыт" else "📛 Username: скрыт\n"
    message_text += f"📝 Имя: {full_name}"
    
    await callback.answer(message_text, show_alert=True)

@dp.message(F.from_user.id == ADMIN_ID, F.reply_to_message)
async def admin_reply(message: Message):
    original_msg_id = message.reply_to_message.message_id
    sender_data = await get_sender_info(original_msg_id)

    if not sender_data:
        await message.reply("❌ Не могу найти отправителя в базе.")
        return

    sender_id, username, full_name = sender_data

    try:
        await bot.send_message(
            sender_id,
            f"💬 <b>Ответ от анонимного собеседника:</b>\n\n{message.text}"
        )
        await message.reply("✅ Ответ доставлен.")
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")

@dp.message(Command("whois"), F.from_user.id == ADMIN_ID, F.reply_to_message)
async def whois_cmd(message: Message):
    sender_data = await get_sender_info(message.reply_to_message.message_id)
    if not sender_data:
        await message.reply("❌ Отправитель не найден.")
        return
    
    sender_id, username, full_name = sender_data
    
    response = f"👤 <b>Информация об отправителе:</b>\n"
    response += f"🆔 ID: <code>{sender_id}</code>\n"
    response += f"📛 Username: @{username}\n" if username else "📛 Username: скрыт\n"
    response += f"📝 Имя: {full_name}"
    
    await message.reply(response)

# ---------- ПИНГ ДЛЯ CRON-JOB ----------
from aiohttp import web

async def handle_ping(request):
    return web.Response(text="OK")

async def run_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 10000)
    await site.start()
    print("Web server started on port 10000")

async def main():
    await init_db()
    await run_web_server()
    print("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
