import asyncio
import os
import re
import json
from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web, ClientSession
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CMC_KEY = os.getenv("CMC_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
PORT = int(os.getenv("PORT", 8000))
GROQ_MODEL = "meta-llama/llama-4-maverick-17b-128e-instruct"
CHANNEL_USERNAME = "p2p_LRN"

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(storage=MemoryStorage())
USERS_FILE = "users.json"

# === دعم تخزين المستخدمين في ملف JSON ===
def load_users():
    try:
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f)

user_lang = load_users()

def clean_response(text, lang="ar"):
    if lang == "ar":
        return re.sub(r'[^\u0600-\u06FF0-9A-Za-z.,:%$؟! \n\-]+', '', text)
    else:
        return re.sub(r'[^\w\s.,:%$!?$-]+', '', text)

# === استبدال httpx بـ aiohttp ===
async def ask_groq(prompt, lang="ar"):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": GROQ_MODEL,
        "messages": [{"role": "user", "content": prompt}]
    }
    try:
        async with ClientSession(timeout=None) as session:
            async with session.post(url, headers=headers, json=data) as res:
                result = await res.json()
                content = result["choices"][0]["message"]["content"]
                return clean_response(content, lang=lang).strip()
    except Exception as e:
        print("❌ Error from AI:", e)
        return "❌ حدث خطأ أثناء تحليل التشارت." if lang == "ar" else "❌ Analysis failed."

async def get_price_cmc(symbol):
    url = f"https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest?symbol={symbol.upper()}"
    headers = {"X-CMC_PRO_API_KEY": CMC_KEY}
    try:
        async with ClientSession() as session:
            async with session.get(url, headers=headers) as res:
                if res.status != 200:
                    return None
                data = await res.json()
                return data["data"][symbol.upper()]["quote"]["USD"]["price"]
    except:
        return None

# === أزرار اللغة ===
language_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="العربية", callback_data="lang_ar"),
     InlineKeyboardButton(text="English", callback_data="lang_en")]
])

# === أزرار الاشتراك ===
subscribe_ar = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="اشترك بالقناة", url=f"https://t.me/{CHANNEL_USERNAME}")],
    [InlineKeyboardButton(text="تحققت", callback_data="check_sub")]
])
subscribe_en = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Subscribe", url=f"https://t.me/{CHANNEL_USERNAME}")],
    [InlineKeyboardButton(text="I've joined", callback_data="check_sub")]
])

# === أزرار الإطار الزمني ===
timeframe_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton("1D", callback_data="tf_1D"),
     InlineKeyboardButton("1W", callback_data="tf_1W"),
     InlineKeyboardButton("1M", callback_data="tf_1M")]
])

# === أحداث البوت ===
@dp.message(F.text == "/start")
async def start(m: types.Message):
    uid = str(m.from_user.id)
    if uid not in user_lang:
        user_lang[uid] = "ar"
        save_users(user_lang)
    await m.answer("اختر لغتك / Choose your language:", reply_markup=language_keyboard)

@dp.callback_query(F.data.startswith("lang_"))
async def set_lang(cb: types.CallbackQuery):
    lang = cb.data.split("_")[1]
    uid = str(cb.from_user.id)
    user_lang[uid] = lang
    save_users(user_lang)
    member = await bot.get_chat_member(f"@{CHANNEL_USERNAME}", cb.from_user.id)
    if member.status in ("member", "administrator", "creator"):
        await cb.message.edit_text("✅ مشترك. أرسل رمز العملة:" if lang=="ar" else "✅ Subscribed. Send coin symbol:")
    else:
        kb = subscribe_ar if lang=="ar" else subscribe_en
        await cb.message.edit_text("❗ الرجاء الاشتراك أولاً" if lang=="ar" else "❗ Please subscribe first", reply_markup=kb)

@dp.callback_query(F.data == "check_sub")
async def check_sub(cb: types.CallbackQuery):
    uid = str(cb.from_user.id)
    lang = user_lang.get(uid, "ar")
    member = await bot.get_chat_member(f"@{CHANNEL_USERNAME}", cb.from_user.id)
    if member.status in ("member", "administrator", "creator"):
        await cb.message.edit_text("✅ مشترك. أرسل رمز العملة:" if lang=="ar" else "✅ Subscribed. Send coin symbol:")
    else:
        kb = subscribe_ar if lang=="ar" else subscribe_en
        await cb.message.edit_text("❗ الرجاء الاشتراك أولاً" if lang=="ar" else "❗ Please subscribe first", reply_markup=kb)

selected_symbol = {}
selected_timeframe = {}

@dp.message(F.text)
async def handle_symbol(m: types.Message):
    uid = str(m.from_user.id)
    lang = user_lang.get(uid, "ar")
    sym = m.text.strip().upper()
    selected_symbol[uid] = sym

    member = await bot.get_chat_member(f"@{CHANNEL_USERNAME}", m.from_user.id)
    if member.status not in ("member", "administrator", "creator"):
        await m.answer("⚠️ اشترك بالقناة أولاً." if lang=="ar" else "⚠️ Please join the channel first.",
                       reply_markup=subscribe_ar if lang=="ar" else subscribe_en)
        return

    await m.answer("⏳ جاري جلب السعر..." if lang=="ar" else "⏳ Fetching price...")
    price = await get_price_cmc(sym)
    if not price:
        await m.answer("❌ لم أتمكن من جلب السعر الحالي للعملة." if lang=="ar"
                       else "❌ Couldn't fetch current price.")
        return

    await m.answer(f"💵 السعر الحالي: ${price:.6f}" if lang=="ar" else f"💵 Current price: ${price:.6f}")
    await m.answer("اختر الإطار الزمني:", reply_markup=timeframe_keyboard if lang=="ar" else timeframe_keyboard)

@dp.callback_query(F.data.startswith("tf_"))
async def handle_timeframe(cb: types.CallbackQuery):
    uid = str(cb.from_user.id)
    tf = cb.data.split("_")[1]
    selected_timeframe[uid] = tf
    sym = selected_symbol.get(uid)
    lang = user_lang.get(uid, "ar")

    if not sym:
        await cb.message.answer("❗ الرجاء إرسال رمز العملة أولاً." if lang=="ar" else "❗ Send coin symbol first.")
        return

    price = await get_price_cmc(sym)
    if not price:
        await cb.message.answer("❌ لم أتمكن من جلب السعر الحالي للعملة." if lang=="ar"
                                else "❌ Couldn't fetch current price.")
        return

    prompt = f"""سعر العملة {sym} الآن هو {price:.6f}$.
قم بتحليل التشارت {tf} باستخدام مؤشرات الدعم، المقاومة، RSI، MACD، MA، Bollinger Bands، Fibonacci Levels، Stochastic Oscillator، Volume Analysis، Trendlines.
قدم تقييم عام وأهداف سعرية مستقبلية.""" if lang=="ar" else f"""Current price of {sym} is ${price:.6f}.
Analyze the {tf} chart using support, resistance, RSI, MACD, MA, Bollinger Bands, Fibonacci Levels, Stochastic, Volume, Trendlines.
Provide general trend and target price range."""

    await cb.message.answer("🤖 جاري التحليل..." if lang=="ar" else "🤖 Analyzing...")
    analysis = await ask_groq(prompt, lang=lang)
    await cb.message.answer(analysis)

# === Web Mini App ===
async def handle_webhook(req):
    if req.method == "GET":
        return web.Response(text="✅ Bot is alive.")
    update = await req.json()
    await dp.feed_update(bot=bot, update=types.Update(**update))
    return web.Response()

async def on_startup(app):
    print("✅ Bot started...")

async def main():
    app = web.Application()
    app.router.add_post("/", handle_webhook)
    app.router.add_get("/", handle_webhook)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    print("✅ Bot is running...")
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
