import telebot
import random
import json
import os
import time
from datetime import date
from telebot import apihelper
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ═══════════════════════════════════════════════
# НАСТРОЙКИ
# ═══════════════════════════════════════════════
TOKEN = os.getenv("BOT_TOKEN", "").strip()
if not TOKEN:
    raise RuntimeError("Укажи BOT_TOKEN в переменных окружения Termux.")
SERVER_URL = os.getenv("MECHAGRAM_SERVER_URL", "http://177.3.213.27:8081").rstrip("/")
apihelper.API_URL = f"{SERVER_URL}/bot{{0}}/{{1}}"
apihelper.FILE_URL = f"{SERVER_URL}/file/bot{{0}}/{{1}}"
bot = telebot.TeleBot(TOKEN)

DB_FILE = "nft_casino_data.json"
BOT_USERNAME = os.getenv("BOT_USERNAME", "").strip().lstrip("@")
ADMIN_SECRET_CODE = os.getenv("ADMIN_SECRET_CODE", "").strip()
ADMIN_SESSIONS = set()
PROMO_CHANNEL = "@lukiiii"
TESTER_IDS = {1780249850, 1780266108}
PUBLIC_LAUNCH_DATE = date(2026, 11, 1)

def is_admin(user_id):
    return int(user_id) in ADMIN_SESSIONS

def has_full_access(user_id):
    return int(user_id) in TESTER_IDS or date.today() >= PUBLIC_LAUNCH_DATE

def launch_stub():
    return "🔒 NFT-Casino пока закрыт на тестирование.\n\n🎉 Официальное открытие — 01.11.2026.\nДо открытия полный доступ есть только у тестеров."

# ═══════════════════════════════════════════════
# БАЗА
# ═══════════════════════════════════════════════
def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if "users" not in data: data["users"] = {}
            if "promos" not in data: data["promos"] = {"START": {"type": "tokens", "amount": 1000}}
            if "waiting_step" not in data: data["waiting_step"] = {}
            if "pending_data" not in data: data["pending_data"] = {}
            if "processed_payments" not in data: data["processed_payments"] = []
            if "maintenance" not in data: data["maintenance"] = False
            return data
        except Exception: pass
    return {"users": {}, "promos": {"START": {"type": "tokens", "amount": 1000}}, "waiting_step": {}, "pending_data": {}, "processed_payments": [], "maintenance": False}

def save_db(db):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

db = load_db()

def get_user(uid):
    uid = str(uid)
    if uid not in db["users"]:
        db["users"][uid] = {
            "balance": 1000, "wins": 0, "deaths": 0, "username": None,
            "used_promos": [], "nfts": [], "gifts": [],
            "last_bonus": 0
        }
        save_db(db)
    u = db["users"][uid]
    if "nfts" not in u: u["nfts"] = []
    if "gifts" not in u: u["gifts"] = []
    if "used_promos" not in u: u["used_promos"] = []
    if "inventory" not in u: u["inventory"] = {}
    return u

# ═══════════════════════════════════════════════
# КЛАВИАТУРЫ
# ═══════════════════════════════════════════════
def main_menu():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("📦 Кейсы", callback_data="menu_cases"),
        InlineKeyboardButton("🔐 Секретный код", callback_data="secret_code"),
        InlineKeyboardButton("🏆 Топ игроков", callback_data="top_menu"),
        InlineKeyboardButton("👤 Мой профиль", callback_data="profile"),
        InlineKeyboardButton("💰 Пополнение", callback_data="menu_deposit"),
        InlineKeyboardButton("💸 Вывод", callback_data="menu_withdraw")
    )
    return kb

CASES = {
    "empty": {"name": "📦 Обычный кейс", "price": 100, "nft_chance": 0.001, "nfts": ["NFT #1"]},
    "cobra": {"name": "🐍 Кейс Кобры", "price": 500, "nft_chance": 0.003, "nfts": ["🐍 Кобра NFT #1", "🐍 Кобра NFT #2"]},
    "dragon": {"name": "🐉 Кейс Дракона", "price": 1000, "nft_chance": 0.005, "nfts": ["🐉 Дракон NFT #1", "🐉 Дракон NFT #2", "🐉 Дракон NFT #3"]},
    "win": {"name": "🏆 WIN кейс", "price": 1500, "nft_chance": 0.007, "nfts": ["🏆 WIN NFT #1", "🏆 WIN NFT #2", "🏆 WIN NFT #3", "🏆 WIN NFT #4"]},
    "luki": {"name": "👑 LUKI кейс", "price": 2000, "nft_chance": 0.01, "nfts": ["👑 LUKI NFT #1", "👑 LUKI NFT #2", "👑 LUKI NFT #3", "👑 LUKI NFT #4", "👑 LUKI NFT #5"]}
}

GIFT_CHANCE = 0.20

def cases_menu():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("📦 Обычный кейс — 100 токенов", callback_data="case_info_empty"))
    kb.add(InlineKeyboardButton("🐍 Кейс Кобры — 500 токенов", callback_data="case_info_cobra"))
    kb.add(InlineKeyboardButton("🐉 Кейс Дракона — 1000 токенов", callback_data="case_info_dragon"))
    kb.add(InlineKeyboardButton("🏆 WIN кейс — 1500 токенов", callback_data="case_info_win"))
    kb.add(InlineKeyboardButton("👑 LUKI кейс — 2000 токенов", callback_data="case_info_luki"))
    kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="refresh"))
    return kb

def back_kb():
    return InlineKeyboardMarkup().add(InlineKeyboardButton("⬅️ Назад", callback_data="refresh"))

# ═══════════════════════════════════════════════
# ХЕЛПЕРЫ
# ═══════════════════════════════════════════════
def safe_answer(call, text=None, show_alert=False):
    try: bot.answer_callback_query(call.id, text=text, show_alert=show_alert)
    except Exception: pass

def safe_send(chat_id, text, markup=None):
    try: return bot.send_message(chat_id, text, reply_markup=markup)
    except Exception: return None

def safe_edit(chat_id, message_id, text, markup=None):
    try: bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup)
    except Exception: pass

# ═══════════════════════════════════════════════
# ОГРАНИЧЕНИЕ ДО ПУБЛИЧНОГО ЗАПУСКА
# ═══════════════════════════════════════════════
@bot.message_handler(func=lambda m: db.get("maintenance", False) and not is_admin(m.from_user.id) and (m.text or "") != "/admin")
def maintenance_message(message):
    safe_send(message.chat.id, "🛠 NFT-Casino временно закрыт на технические работы. Попробуй зайти позже.")

@bot.callback_query_handler(func=lambda c: db.get("maintenance", False) and not is_admin(c.from_user.id))
def maintenance_callback(call):
    safe_answer(call, "🛠 Бот временно закрыт на технические работы.", show_alert=True)

@bot.callback_query_handler(func=lambda c: not has_full_access(c.from_user.id))
def closed_callback(call):
    safe_answer(call, "Бот пока закрыт на тестирование.", show_alert=True)
    safe_edit(call.message.chat.id, call.message.message_id, launch_stub())

@bot.message_handler(func=lambda m: not has_full_access(m.from_user.id) and not (m.text or "").startswith("/start"))
def closed_message(message):
    safe_send(message.chat.id, launch_stub())

# ═══════════════════════════════════════════════
# /start
# ═══════════════════════════════════════════════
@bot.message_handler(commands=["start"])
def start(message):
    if not has_full_access(message.from_user.id):
        return safe_send(message.chat.id, launch_stub())
    u = get_user(message.from_user.id)
    u["username"] = message.from_user.username or message.from_user.first_name
    save_db(db)
    text = ("Привет! Я игровой бот Casino! 👋\n\n"
            "Открывай кейсы, получай НФТ и подарки!\n"
            f"💵 Твой баланс: {u['balance']}")
    safe_send(message.chat.id, text, main_menu())

# ═══════════════════════════════════════════════
# КЕЙСЫ
# ═══════════════════════════════════════════════
@bot.callback_query_handler(func=lambda c: c.data == "menu_cases")
def menu_cases(call):
    safe_answer(call)
    safe_edit(call.message.chat.id, call.message.message_id, "📦 ВЫБЕРИ КЕЙС:", cases_menu())

@bot.callback_query_handler(func=lambda c: c.data.startswith("case_info_"))
def show_case_info(call):
    case_type = call.data.replace("case_info_", "")
    case = CASES.get(case_type)
    if not case:
        return safe_answer(call, "Кейс не найден.", show_alert=True)

    nft_percent = f"{case['nft_chance'] * 100:g}%"
    text = (
        f"{case['name']}\n\n"
        f"💰 Цена: {case['price']} токенов\n"
        f"🎒 NFT в коллекции кейса: {len(case['nfts'])}\n"
        f"💎 Шанс получить NFT: {nft_percent}\n"
        f"🎁 Шанс обычного подарка: 20%\n\n"
        "NFT и обычный подарок могут выпасть одновременно."
    )
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("🎲 Купить и открыть", callback_data=f"buy_case_{case_type}"))
    kb.add(InlineKeyboardButton("⬅️ Назад к кейсам", callback_data="menu_cases"))
    safe_answer(call)
    safe_edit(call.message.chat.id, call.message.message_id, text, kb)


@bot.callback_query_handler(func=lambda c: c.data.startswith("buy_case_"))
def open_case(call):
    case_type = call.data.replace("buy_case_", "")
    case = CASES.get(case_type)
    if not case:
        return safe_answer(call, "Кейс не найден.", show_alert=True)

    user = get_user(call.from_user.id)
    price = case["price"]
    if user["balance"] < price:
        return safe_answer(call, f"❌ Нужно {price} токенов!", show_alert=True)

    safe_answer(call, "🎲 Открываем...")
    msg = safe_send(call.message.chat.id, "🔄 Крутим барабаны...")
    if not msg:
        return

    user["balance"] -= price
    save_db(db)

    frames = ["🎰 [ 🍒 | 🍋 | 🔔 ]", "🎰 [ 💎 | 7️⃣ | 🍒 ]", "🎰 [ 🔔 | 💎 | 🍋 ]"]
    for frame in frames:
        time.sleep(0.4)
        safe_edit(msg.chat.id, msg.message_id, frame)
    time.sleep(0.4)

    result_text = f"{case['name']}\n\n"
    if random.random() < case["nft_chance"]:
        won_nft = random.choice(case["nfts"])
        user["nfts"].append(won_nft)
        result_text += f"🎉 Тебе выпал NFT: {won_nft}"
    else:
        result_text += "😢 NFT не выпало. Попробуй ещё раз!"

    gift_message = None
    if random.random() < GIFT_CHANCE:
        gift = random.choice(["🎁 Подарок 1", "🎀 Подарок 2", "🧸 Подарок 3"])
        user["gifts"].append(gift)
        gift_message = f"🎁 Вам выпал подарок из Telegram: {gift}"

    save_db(db)
    safe_edit(msg.chat.id, msg.message_id, result_text + f"\n\n💵 Баланс: {user['balance']}", cases_menu())

    # Отдельное уведомление о подарке приходит после завершения анимации и результата кейса.
    if gift_message:
        time.sleep(1.5)
        safe_send(call.message.chat.id, gift_message)

# ═══════════════════════════════════════════════
# ПРОЧЕЕ
# ═══════════════════════════════════════════════
@bot.callback_query_handler(func=lambda c: c.data == "refresh")
def refresh(call):
    safe_answer(call)
    u = get_user(call.from_user.id)
    text = ("Привет! Я игровой бот Casino! 👋\n\n"
            f"💵 Твой баланс: {u['balance']}")
    safe_edit(call.message.chat.id, call.message.message_id, text, main_menu())
  # ═══════════════════════════════════════════════
# АДМИН-ПАНЕЛЬ
# ═══════════════════════════════════════════════
def admin_keyboard():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("➕ Промокод на токены", callback_data="adm_create_tokens"),
        InlineKeyboardButton("🎁 Промокод на предмет", callback_data="adm_create_item"),
        InlineKeyboardButton("📋 Список промокодов", callback_data="adm_list_promos"),
        InlineKeyboardButton("❌ Удалить промокод", callback_data="adm_delete_promo"),
        InlineKeyboardButton("📣 Рассылка всем игрокам", callback_data="adm_broadcast"),
        InlineKeyboardButton("🔒 Закрыть бота на техработы" if not db.get("maintenance", False) else "🔓 Открыть бота после техработ", callback_data="adm_toggle_maintenance")
    )
    return kb

def require_admin_call(call):
    if not is_admin(call.from_user.id):
        safe_answer(call, "⛔ Нет доступа.", show_alert=True)
        return False
    return True

@bot.message_handler(commands=["admin"])
def admin_panel(message):
    if not ADMIN_SECRET_CODE:
        return safe_send(message.chat.id, "⚠️ Админ-код не настроен в Termux.")
    if is_admin(message.from_user.id):
        return safe_send(message.chat.id, "👑 АДМИН-ПАНЕЛЬ", admin_keyboard())
    sent = safe_send(message.chat.id, "🔐 Введи секретный код:")
    if sent:
        bot.register_next_step_handler(sent, admin_check)

def admin_check(message):
    if not message.text or message.text.strip() != ADMIN_SECRET_CODE:
        return safe_send(message.chat.id, "❌ Неверный код.")
    ADMIN_SESSIONS.add(int(message.from_user.id))
    safe_send(message.chat.id, "✅ Доступ разрешён.\n👑 АДМИН-ПАНЕЛЬ", admin_keyboard())

@bot.callback_query_handler(func=lambda c: c.data.startswith("adm_"))
def admin_actions(call):
    if not require_admin_call(call):
        return
    data = call.data
    safe_answer(call)
    if data == "adm_create_tokens":
        sent = safe_send(call.message.chat.id, "Введи: КОД СУММА. Например: WIN500 500")
        if sent: bot.register_next_step_handler(sent, adm_process_tokens)
    elif data == "adm_create_item":
        kb = InlineKeyboardMarkup(row_width=1)
        kb.add(
            InlineKeyboardButton("🎁 Обычный подарок", callback_data="adm_item_gift"),
            InlineKeyboardButton("💎 NFT из коллекции кейсов", callback_data="adm_item_nft")
        )
        safe_send(call.message.chat.id, "Выбери награду промокода:", kb)
    elif data in ("adm_item_gift", "adm_item_nft"):
        item_type = data.replace("adm_item_", "")
        sent = safe_send(
            call.message.chat.id,
            "Введи: КОД КОЛИЧЕСТВО. Например: GIFT5 5\n"
            + ("Будет выдан случайный обычный подарок." if item_type == "gift" else "Будет выдан случайный NFT из коллекции кейсов.")
        )
        if sent: bot.register_next_step_handler(sent, adm_process_item, item_type)
    elif data == "adm_list_promos":
        lines = ["📋 ПРОМОКОДЫ:"]
        for code, promo in db["promos"].items():
            lines.append(f"{code} — {promo.get('amount', 0)}")
        safe_send(call.message.chat.id, "\n".join(lines), admin_keyboard())
    elif data == "adm_delete_promo":
        sent = safe_send(call.message.chat.id, "Введи код для удаления:")
        if sent: bot.register_next_step_handler(sent, adm_process_delete)
    elif data == "adm_broadcast":
        sent = safe_send(call.message.chat.id, "Отправь текст сообщения для всех игроков:")
        if sent: bot.register_next_step_handler(sent, adm_process_broadcast)
    elif data == "adm_toggle_maintenance":
        db["maintenance"] = not db.get("maintenance", False)
        save_db(db)
        state = "закрыт на техработы" if db["maintenance"] else "снова открыт"
        safe_send(call.message.chat.id, "✅ Бот " + state + ".", admin_keyboard())

def publish_promo(code, promo, chat_id):
    if promo["type"] == "tokens":
        reward = str(promo.get("amount", 0)) + " токенов"
    elif promo["type"] == "gift":
        reward = str(promo.get("amount", 0)) + " обычных подарков"
    elif promo["type"] == "nft":
        reward = str(promo.get("amount", 0)) + " NFT (случайные из коллекции кейсов)"
    else:
        reward = str(promo.get("amount", 0)) + " предмет(ов)"
    announcement = "🎁 ПРОМОКОД NFT-Casino\n\n🔑 Код: " + code + "\n🏆 Награда: " + reward + "\n\nАктивируй код в боте через меню «Секретный код»."
    posted = safe_send(PROMO_CHANNEL, announcement)
    if posted:
        safe_send(chat_id, "✅ Промокод создан и опубликован в https://t.me/lukiiii\n\n" + announcement)
    else:
        safe_send(chat_id, "⚠️ Промокод создан, но публикация в канале не удалась. Добавь бота администратором @lukiiii с правом публикации.\n\nТекст для канала:\n" + announcement)

def adm_process_tokens(message):
    if not is_admin(message.from_user.id): return
    parts = (message.text or "").split()
    if len(parts) != 2: return safe_send(message.chat.id, "Формат: КОД СУММА.")
    code = parts[0].upper()
    try: amount = int(parts[1])
    except ValueError: return safe_send(message.chat.id, "Сумма должна быть числом.")
    if not code.isalnum() or amount <= 0: return safe_send(message.chat.id, "Код — латинские буквы/цифры, сумма больше нуля.")
    if code in db["promos"]: return safe_send(message.chat.id, "Такой промокод уже существует.")
    promo = {"type": "tokens", "amount": amount}
    db["promos"][code] = promo
    save_db(db)
    publish_promo(code, promo, message.chat.id)

def adm_process_item(message, item_type):
    if not is_admin(message.from_user.id): return
    parts = (message.text or "").split()
    if len(parts) != 2: return safe_send(message.chat.id, "Формат: КОД КОЛИЧЕСТВО.")
    code = parts[0].upper()
    try: amount = int(parts[1])
    except ValueError: return safe_send(message.chat.id, "Количество должно быть числом.")
    if not code.isalnum() or amount <= 0: return safe_send(message.chat.id, "Код — латинские буквы/цифры, количество больше нуля.")
    if code in db["promos"]: return safe_send(message.chat.id, "Такой промокод уже существует.")
    if item_type not in ("gift", "nft"):
        return safe_send(message.chat.id, "Неизвестный тип награды.")
    promo = {"type": item_type, "amount": amount}
    db["promos"][code] = promo
    save_db(db)
    publish_promo(code, promo, message.chat.id)

def adm_process_delete(message):
    if not is_admin(message.from_user.id): return
    code = (message.text or "").strip().upper()
    if code in db["promos"]:
        del db["promos"][code]
        save_db(db)
        safe_send(message.chat.id, "Промокод удалён.", admin_keyboard())
    else:
        safe_send(message.chat.id, "Промокод не найден.")

def adm_process_broadcast(message):
    if not is_admin(message.from_user.id): return
    body = (message.text or "").strip()
    if not body: return safe_send(message.chat.id, "Пустое сообщение. Рассылка отменена.")
    sent_count = 0
    failed_count = 0
    for uid in list(db.get("users", {}).keys()):
        result = safe_send(int(uid), body)
        if result: sent_count += 1
        else: failed_count += 1
        time.sleep(0.05)
    safe_send(message.chat.id, "📣 Рассылка завершена.\nДоставлено: " + str(sent_count) + "\nНе доставлено: " + str(failed_count), admin_keyboard())

# ═══════════════════════════════════════════════
# ПРОМОКОДЫ (ИГРОК)
# ═══════════════════════════════════════════════
@bot.callback_query_handler(func=lambda c: c.data == "secret_code")
def secret_code(call):
    safe_answer(call)
    safe_edit(call.message.chat.id, call.message.message_id, "🔐 Введи код:", back_kb())
    bot.register_next_step_handler(call.message, process_promo)

def process_promo(message):
    if message.text.startswith("/"): return
    code = message.text.strip().upper()
    user = get_user(message.from_user.id)
    
    if code not in db["promos"]: return safe_send(message.chat.id, "❌ Неверный код.", main_menu())
    if code in user.get("used_promos", []): return safe_send(message.chat.id, "❌ Уже активирован.", main_menu())
    
    promo = db["promos"][code]
    if promo["type"] == "tokens":
        user["balance"] += promo["amount"]
        reward_text = f"+{promo['amount']} токенов"
    elif promo["type"] == "gift":
        gifts = ["🎁 Подарок 1", "🎀 Подарок 2", "🧸 Подарок 3"]
        won_gifts = [random.choice(gifts) for _ in range(promo["amount"])]
        user.setdefault("gifts", []).extend(won_gifts)
        reward_text = f"+{promo['amount']} обычных подарков: " + ", ".join(won_gifts)
    elif promo["type"] == "nft":
        nft_pool = [nft for case in CASES.values() for nft in case["nfts"]]
        won_nfts = [random.choice(nft_pool) for _ in range(promo["amount"])]
        user.setdefault("nfts", []).extend(won_nfts)
        reward_text = f"+{promo['amount']} NFT: " + ", ".join(won_nfts)
    elif promo["type"] == "item":
        # Поддержка старых промокодов, созданных до обновления.
        item = promo["item"]
        user.setdefault("inventory", {})
        user["inventory"][item] = user["inventory"].get(item, 0) + promo["amount"]
        names = {"xray": "Рентген", "pill": "Таблетка", "angel": "Зелье ангела"}
        reward_text = f"+{promo['amount']} шт. {names.get(item, item)}"
        
    user.setdefault("used_promos", []).append(code)
    save_db(db)
    safe_send(message.chat.id, f"✅ Активирован! Награда: {reward_text}\n💵 Баланс: {user['balance']}", main_menu())

# ═══════════════════════════════════════════════
# ПРОФИЛЬ, ТОП, ВЫВОД, ПОПОЛНЕНИЕ
# ═══════════════════════════════════════════════
@bot.callback_query_handler(func=lambda c: c.data == "profile")
def profile(call):
    safe_answer(call)
    u = get_user(call.from_user.id)
    txt = (f"👤 ПРОФИЛЬ\n🆔 `{call.from_user.id}`\n💵 Баланс: {u['balance']}\n"
           f"🎒 НФТ: {len(u['nfts'])} шт.\n🎁 Подарков: {len(u['gifts'])} шт.")
    safe_edit(call.message.chat.id, call.message.message_id, txt, back_kb())

@bot.callback_query_handler(func=lambda c: c.data == "top_menu")
def top_menu_cb(call):
    safe_answer(call)
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🪙 По токенам", callback_data="top_tokens"),
        InlineKeyboardButton("🎒 По НФТ", callback_data="top_nfts")
    )
    kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="refresh"))
    safe_edit(call.message.chat.id, call.message.message_id, "🏆 ТОП ИГРОКОВ\nВыбери категорию:", kb)

@bot.callback_query_handler(func=lambda c: c.data in ("top_tokens", "top_nfts"))
def show_top(call):
    safe_answer(call)
    sort_by = "balance" if call.data == "top_tokens" else "nfts"
    all_users = list(db["users"].items())
    if sort_by == "nfts":
        all_users.sort(key=lambda x: len(x[1].get("nfts", [])), reverse=True)
    else:
        all_users.sort(key=lambda x: x[1].get("balance", 0), reverse=True)
    
    title = "🪙 ПО ТОКЕНАМ" if sort_by == "balance" else "🎒 ПО НФТ"
    lines = [f"🏆 {title}:\n"]
    for i, (uid, info) in enumerate(all_users[:10], 1):
        name = info.get('username') or uid
        val = info.get('balance', 0) if sort_by == "balance" else len(info.get('nfts', []))
        lines.append(f"{i}. {name} — {val}")
    
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("⬅️ Назад", callback_data="top_menu"))
    safe_edit(call.message.chat.id, call.message.message_id, "\n".join(lines), kb)

@bot.callback_query_handler(func=lambda c: c.data == "menu_withdraw")
def menu_withdraw(call):
    safe_answer(call)
    user = get_user(call.from_user.id)
    if user.get("nfts"):
        txt = ("💸 ВЫВОД НФТ\n\n"
               "Сейчас вывести нфт нельзя из-за банкрота @lukii но вы можете поддержать его путь с 0\n\n"
               "Вывод станет доступен в ближайшем времени🎯\n\n"
               "Но ты можешь вывести обычные гифти!")
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🎁 Вывести подарки", callback_data="withdraw_gifts"))
        kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="refresh"))
        safe_edit(call.message.chat.id, call.message.message_id, txt, kb)
    else:
        safe_edit(call.message.chat.id, call.message.message_id, "💸 У тебя нет НФТ для вывода.", back_kb())

@bot.callback_query_handler(func=lambda c: c.data == "withdraw_gifts")
def withdraw_gifts(call):
    safe_answer(call)
    user = get_user(call.from_user.id)
    if not user.get("gifts"):
        return safe_edit(call.message.chat.id, call.message.message_id, "🎁 У тебя нет подарков для вывода.", back_kb())
    txt = f"🎁 Твои подарки: {', '.join(user['gifts'])}\n\nВведи, какие подарки хочешь вывести (или `Все`):"
    safe_edit(call.message.chat.id, call.message.message_id, txt, back_kb())
    bot.register_next_step_handler(call.message, process_withdraw_gifts)

def process_withdraw_gifts(message):
    user = get_user(message.from_user.id)
    text = message.text.strip()
    if not user.get("gifts"):
        return safe_send(message.chat.id, "🎁 Нет подарков.", main_menu())
    
    if text.lower() == "все":
        gifts_to_withdraw = user["gifts"]
    else:
        gifts_to_withdraw = [g for g in user["gifts"] if g.lower() in text.lower()]
        if not gifts_to_withdraw:
            return safe_send(message.chat.id, "❌ Ты не указал ни одного подарка.", main_menu())
            
    report_text = (f"🎁 ЗАЯВКА НА ВЫВОД ПОДАРКОВ\n\n"
                   f"👤 От: @{message.from_user.username} (ID: `{message.from_user.id}`)\n"
                   f"🎁 Выводит: {', '.join(gifts_to_withdraw)}\n"
                   f"📊 Всего: {len(gifts_to_withdraw)} шт.")
    safe_send(123456789, report_text) # ЗАМЕНИ 123456789 НА СВОЙ ID
    safe_send(message.chat.id, "✅ Заявка на вывод подарков отправлена админу.", main_menu())

@bot.callback_query_handler(func=lambda c: c.data == "menu_deposit")
def menu_deposit(call):
    safe_answer(call)
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("💬 @winlose — Гл. разработчик", url="https://t.me/winlose"),
        InlineKeyboardButton("💬 @Lukii — Админ", url="https://t.me/Lukii"),
        InlineKeyboardButton("⬅️ Назад", callback_data="refresh")
    )
    safe_edit(call.message.chat.id, call.message.message_id, "💰 ПОПОЛНЕНИЕ\nВыбери способ:", kb)

# ═══════════════════════════════════════════════
# ЗАПУСК
# ═══════════════════════════════════════════════
if __name__ == "__main__":
    print("🚀 CASINO BOT запущен...")
    bot.infinity_polling()
