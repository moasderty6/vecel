# app.py
import os
import json
import asyncio
import httpx
from aiohttp import web
import aiohttp_jinja2
import jinja2
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
CMC_KEY = os.getenv("CMC_API_KEY")
PORT = int(os.getenv("MINI_PORT", 9000))

USERS_FILE = "users.json"
user_lang = {}

# =========================
# Load/Save Users
# =========================
def load_users():
    global user_lang
    try:
        with open(USERS_FILE, "r") as f:
            user_lang = json.load(f)
    except:
        user_lang = {}

def save_users():
    with open(USERS_FILE, "w") as f:
        json.dump(user_lang, f)

load_users()

# =========================
# Price fetching
# =========================
async def get_price_cmc(symbol):
    url = f"https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest?symbol={symbol.upper()}"
    headers = {"X-CMC_PRO_API_KEY": CMC_KEY}
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(url, headers=headers)
            if res.status_code != 200:
                return None
            data = res.json()
            return data["data"][symbol.upper()]["quote"]["USD"]["price"]
    except:
        return None

# =========================
# Groq AI Analysis
# =========================
async def ask_groq(prompt, lang="ar"):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "meta-llama/llama-4-maverick-17b-128e-instruct",
        "messages": [{"role": "user", "content": prompt}]
    }
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            res = await client.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=data)
            result = res.json()
            content = result["choices"][0]["message"]["content"]
            return content.strip()
    except Exception as e:
        print("❌ Error:", e)
        return "❌ حدث خطأ أثناء التحليل." if lang=="ar" else "❌ Analysis failed."

# =========================
# WebApp HTML
# =========================
async def index(request):
    context = {}
    return aiohttp_jinja2.render_template("index.html", request=request, context=context)

# =========================
# Handle Analysis Request (via fetch)
# =========================
async def analyze(request):
    data = await request.json()
    symbol = data.get("symbol")
    timeframe = data.get("timeframe", "1W")
    lang = data.get("lang", "ar")
    price = await get_price_cmc(symbol)
    if not price:
        return web.json_response({"status":"error","msg":"❌ لم أتمكن من جلب السعر الحالي للعملة."})
    
    prompt = f"""
سعر العملة {symbol.upper()} الآن هو {price:.6f}$.
الإطار الزمني: {timeframe}
قم بتحليل التشارت الأسبوعي فقط للعملة اعتمادًا على:
- خطوط الدعم والمقاومة.
- مؤشرات RSI و MACD و MA.
- Bollinger Bands
- Fibonacci Levels
- Stochastic Oscillator
- Volume Analysis
- Trendlines
ثم قدّم:
1. تقييم عام (صعود أم هبوط؟).
2. أقرب مقاومة ودعم.
3. السعر المستهدف المتوقع (نطاق سعري).
✅ استخدم العربية فقط.
"""
    analysis = await ask_groq(prompt, lang)
    return web.json_response({"status":"ok","analysis":analysis,"price":price})

# =========================
# Setup app
# =========================
app = web.Application()
aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader("templates"))

app.router.add_get("/", index)
app.router.add_post("/analyze", analyze)

async def start():
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    print(f"✅ Mini App running on port {PORT}...")
    while True:
        await asyncio.sleep(3600)

if __name__=="__main__":
    asyncio.run(start())
