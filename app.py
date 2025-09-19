import os, json, asyncio
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
import httpx
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
CMC_KEY = os.getenv("CMC_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
PORT = int(os.getenv("PORT", 8000))
GROQ_MODEL = "meta-llama/llama-4-maverick-17b-128e-instruct"

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(storage=MemoryStorage())

# Price from CMC
async def get_price_cmc(symbol):
    url = f"https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest?symbol={symbol.upper()}"
    headers = {"X-CMC_PRO_API_KEY": CMC_KEY}
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(url, headers=headers)
            if res.status_code != 200: return None
            data = res.json()
            return data["data"][symbol.upper()]["quote"]["USD"]["price"]
    except: return None

# AI Analysis
async def ask_groq(prompt, lang="ar"):
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    data = {"model": GROQ_MODEL, "messages":[{"role":"user","content":prompt}]}
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            res = await client.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=data)
            content = res.json()["choices"][0]["message"]["content"]
            return content.strip()
    except Exception as e:
        print("AI Error:", e)
        return "❌ حدث خطأ أثناء تحليل التشارت." if lang=="ar" else "❌ Analysis failed."

# Web server
async def analyze(request):
    try:
        data = await request.json()
        symbol = data.get("symbol")
        timeframe = data.get("timeframe", "1W")
        lang = data.get("lang","ar")
        price = await get_price_cmc(symbol)
        if not price: return web.json_response({"status":"error","msg":"❌ لم أتمكن من جلب السعر الحالي للعملة." if lang=="ar" else "❌ Couldn't fetch price."})
        prompt = f"سعر العملة {symbol.upper()} الآن هو {price:.6f}$. الإطار الزمني {timeframe}. حلل التشارت أسبوعيًا فقط."
        if lang=="en": prompt = f"The current price of {symbol.upper()} is ${price:.6f}. Timeframe {timeframe}. Analyze the chart."
        analysis = await ask_groq(prompt, lang=lang)
        return web.json_response({"status":"ok","price":price,"analysis":analysis})
    except Exception as e:
        return web.json_response({"status":"error","msg":str(e)})

async def index(request):
    with open("index.html","r",encoding="utf-8") as f: content=f.read()
    return web.Response(text=content, content_type="text/html")

async def main():
    app = web.Application()
    app.router.add_get("/", index)
    app.router.add_post("/analyze", analyze)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    print(f"Server running on port {PORT}")
    while True: await asyncio.sleep(3600)

if __name__=="__main__":
    asyncio.run(main())
