import os
import re
import json
import asyncio
from aiogram import Bot, Dispatcher, F, types
from github import Github
from google import genai
from groq import Groq
from aiohttp import web

TG_TOKEN = (os.getenv("TG_TOKEN") or "").strip()
GITHUB_TOKEN = (os.getenv("GITHUB_TOKEN") or "").strip()
GITHUB_REPO = (os.getenv("GITHUB_REPO") or "").strip()
GEMINI_KEY = (os.getenv("GEMINI_API_KEY") or "").strip()
GROQ_KEY = (os.getenv("GROQ_API_KEY") or "").strip()
VERCEL_URL = (os.getenv("VERCEL_URL") or "").strip()

bot = Bot(token=TG_TOKEN)
dp = Dispatcher()
groq_client = Groq(api_key=GROQ_KEY) if GROQ_KEY else None
ai_client = genai.Client(api_key=GEMINI_KEY) if GEMINI_KEY else None
gh = Github(GITHUB_TOKEN).get_repo(GITHUB_REPO)

# ==================== БАЗА ЗНАНИЙ D&D: ЗАТЕРЯННЫЙ ХРАМ АНАКСА АПОГЕЙОНА ====================
DND_SCENARIO_PROMPT = """
Ты — атмосферный Мастер Подземелий (Dungeon Master) в D&D 5e. Ты ведешь приключение «Затерянный храм Анакса Апогейона» для героя 3-го уровня.
Пиши художественно, мрачно (лавкрафтианское темное фэнтези), но по делу (1-2 абзаца за ход). Обращайся к игроку на «ты».

ЛОР И ПРЕДЫСТОРИЯ:
- 300 лет назад культ Великого Древнего Анакса Апогейона замуровал себя в храме в горах Западных пустошей со свитком призыва и умер от голода.
- Недавно маг Натрин Йеллс украл мясного голема, повалил гигантского идола у входа и вошел в храм, но погиб внутри.
- Демонический культ хаоса «Стадо Чёрной Козы» послал экспедицию за свитком.
- Игрок нанят агентом магократии Финнием Каларексом, чтобы узнать судьбу мага и забрать древний свиток.

КАРТА И КОМНАТЫ ХРАМА (СТРОГО СЛЕДУЙ ЭТИМ ПРАВИЛАМ):
[Комната 1: Вход]
- Опрокинутый гигантский идол со щупальцами и одним глазом открывает туннель. Рядом стоит громадный Мясной голем.
- Вход охраняют 2 культиста Чёрной Козы (КД 12, Хиты 9, сабля +3, урон 1к6+1). На шеях серебряные ошейники с пентаграммой из колосьев пшеницы (История СЛ 14 — символ Стада Чёрной Козы, 10 зм).
- Культисты кричат уходить, угрожая натравить голема. ЭТО БЛЕФ: голем подчинялся только мертвому Натрину Йеллсу и не двигается, пока его не бьют.
- Осмотр статуи: Спасбросок Харизмы СЛ 14 или 7 психического урона. Повреждение статуи выпускает Рой бабочек смерти (КД 13, Хиты 22). Внутри идола Чёрный бриллиант (500 зм).

[Комната 2: Лестница]
- Лестница вниз, скелеты 300-летней давности и 2 свежих трупа культистов (Расследование СЛ 12). Стены покрыты резьбой сотен глаз и щупалец.
- ЛОВУШКА: Расследование/Магия СЛ 14 покажет некротическую энергию глаз. Разрушить можно Магией или Религией СЛ 14.
- Иначе на середине пути глаза вспыхивают фиолетовым: Спасбросок Телосложения СЛ 12 или обморок и 7 некротического урона от эфирных щупалец из стен.

[Комната 3: Реликварий]
- Длинный холл с нишами и изуродованными телами. Спереди яма с шипами (20 футов, на дне 2 трупа культистов).
- При входе 4 тела издают визг: Спасбросок Мудрости СЛ 10 или Ужас (бегство, шанс упасть в яму на 10 урона). Атакуют 4 Кожные летучие мыши (КД 12, Хиты 10).
- СЕКРЕТ: Расследование СЛ 13 у правой стены обнаружит сквозняк и проход в Комнату 4.

[Комната 4: Тайное хранилище]
- Каменная плита со скелетом (ловушек нет). СОКРОВИЩЕ: блестящие «Наручи защиты (+2 к КД)».

[Комната 5: Зал Второго]
- Фиолетовые факелы, труп культиста. С платформы встает Мумия (КД 11, Хиты 38, удар +5, урон 10) и атакует!
- СОКРОВИЩЕ на полу: магический Скимитар +1 «Пыль» (раз в сутки создает Туманное облако).

[Комната 6: Зал Криков]
- Два трупа в нишах, изо рта выползает неземная чёрная оса (Магия/Природа СЛ 12). При проходе атакуют 2 Роя чёрных ос (КД 12, Хиты 22).

[Комната 7: Алтарь В'атлуса (ФИНАЛ)]
- Восьмиугольный зиккурат, фиолетовый портал под потолком. На полу безголовый труп мага Натрина Йеллса (предмет «Волшебная палочка секретов»).
- Фанатик Корреш Шепчущий читает свиток: «Дело сделано, Анакс Апогейон слышит меня!»
- Из портала падает босс ДОРРЕК (КД 15, Хиты 93, укус +6 на 22 урона, два щупальца +6 на 8 урона, захват СЛ 14). Он отрывает голову Коррешу, свиток падает на пол. Первые 2 раунда Доррек жует Корреша и бьет героя только щупальцами!
- После победы над Дорреком портал схлопывается, герой решает судьбу «Свитка Анакса Апогейона».

ФОРМАТ ОТВЕТА — СТРОГО JSON:
{
  "reply": "Твой ответ Мастера (если нужен бросок кубика — напиши в конце, какой именно и с какой СЛ)",
  "room": номер_комнаты_от_1_до_7,
  "hp_change": число_изменения_HP_например_0_или_-7,
  "add_item": "Название предмета" или null,
  "roll_needed": { "label": "Название проверки (например: Спасбросок Харизмы СЛ 14)", "bonus": 2, "dc": 14 } или null
}
"""

SYSTEM_PROMPT = """
Ты — элитный разработчик мобильных веб-приложений и HTML5 игр.
Сгенерируй ПОЛНЫЙ, рабочий файл index.html (HTML + CSS + JS в одном файле).
Начни ответ строго с <!DOCTYPE html> и закончи на </html>. Никакого текста до или после кода!
"""

def get_working_groq_models():
    if not groq_client:
        return []
    try:
        avail = [
            m.id for m in groq_client.models.list().data
            if not any(bad in m.id.lower() for bad in ["whisper", "guard", "tts", "vision", "audio"])
        ]
        pref = [m for m in avail if any(k in m.lower() for k in ["llama-3.3", "llama-3.1", "qwen", "llama"])]
        return pref + [m for m in avail if m not in pref]
    except Exception:
        return ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]

def call_ai_sync(messages, max_tokens=4000, json_mode=False):
    errors = []
    if groq_client:
        for m in get_working_groq_models()[:5]:
            try:
                kwargs = {
                    "model": m,
                    "messages": messages,
                    "temperature": 0.5,
                    "max_tokens": max_tokens,
                }
                if json_mode:
                    kwargs["response_format"] = {"type": "json_object"}
                resp = groq_client.chat.completions.create(**kwargs)
                return resp.choices[0].message.content
            except Exception as e:
                errors.append(f"Groq({m}): {str(e)[:100]}")

    if ai_client:
        full_text = "\n\n".join([f"{msg['role']}: {msg['content']}" for msg in messages])
        for gm in ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-3.8-flash"]:
            try:
                resp = ai_client.models.generate_content(model=gm, contents=full_text)
                return resp.text
            except Exception as e:
                errors.append(f"Gemini({gm}): {str(e)[:100]}")

    raise RuntimeError("Детали ошибок API:\n" + "\n".join(errors[:4]))

def clean_html(raw_text: str) -> str:
    raw_text = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL | re.IGNORECASE)
    match = re.search(r"(<!DOCTYPE html>.*</html>|<html.*</html>)", raw_text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return raw_text.strip()

async def process_task(task_text: str, message: types.Message):
    status_msg = await message.reply("⚙️ Архитектор думает и пишет код...")
    try:
        current_file = gh.get_contents("index.html")
        current_code = current_file.decoded_content.decode("utf-8")
        file_sha = current_file.sha
    except Exception:
        current_code = ""
        file_sha = None

    if "с нуля" in task_text.lower() or len(current_code) > 25000:
        prompt = f"Задача:\n{task_text}\n\nНапиши полный рабочий index.html с нуля."
    else:
        prompt = f"Текущий код:\n{current_code}\n\nЗадача:\n{task_text}\n\nВерни обновленный index.html целиком."

    try:
        raw_output = call_ai_sync([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ], max_tokens=6000, json_mode=False)
        new_code = clean_html(raw_output)
        commit_msg = f"Vibe update: {task_text[:40]}"
        if file_sha:
            gh.update_file("index.html", commit_msg, new_code, file_sha)
        else:
            gh.create_file("index.html", commit_msg, new_code)

        await status_msg.edit_text(f"✅ **Готово!**\n🚀 **Открыть:** {VERCEL_URL}")
    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка:\n{str(e)[:3500]}")

@dp.message(F.voice)
async def handle_voice(message: types.Message):
    wait_msg = await message.reply("🎙 Распознаю голос...")
    file = await bot.get_file(message.voice.file_id)
    file_bytes = await bot.download_file(file.file_path)
    transcription = groq_client.audio.transcriptions.create(
        file=("audio.ogg", file_bytes.read()),
        model="whisper-large-v3"
    ).text
    await wait_msg.edit_text(f"🗣 **Услышал:** {transcription}")
    await process_task(transcription, message)

@dp.message(F.text)
async def handle_text(message: types.Message):
    await process_task(message.text, message)

# ==================== ВЕБ-СЕРВЕР И API ДЛЯ ЖИВОГО D&D МАСТЕРА ====================
CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}

async def handle_options(request):
    return web.Response(status=200, headers=CORS_HEADERS)

async def handle_ping(request):
    return web.Response(text="Bot & D&D Master API are running!", headers=CORS_HEADERS)

async def handle_dm_chat(request):
    try:
        data = await request.json()
        user_action = data.get("action", "Осматриваюсь вокруг")
        history = data.get("history", [])
        state = data.get("state", {})

        messages = [
            {"role": "system", "content": DND_SCENARIO_PROMPT},
            {"role": "system", "content": f"СОСТОЯНИЕ ГЕРОЯ: Комната №{state.get('room', 1)}, HP: {state.get('hp', 28)}/{state.get('maxHp', 28)}, КД: {state.get('ac', 16)}, Инвентарь: {', '.join(state.get('inventory', []))}."}
        ]
        for h in history[-8:]:
            messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})
        messages.append({"role": "user", "content": user_action})

        try:
            raw_json = call_ai_sync(messages, max_tokens=1200, json_mode=True)
            parsed = json.loads(raw_json)
        except Exception:
            raw_text = call_ai_sync(messages, max_tokens=1200, json_mode=False)
            m = re.search(r"\{.*\}", raw_text, re.DOTALL)
            parsed = json.loads(m.group(0)) if m else {"reply": raw_text, "room": state.get("room", 1), "hp_change": 0, "add_item": None, "roll_needed": None}

        return web.json_response(parsed, headers=CORS_HEADERS)
    except Exception as e:
        return web.json_response({
            "reply": f"⚠️ Техническая заминка Мастера: {str(e)}",
            "room": 1,
            "hp_change": 0,
            "add_item": None,
            "roll_needed": None
        }, status=200, headers=CORS_HEADERS)

async def handle_voice_api(request):
    try:
        reader = await request.multipart()
        field = await reader.next()
        audio_bytes = await field.read()
        transcription = groq_client.audio.transcriptions.create(
            file=("voice.webm", audio_bytes),
            model="whisper-large-v3",
            language="ru"
        ).text
        return web.json_response({"text": transcription}, headers=CORS_HEADERS)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400, headers=CORS_HEADERS)

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    app.router.add_route("OPTIONS", "/api/dm", handle_options)
    app.router.add_post("/api/dm", handle_dm_chat)
    app.router.add_route("OPTIONS", "/api/voice", handle_options)
    app.router.add_post("/api/voice", handle_voice_api)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def main():
    print("Бот и D&D Мастер запущены...")
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
          
