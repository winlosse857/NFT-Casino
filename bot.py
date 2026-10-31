import telebot
import random
import json
import os
import time
from datetime import date
from telebot import apihelper
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice

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

DB_FILE = "casino_db.json"
BOT_USERNAME = os.getenv("BOT_USERNAME", "").strip().lstrip("@")
ADMIN_SECRET_CODE = os.getenv("ADMIN_SECRET_CODE", "").strip()
SHOP_UPDATE_INTERVAL = 15 * 60
TESTER_IDS = {1780249850, 1780266108}
PUBLIC_LAUNCH_DATE = date(2026, 11, 1)
STARS_PACKAGES = {"stars_100": {"stars": 100, "tokens": 100}, "stars_250": {"stars": 250, "tokens": 250}, "stars_500": {"stars": 500, "tokens": 500}, "stars_1000": {"stars": 1000, "tokens": 1000}}

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
            if "shop_stock" not in data: data["shop_stock"] = {}
            if "shop_timer" not in data: data["shop_timer"] = 0
            if "waiting_step" not in data: data["waiting_step"] = {}
            if "pending_data" not in data: data["pending_data"] = {}
            if "processed_payments" not in data: data["processed_payments"] = []
            return data
        except Exception: pass
    return {"users": {}, "promos": {"START": {"type": "tokens", "amount": 1000}}, "shop_stock": {}, "shop_timer": 0, "waiting_step": {}, "pending_data": {}, "processed_payments": []}

def save_db(db):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

db = load_db()

def update_shop_stock():
    now = int(time.time())
    if now - db.get("shop_timer", 0) >= SHOP_UPDATE_INTERVAL or not db.get("shop_stock"):
        stock = {}
        if random.random() < 0.8: stock["case_empty"] = random.randint(5, 20)
        if random.random() < 0.6: stock["case_small"] = random.randint(2, 10)
        if random.random() < 0.3: stock["case_medium"] = random.randint(1, 3)
        db["shop_stock"] = stock
        db["shop_timer"] = now
        save_db(db)

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
        InlineKeyboardButton("🎮 Мини-игры", callback_data="mini_games_menu"),
        InlineKeyboardButton("🛒 Магазин", callback_data="shop_menu"),
        InlineKeyboardButton("🔐 Секретный код", callback_data="secret_code"),
        InlineKeyboardButton("🏆 Топ игроков", callback_data="top_menu"),
        InlineKeyboardButton("👤 Мой профиль", callback_data="profile"),
        InlineKeyboardButton("💰 Пополнение", callback_data="menu_deposit"),
        InlineKeyboardButton("💸 Вывод", callback_data="menu_withdraw")
    )
    return kb

def shop_menu():
    update_shop_stock()
    stock = db["shop_stock"]
    kb = InlineKeyboardMarkup(row_width=1)
    if stock.get("case_empty", 0) > 0:
        kb.add(InlineKeyboardButton(f"📦 Кейс без НФТ (осталось: {stock['case_empty']}) — 100", callback_data="open_case_empty"))
    if stock.get("case_small", 0) > 0:
        kb.add(InlineKeyboardButton(f"🎁 Малый кейс — шанс НФТ 35% (осталось: {stock['case_small']}) — 500", callback_data="open_case_small"))
    if stock.get("case_medium", 0) > 0:
        kb.add(InlineKeyboardButton(f"💎 Средний кейс — шанс НФТ 70% (осталось: {stock['case_medium']}) — 1500", callback_data="open_case_medium"))
    kb.add(InlineKeyboardButton("🔄 Обновить магазин", callback_data="shop_menu"))
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
    safe_edit(call.message.chat.id, call.message.message_id, "📦 ВЫБЕРИ КЕЙС:", shop_menu())

@bot.callback_query_handler(func=lambda c: c.data.startswith("open_case_"))
def open_case(call):
    case_type = call.data.replace("open_case_", "")
    user = get_user(call.from_user.id)
    update_shop_stock()
    
    prices = {"empty": 100, "small": 500, "medium": 1500}
    names = {"empty": "📦 Кейс без НФТ", "small": "🎁 Кейс 1-2 НФТ", "medium": "💎 Кейс 4 НФТ"}
    stock_key = f"case_{case_type}"
    
    if db["shop_stock"].get(stock_key, 0) <= 0:
        return safe_answer(call, "❌ Кейс закончился! Жди обновления.", show_alert=True)
    
    price = prices[case_type]
    if user["balance"] < price:
        return safe_answer(call, f"❌ Нужно {price} токенов!", show_alert=True)
    
    safe_answer(call, "🎲 Открываем...")
    msg = safe_send(call.message.chat.id, "🔄 Крутим барабаны...")
    if not msg:
        return

    user["balance"] -= price
    db["shop_stock"][stock_key] -= 1
    save_db(db)
    
    frames = ["🎰 [ 🍒 | 🍋 | 🔔 ]", "🎰 [ 💎 | 7️⃣ | 🍒 ]", "🎰 [ 🔔 | 💎 | 🍋 ]"]
    for f in frames:
        time.sleep(0.4)
        safe_edit(msg.chat.id, msg.message_id, f)
    time.sleep(0.4)
    
    result_text = f"{names[case_type]}\n\n"
    if case_type == "empty":
        result_text += "😢 Пусто. НФТ не выпало."
    else:
        nft_chance = {"small": 0.35, "medium": 0.70}[case_type]
        if random.random() < nft_chance:
            count = random.randint(1, 2) if case_type == "small" else 4
            nft_pool = [f"NFT #{i}" for i in range(1, 21)]
            won = random.sample(nft_pool, count)
            user["nfts"].extend(won)
            result_text += f"🎉 Выпало {len(won)} НФТ:\n" + "\n".join(f"  • {n}" for n in won)
        else:
            result_text += "😢 НФТ не выпало. Попробуй ещё раз!"
    
    if random.random() < 0.2:
        gift = random.choice(["🎁 Подарок 1", "🎀 Подарок 2", "🧸 Подарок 3"])
        user["gifts"].append(gift)
        result_text += f"\n🎁 Бонус! Выпал обычный подарок: {gift}"
    
    save_db(db)
    safe_edit(msg.chat.id, msg.message_id, result_text + f"\n\n💵 Баланс: {user['balance']}", shop_menu())

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
@bot.message_handler(commands=["admin"])
def admin_panel(message):
    bot.send_message(message.chat.id, "🔐 Введи секретный код:")
    bot.register_next_step_handler(message, admin_check)

def admin_check(message):
    if message.text.strip() == ADMIN_SECRET_CODE:
        kb = InlineKeyboardMarkup(row_width=1)
        kb.add(
            InlineKeyboardButton("➕ Промокод на Токены", callback_data="adm_create_tokens"),
            InlineKeyboardButton("🎁 Промокод на Предмет", callback_data="adm_create_item"),
            InlineKeyboardButton("📋 Список промокодов", callback_data="adm_list_promos"),
            InlineKeyboardButton("❌ Удалить промокод", callback_data="adm_delete_promo")
        )
        bot.send_message(message.chat.id, "👑 АДМИН-ПАНЕЛЬ", reply_markup=kb)
    else:
        bot.send_message(message.chat.id, "❌ Неверный код.")

@bot.callback_query_handler(func=lambda c: c.data == "adm_create_tokens")
def adm_create_tokens(call):
    safe_answer(call)
    bot.send_message(call.message.chat.id, "Введи: `КОД СУММА`\nПример: `WIN 500`")
    bot.register_next_step_handler(call.message, adm_process_tokens)

def adm_process_tokens(message):
    parts = message.text.split()
    if len(parts) != 2: return safe_send(message.chat.id, "❌ Формат: `КОД СУММА`")
    code, amount_str = parts[0].upper(), parts[1]
    try: amount = int(amount_str)
    except ValueError: return safe_send(message.chat.id, "❌ Сумма должна быть числом.")
    
    db["promos"][code] = {"type": "tokens", "amount": amount}
    save_db(db)
    safe_send(message.chat.id, f"✅ Промокод `{code}` на {amount} токенов создан!")

@bot.callback_query_handler(func=lambda c: c.data == "adm_create_item")
def adm_create_item(call):
    safe_answer(call)
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("👓 Рентген-очки", callback_data="adm_item_xray"),
        InlineKeyboardButton("💊 Таблетка", callback_data="adm_item_pill"),
        InlineKeyboardButton("👼 Зелье ангела", callback_data="adm_item_angel")
    )
    safe_edit(call.message.chat.id, call.message.message_id, "Выбери предмет:", kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("adm_item_"))
def adm_item_chosen(call):
    item = call.data.replace("adm_item_", "")
    names = {"xray": "Рентген", "pill": "Таблетка", "angel": "Зелье ангела"}
    bot.send_message(call.message.chat.id, f"Введи: `КОД КОЛИЧЕСТВО` для предмета *{names[item]}*\nПример: `XRAY3 5`")
    bot.register_next_step_handler(call.message, adm_process_item, item)

def adm_process_item(message, item):
    parts = message.text.split()
    if len(parts) != 2: return safe_send(message.chat.id, "❌ Формат: `КОД КОЛИЧЕСТВО`")
    code, amount_str = parts[0].upper(), parts[1]
    try: amount = int(amount_str)
    except ValueError: return safe_send(message.chat.id, "❌ Количество должно быть числом.")
    
    db["promos"][code] = {"type": "item", "item": item, "amount": amount}
    save_db(db)
    names = {"xray": "Рентген", "pill": "Таблетка", "angel": "Зелье ангела"}
    safe_send(message.chat.id, f"✅ Промокод `{code}` на {amount} шт. ({names[item]}) создан!")

@bot.callback_query_handler(func=lambda c: c.data == "adm_list_promos")
def adm_list_promos(call):
    safe_answer(call)
    if not db["promos"]:
        return safe_edit(call.message.chat.id, call.message.message_id, "📭 Список пуст.", None)
    lines = ["📋 СПИСОК ПРОМОКОДОВ:\n"]
    for code, data in db["promos"].items():
        if data["type"] == "tokens":
            lines.append(f"• `{code}` — {data['amount']} токенов")
        else:
            lines.append(f"• `{code}` — {data['amount']} шт. ({data['item']})")
    safe_edit(call.message.chat.id, call.message.message_id, "\n".join(lines), back_kb())

@bot.callback_query_handler(func=lambda c: c.data == "adm_delete_promo")
def adm_delete_promo(call):
    safe_answer(call)
    bot.send_message(call.message.chat.id, "Введи код промокода для удаления:")
    bot.register_next_step_handler(call.message, adm_process_delete)

def adm_process_delete(message):
    code = message.text.strip().upper()
    if code in db["promos"]:
        del db["promos"][code]
        save_db(db)
        safe_send(message.chat.id, f"✅ Промокод `{code}` удален.")
    else:
        safe_send(message.chat.id, "❌ Промокод не найден.")

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
    elif promo["type"] == "item":
        item = promo["item"]
        user["inventory"][item] = user["inventory"].get(item, 0) + promo["amount"]
        names = {"xray": "Рентген", "pill": "Таблетка", "angel": "Зелье ангела"}
        reward_text = f"+{promo['amount']} шт. {names[item]}"
        
    user.setdefault("used_promos", []).append(code)
    save_db(db)
    safe_send(message.chat.id, f"✅ Активирован! Награда: {reward_text}\n💵 Баланс: {user['balance']}", main_menu())

# ═══════════════════════════════════════════════
# МИНИ-ИГРЫ
# ═══════════════════════════════════════════════
@bot.callback_query_handler(func=lambda c: c.data == "mini_games_menu")
def mini_games_menu_cb(call):
    safe_answer(call)
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("🎲 Кубик (+50)", callback_data="mg_dice"),
        InlineKeyboardButton("🪙 Монетка (x2)", callback_data="mg_coin"),
        InlineKeyboardButton("🎁 Бонус: Снятие минуса (раз в день)", callback_data="mg_minus"),
        InlineKeyboardButton("⬅️ Назад", callback_data="refresh")
    )
    safe_edit(call.message.chat.id, call.message.message_id, "🎮 МИНИ-ИГРЫ\nВыбери игру:", kb)

@bot.callback_query_handler(func=lambda c: c.data == "mg_dice")
def mg_dice(call):
    safe_answer(call)
    safe_edit(call.message.chat.id, call.message.message_id, "🎲 Бросаем кубик...", None)
    time.sleep(0.5)
    user = get_user(call.from_user.id)
    r = random.randint(1, 6)
    if r >= 4:
        user["balance"] += 50
        txt = f"🎲 Выпало: {r}. Победа! +50 токенов.\n💵 Баланс: {user['balance']}"
    else:
        txt = f"🎲 Выпало: {r}. Не повезло."
    save_db(db)
    safe_edit(call.message.chat.id, call.message.message_id, txt, main_menu())

@bot.callback_query_handler(func=lambda c: c.data == "mg_coin")
def mg_coin(call):
    safe_answer(call)
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🪙 Орел", callback_data="coin_heads"),
        InlineKeyboardButton("🪙 Решка", callback_data="coin_tails")
    )
    kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="mini_games_menu"))
    safe_edit(call.message.chat.id, call.message.message_id, "🪙 Орел или решка?", kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("coin_"))
def coin_flip(call):
    safe_answer(call)
    user = get_user(call.from_user.id)
    choice = call.data.replace("coin_", "")
    msg = safe_send(call.message.chat.id, "🪙 Подбрасываем...")
    if not msg: return
    time.sleep(1)
    result = random.choice(["heads", "tails"])
    if choice == result:
        user["balance"] *= 2
        txt = f"🪙 {result.capitalize()}! Ты угадал. Баланс удвоен: {user['balance']}"
    else:
        txt = f"🪙 {result.capitalize()}! Не угадал."
    save_db(db)
    safe_edit(msg.chat.id, msg.message_id, txt, main_menu())

@bot.callback_query_handler(func=lambda c: c.data == "mg_minus")
def mg_minus(call):
    safe_answer(call)
    user = get_user(call.from_user.id)
    now = int(time.time())
    if now - user.get("last_minus_bonus", 0) < 86400:
        left = 86400 - (now - user["last_minus_bonus"])
        return safe_answer(call, f"⏳ Бонус через {left//3600}ч {(left%3600)//60}м", show_alert=True)
    if user["balance"] >= 0:
        return safe_answer(call, "❌ Бонус доступен только при минусовом балансе!", show_alert=True)
    user["balance"] = 0
    user["last_minus_bonus"] = now
    save_db(db)
    safe_edit(call.message.chat.id, call.message.message_id, "🎁 Минус снят! Твой баланс теперь 0.", main_menu())

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
        InlineKeyboardButton("⭐ Пополнить через звёзды", callback_data="buy_stars"),
        InlineKeyboardButton("⬅️ Назад", callback_data="refresh")
    )
    safe_edit(call.message.chat.id, call.message.message_id, "💰 ПОПОЛНЕНИЕ\nВыбери способ:", kb)

@bot.callback_query_handler(func=lambda c: c.data == "buy_stars")
def buy_stars(call):
    safe_answer(call)
    kb = InlineKeyboardMarkup(row_width=1)
    packages = [(100, 100), (250, 250), (500, 500), (1000, 1000)]
    for stars, tokens in packages:
        kb.add(InlineKeyboardButton(
            f"⭐ {stars} звёзд → {tokens} токенов",
            callback_data=f"stars_{stars}"
        ))
    kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="menu_deposit"))
    safe_edit(call.message.chat.id, call.message.message_id,
              "⭐ ВЫБЕРИ ПАКЕТ ПОПОЛНЕНИЯ\nКурс: 1 ⭐ = 1 токен", kb)


@bot.callback_query_handler(func=lambda c: c.data in ("stars_100", "stars_250", "stars_500", "stars_1000"))
def send_stars_invoice(call):
    safe_answer(call)
    stars = int(call.data.split("_")[1])
    tokens = stars
    try:
        bot.send_invoice(
            call.message.chat.id,
            f"Пополнение на {tokens} токенов",
            f"{stars} Telegram Stars → {tokens} токенов",
            f"stars_{stars}",
            "",
            "XTR",
            [LabeledPrice(f"{tokens} токенов", stars)]
        )
    except Exception:
        safe_send(call.message.chat.id, "❌ Не удалось создать счёт. Попробуй позже.")


@bot.pre_checkout_query_handler(func=lambda query: True)
def pre_checkout(query):
    try:
        stars = int(query.invoice_payload.split("_")[1]) if query.invoice_payload.startswith("stars_") else 0
    except (ValueError, IndexError):
        stars = 0
    if (not has_full_access(query.from_user.id) or stars not in (100, 250, 500, 1000)
            or query.currency != "XTR" or query.total_amount != stars):
        try:
            bot.answer_pre_checkout_query(
                query.id, ok=False,
                error_message="Платёж не прошёл проверку. Создай новый счёт."
            )
        except Exception:
            pass
        return
    try:
        bot.answer_pre_checkout_query(query.id, ok=True)
    except Exception:
        pass


@bot.message_handler(content_types=["successful_payment"])
def on_payment(message):
    payment = message.successful_payment
    try:
        stars = int(payment.invoice_payload.split("_")[1]) if payment.invoice_payload.startswith("stars_") else 0
    except (ValueError, IndexError):
        stars = 0
    if (stars not in (100, 250, 500, 1000) or payment.currency != "XTR"
            or payment.total_amount != stars):
        safe_send(message.chat.id, "⚠️ Платёж получен, но его данные не прошли проверку. Обратись к администратору.")
        return

    charge_id = payment.telegram_payment_charge_id
    processed = db.setdefault("processed_payments", [])
    if charge_id in processed:
        return safe_send(message.chat.id, "ℹ️ Этот платёж уже был зачислен.")

    user = get_user(message.from_user.id)
    user["balance"] += stars
    processed.append(charge_id)
    save_db(db)
    safe_send(message.chat.id,
              f"✅ Оплата прошла! +{stars} токенов.\n💵 Баланс: {user['balance']}",
              main_menu())

# ═══════════════════════════════════════════════
# ЗАПУСК
# ═══════════════════════════════════════════════
if __name__ == "__main__":
    print("🚀 CASINO BOT запущен...")
    update_shop_stock()
    bot.infinity_polling()
