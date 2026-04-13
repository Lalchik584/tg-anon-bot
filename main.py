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

# Важно для Render: создаём бота с настройками по умолчанию
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=PM.HTML))
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

# ---------- БАЗА ДАННЫХ ----------
async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS mapping (
                admin_message_id INTEGER PRIMARY KEY,
                original_sender_id INTEGER,
                original_sender_username TEXT
            )
        """)
        await db.commit()

async def save_mapping(admin_msg_id: int, sender_id: int, username: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO mapping VALUES (?, ?, ?)",
            (admin_msg_id, sender_id, username)
        )
        await db.commit()

async def get_sender_info(admin_msg_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT original_sender_id, original_sender_username FROM mapping WHERE admin_message_id = ?",
            (admin_msg_id,)
        ) as cursor:
            return await cursor.fetchone()

# ---------- КЛАВИАТУРА ----------
def get_admin_panel(user_id: int, username: str):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="👤 Кто отправил?",
                callback_data=f"info_{user_id}_{username}"
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

    sender_info = f"@{message.from_user.username}" if message.from_user.username else "без username"
    admin_text = (
        f"📩 <b>Новое анонимное сообщение</b>\n\n"
        f"{message.text}\n\n"
        f"<i>Отправитель скрыт</i>"
    )

    sent_msg = await bot.send_message(
        ADMIN_ID,
        admin_text,
        reply_markup=get_admin_panel(message.from_user.id, message.from_user.username or "")
    )

    await save_mapping(sent_msg.message_id, message.from_user.id, message.from_user.username or "")
    await message.answer("✅ Сообщение отправлено анонимно. Жди ответ.")

@dp.callback_query(F.data.startswith("info_"))
async def show_sender_info(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    parts = callback.data.split("_")
    user_id = parts[1]
    username = parts[2] if len(parts) > 2 else "скрыт"
    
    await callback.answer(
        f"👤 ID: {user_id}\n📛 Username: @{username}",
        show_alert=True
    )

@dp.message(F.from_user.id == ADMIN_ID, F.reply_to_message)
async def admin_reply(message: Message):
    original_msg_id = message.reply_to_message.message_id
    sender_data = await get_sender_info(original_msg_id)

    if not sender_data:
        await message.reply("❌ Не могу найти отправителя в базе.")
        return

    sender_id, username = sender_data

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
    sender_id, username = sender_data
    await message.reply(f"👤 ID: <code>{sender_id}</code>\n📛 @{username}")

# ---------- ПИНГ ДЛЯ CRON-JOB (чтобы не засыпал) ----------
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
    await run_web_server()  # запускаем веб-сервер для пинга
    print("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())