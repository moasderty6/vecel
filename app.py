import os
import json
from aiohttp import web
import httpx
from aiohttp_jinja2 import setup as jinja_setup, render_template
import jinja2
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
MINI_PORT = int(os.getenv("MINI_PORT", 9000))
USERS_FILE = "mini_users.json"

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

async def send_message(chat_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    async with httpx.AsyncClient() as client:
        await client.post(BOT_API_URL, json=payload)

async def index(request):
    return render_template("index.html", request=request)

async def interact(request):
    user_id = request.match_info.get("user_id")
    lang = user_lang.get(user_id, "ar")
    kb = {
        "inline_keyboard": [
            [{"text": "🇸🇦 العربية", "callback_data": "lang_ar"}],
            [{"text": "🇺🇸 English", "callback_data": "lang_en"}]
        ]
    }
    await send_message(user_id, "👋 اختر لغتك:\nChoose your language:", reply_markup=kb)
    return web.Response(text=f"تم بدء التفاعل مع {user_id}")

async def send_symbol(request):
    data = await request.json()
    user_id = str(data["user_id"])
    symbol = data["symbol"].upper()
    price = data.get("price", 0)
    user_lang[user_id+"_symbol"] = symbol
    user_lang[user_id+"_price"] = price
    save_users(user_lang)

    lang = user_lang.get(user_id, "ar")
    kb = {
        "inline_keyboard": [
            [
                {"text": "أسبوعي", "callback_data": "tf_weekly"},
                {"text": "يومي", "callback_data": "tf_daily"},
                {"text": "4 ساعات", "callback_data": "tf_4h"}
            ]
        ]
    }
    if lang != "ar":
        kb["inline_keyboard"] = [
            [
                {"text": "Weekly", "callback_data": "tf_weekly"},
                {"text": "Daily", "callback_data": "tf_daily"},
                {"text": "4H", "callback_data": "tf_4h"}
            ]
        ]
    await send_message(user_id, "⏳ اختر الإطار الزمني للتحليل:" if lang=="ar" else "⏳ Select timeframe for analysis:", reply_markup=kb)
    return web.Response(text="تم إرسال الرمز للبوت.")

app = web.Application()
jinja_setup(app, loader=jinja2.FileSystemLoader("templates"))
app.router.add_get("/", index)
app.router.add_get("/interact/{user_id}", interact)
app.router.add_post("/send_symbol", send_symbol)
app.router.add_static("/static", "static")

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=MINI_PORT)
