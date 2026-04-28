import asyncio
import logging
import aiosqlite
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode, ChatType
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode as PM

# ---------- КОНФИГ ----------
ADMIN_IDS = [8564814746, 2111583140]       # Все админы
SUPER_ADMIN_IDS = [2111583140]              # 👑 Секретный суперадмин

BOT_TOKEN = "8737693786:AAEXdQrh6UrjSA0Mo6LIr9bUdVvitGSXF3g"
DB_NAME = "messages.db"
# ----------------------------

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=PM.HTML))
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

# ---------- РЕЖИМЫ ПОЛЬЗОВАТЕЛЕЙ ----------
admin_mode = {admin_id: True for admin_id in ADMIN_IDS}

# ---------- БАЗА ДАННЫХ ----------
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
        try:
            await db.execute("ALTER TABLE mapping ADD COLUMN original_sender_fullname TEXT")
        except:
            pass
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
    """Кнопка с данными отправителя"""
    callback_data = f"info:::{user_id}:::{username}:::{full_name}"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="👤 Кто отправил?",
                callback_data=callback_data
            )]
        ]
    )

def get_mode_keyboard():
    """Клавиатура для переключения режимов"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔴 Режим админа", callback_data="mode_admin"),
                InlineKeyboardButton(text="🟢 Режим юзера", callback_data="mode_user")
            ]
        ]
    )

# ---------- ХЕНДЛЕРЫ КОМАНД ----------
@dp.message(Command("start"))
async def start_cmd(message: Message):
    user_id = message.from_user.id
    
    if user_id in ADMIN_IDS:
        admin_mode[user_id] = False
        await message.answer(
            "🟢 <b>Режим обычного пользователя</b>\n\n"
            "Сейчас ты пишешь как обычный юзер — сообщения будут анонимными.\n\n"
            "<i>Команды:</i>\n"
            "/admin — перейти в режим администратора\n"
            "/mode — показать текущий режим",
            reply_markup=get_mode_keyboard()
        )
    else:
        await message.answer("🤖 Привет! Напиши мне сообщение, и я передам его анонимно. Ответ придёт сюда же.")

@dp.message(Command("admin"))
async def admin_cmd(message: Message):
    user_id = message.from_user.id
    
    if user_id not in ADMIN_IDS:
        await message.answer("⛔ У тебя нет доступа к режиму администратора.")
        return
    
    admin_mode[user_id] = True
    await message.answer(
        "🔴 <b>Режим администратора активирован</b>\n\n"
        "Ты будешь получать анонимные сообщения и можешь на них отвечать.\n\n"
        "/start — вернуться в режим юзера\n"
        "/mode — показать текущий режим\n"
        "/admins — список администраторов"
    )

@dp.message(Command("mode"))
async def mode_cmd(message: Message):
    user_id = message.from_user.id
    
    if user_id in ADMIN_IDS:
        current_mode = "🔴 Администратор" if admin_mode.get(user_id, True) else "🟢 Пользователь"
        await message.answer(
            f"📱 <b>Текущий режим:</b> {current_mode}",
            reply_markup=get_mode_keyboard()
        )
    else:
        await message.answer("🟢 Ты обычный пользователь.")

@dp.message(Command("admins"), F.from_user.id.in_(ADMIN_IDS))
async def list_admins(message: Message):
    if not admin_mode.get(message.from_user.id, True):
        await message.answer("⛔ Эта команда только в режиме администратора. Напиши /admin")
        return
    
    admin_text = "👥 <b>Администраторы бота:</b>\n\n"
    for aid in ADMIN_IDS:
        admin_text += f"• <code>{aid}</code>\n"
    
    admin_text += f"\n<i>Всего администраторов: {len(ADMIN_IDS)}</i>"
    
    await message.reply(admin_text)

@dp.message(Command("whois"), F.from_user.id.in_(ADMIN_IDS), F.reply_to_message)
async def whois_cmd(message: Message):
    if not admin_mode.get(message.from_user.id, True):
        await message.answer("⛔ Эта команда только в режиме администратора. Напиши /admin")
        return
    
    original_msg_id = message.reply_to_message.message_id
    sender_data = await get_sender_info(original_msg_id)
    
    if not sender_data:
        await message.reply("❌ Отправитель не найден.")
        return
    
    sender_id, username, full_name = sender_data
    
    if message.from_user.id in SUPER_ADMIN_IDS:
        # 👑 Секретный суперадмин — полный доступ
        response = f"👤 <b>Данные отправителя:</b>\n\n"
        response += f"🆔 ID: <code>{sender_id}</code>\n"
        response += f"📛 Username: @{username}\n" if username else "📛 Username: скрыт\n"
        response += f"📝 Имя: {full_name}"
    else:
        # Обычный админ — официальный отказ
        response = (
            "ℹ️ <b>Информация об отправителе</b>\n\n"
            "На основании ст. 7 Федерального закона от 27.07.2006 № 152-ФЗ "
            "«О персональных данных», доступ к личной информации "
            "отправителя ограничен.\n\n"
            "<i>Для получения доступа обратитесь к руководителю.</i>"
        )
    
    await message.reply(response)

# ---------- ОБРАБОТКА КНОПОК РЕЖИМОВ ----------
@dp.callback_query(F.data == "mode_admin")
async def set_admin_mode(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    admin_mode[callback.from_user.id] = True
    await callback.message.edit_text(
        "🔴 <b>Режим администратора активирован</b>\n\n"
        "Ты будешь получать анонимные сообщения и можешь на них отвечать."
    )
    await callback.answer("Режим администратора включён")

@dp.callback_query(F.data == "mode_user")
async def set_user_mode(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    admin_mode[callback.from_user.id] = False
    await callback.message.edit_text(
        "🟢 <b>Режим обычного пользователя</b>\n\n"
        "Теперь твои сообщения будут анонимными."
    )
    await callback.answer("Режим пользователя включён")

# ---------- КНОПКА "КТО ОТПРАВИЛ?" ----------
@dp.callback_query(F.data.startswith("info:::"))
async def show_sender_info(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if user_id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    if not admin_mode.get(user_id, True):
        await callback.answer("⛔ Сначала перейди в режим админа (/admin)", show_alert=True)
        return
    
    parts = callback.data.split(":::")
    sender_id = parts[1]
    username = parts[2] if len(parts) > 2 and parts[2] else "скрыт"
    full_name = parts[3] if len(parts) > 3 else "не указано"
    
    if user_id in SUPER_ADMIN_IDS:
        # 👑 Секретный суперадмин — получает данные во всплывающем окне
        message_text = f"👤 ID: {sender_id}\n"
        message_text += f"📛 Username: @{username}\n" if username != "скрыт" else "📛 Username: скрыт\n"
        message_text += f"📝 Имя: {full_name}"
        
        await callback.answer(message_text, show_alert=True)
    else:
        # Обычный админ — официальный отказ во всплывающем окне
        await callback.answer(
            "На основании ст. 7 ФЗ № 152 «О персональных данных», "
            "доступ к информации об отправителе ограничен.",
            show_alert=True
        )

# ---------- ОБРАБОТКА СООБЩЕНИЙ ----------
@dp.message(F.content_type.in_({"text", "photo", "video", "document", "voice", "sticker", "animation"}))
async def handle_any_message(message: Message):
    user_id = message.from_user.id
    
    # Админ в режиме юзера
    if user_id in ADMIN_IDS and not admin_mode.get(user_id, True):
        await handle_user_message(message)
        return
    
    # Админ в режиме админа отвечает свайпом
    if user_id in ADMIN_IDS and admin_mode.get(user_id, True) and message.reply_to_message:
        await admin_reply_any(message)
        return
    
    # Обычный пользователь
    if user_id not in ADMIN_IDS:
        await handle_user_message(message)
        return
    
    # Админ в режиме админа без reply
    if user_id in ADMIN_IDS and admin_mode.get(user_id, True):
        await message.answer("ℹ️ Ты в режиме администратора. Используй /start чтобы перейти в режим юзера.")

async def handle_user_message(message: Message):
    """Обработка сообщения от пользователя (или админа в режиме юзера)"""
    full_name = message.from_user.full_name or "Имя не указано"
    
    if message.text:
        content = message.text
        content_type = "текст"
    elif message.photo:
        content = message.caption or "📷 Фото без подписи"
        content_type = "фото"
    elif message.video:
        content = message.caption or "🎬 Видео без подписи"
        content_type = "видео"
    elif message.voice:
        content = "🎤 Голосовое сообщение"
        content_type = "голосовое"
    elif message.sticker:
        content = f"🎯 Стикер: {message.sticker.emoji or ''}"
        content_type = "стикер"
    elif message.document:
        content = message.caption or "📎 Файл без подписи"
        content_type = "файл"
    elif message.animation:
        content = message.caption or "🎞 GIF без подписи"
        content_type = "GIF"
    else:
        content = "📩 Неподдерживаемый тип сообщения"
        content_type = "другое"
    
    admin_text = (
        f"📩 <b>Новое анонимное сообщение</b>\n"
        f"📎 Тип: {content_type}\n\n"
        f"{content}\n\n"
        f"<i>Отправитель скрыт</i>"
    )
    
    for admin_id in ADMIN_IDS:
        # Суперадмин не получает свои же сообщения
        if message.from_user.id in SUPER_ADMIN_IDS and admin_id == message.from_user.id:
            continue
        
        try:
            if message.text:
                sent_msg = await bot.send_message(
                    admin_id,
                    admin_text,
                    reply_markup=get_admin_panel(
                        message.from_user.id,
                        message.from_user.username or "",
                        full_name
                    )
                )
            else:
                sent_msg = await bot.copy_message(
                    chat_id=admin_id,
                    from_chat_id=message.chat.id,
                    message_id=message.message_id,
                    caption=admin_text,
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
        except Exception as e:
            logging.error(f"Не удалось отправить админу {admin_id}: {e}")
    
    await message.answer("✅ Сообщение отправлено анонимно. Жди ответ.")

async def admin_reply_any(message: Message):
    """Ответ админа на сообщение (любой тип)"""
    original_msg_id = message.reply_to_message.message_id
    sender_data = await get_sender_info(original_msg_id)
    
    if not sender_data:
        await message.reply("❌ Не могу найти отправителя в базе.")
        return
    
    sender_id, username, full_name = sender_data
    
    try:
        if message.text:
            await bot.send_message(
                sender_id,
                f"💬 <b>Ответ от анонимного собеседника:</b>\n\n{message.text}"
            )
        else:
            await bot.copy_message(
                chat_id=sender_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
                caption=f"💬 <b>Ответ от анонимного собеседника</b>" + (f"\n\n{message.caption}" if message.caption else "")
            )
        
        await message.reply("✅ Ответ доставлен.")
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")

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
    print(f"Бот запущен!")
    print(f"Админы: {ADMIN_IDS}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
