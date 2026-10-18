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
groq_client = Groq(api_key=GROQ_KEY)
ai_client = genai.Client(api_key=GEMINI_KEY) if GEMINI_KEY else None
gh = Github(GITHUB_TOKEN).get_repo(GITHUB_REPO)

# ==================== БАЗА ЗНАНИЙ D&D: ЗАТЕРЯННЫЙ ХРАМ АНАКСА АПОГЕЙОНА ====================
DND_SCENARIO_PROMPT = """
Ты — атмосферный Мастер Подземелий (Dungeon Master) в D&D 5e. Ты ведешь приключение «Затерянный храм Анакса Апогейона» для героя 3-го уровня.
Пиши художественно, мрачно (лавкрафтианское темное фэнтези), но по делу (1-3 абзаца за ход). Обращайся к игроку на «ты».

ЛОР И ПРЕДЫСТОРИЯ:
- 300 лет назад культ Великого Древнего Анакса Апогейона замуровал себя в храме в горах Западных пустошей со свитком призыва и умер от голода.
- Недавно маг Натрин Йеллс (из магократии Аллен) украл мясного голема, повалил гигантского идола у входа и вошел в храм, но погиб внутри.
- Демонический культ хаоса «Стадо Чёрной Козы» узнал об открытии храма и послал экспедицию за свитком.
- Игрок нанят агентом магократии Финнием Каларексом, чтобы узнать судьбу мага Натрина Йеллса и забрать древний свиток.

КАРТА И КОМНАТЫ ХРАМА (СТРОГО СЛЕДУЙ ЭТИМ ПРАВИЛАМ):
[Комната 1: Вход]
- Опрокинутый гигантский идол со щупальцами и одним глазом открывает туннель. Рядом стоит громадный Мясной голем (сшитый из кусков кожи).
- Вход охраняют 2 культиста Чёрной Козы (КД 12, Хиты 9, кривая сабля +3, урон 1к6+1). На шеях серебряные ошейники с пентаграммой из колосьев пшеницы (Проверка Интеллекта/Истории СЛ 14 — символ Стада Чёрной Козы, цена 10 зм).
- Культисты кричат уходить, угрожая натравить голема. ЭТО УЛОВКА И БЛЕФ: голем подчинялся только мертвому Натрину Йеллсу и просто стоит, пока его не атакуют.
- Осмотр статуи Анакса Апогейона: требуется Спасбросок Харизмы СЛ 14, при провале 7 (2к6) психического урона.
- Физическое повреждение статуи выпускает Рой бабочек смерти (КД 13, Хиты 22). Внутри идола спрятан Чёрный бриллиант (500 зм, Магия СЛ 16 — камень из иного мира).

[Комната 2: Лестница]
- Крутая лестница вниз, десятки скелетов 300-летней давности в серых лохмотьях и 2 свежих трупа культистов Чёрной Козы (Расследование СЛ 12).
- Стены покрыты резьбой: сотни глаз и тысячи щупалец.
- ЛОВУШКА: Расследование СЛ 14 покажет, что глаза пульсируют энергией (Магия СЛ 14 — некротическая). Разрушить энергию можно проверкой Интеллекта (Магия или Религия) СЛ 14.
- Если спускаться без обезвреживания: на середине пути глаза вспыхивают фиолетовым! Нужен Спасбросок Телосложения СЛ 12. При провале — обморок и черные эфирные щупальца из стен высасывают жизнь: 7 (2к6) некротического урона.

[Комната 3: Реликварий]
- Длинный холл с нишами, где стоят изуродованные останки. В передней части — яма с шипами глубиной 20 футов, на дне 2 пронзенных трупа культистов.
- Восприятие СЛ 13: тела в нишах шевелятся. При входе в зал 4 тела издают жуткий визг! Нужен Спасбросок Мудрости СЛ 10 или эффект Ужаса (бегство, при 1-2 на к6 падение в яму с шипами: 7 колющего + 3 урона ядом).
- С останков срываются 4 Кожные летучие мыши (КД 12, Хиты 10, укус +4, урон 1к4+2) и атакуют.
- СЕКРЕТ: Расследование СЛ 13 у правой стены за трупом культиста обнаружит сквозняк из тонкой каменной кладки. Пробив стену, герой попадает в Комнату 4.

[Комната 4: Тайное хранилище]
- Нетронутый зал, каменная плита со скелетом (300 лет, ловушек нет), по углам 4 одноглазые статуи со щупальцами.
- СОКРОВИЩЕ: на скелете блестящие «Наручи защиты (+2 к КД)».

[Комната 5: Зал Второго]
- Фиолетовые факелы на стенах, труп культиста с искаженным агонией лицом. На каменной платформе поднимается древняя Мумия (КД 11, Хиты 38, кулак +5, урон 2к6+3) и атакует!
- СОКРОВИЩЕ на полу: магический Скимитар +1 «Пыль» (раз в сутки создает Туманное облако).

[Комната 6: Зал Криков]
- Два обёрнутых тканью тела в нишах, лужа крови. Изо рта левого трупа выползает неземная чёрная оса (Магия/Природа СЛ 12).
- При проходе вылетают 2 Роя чёрных ос (КД 12, Хиты 22 каждый, укусы +3, урон 2к4) и атакуют.

[Комната 7: Алтарь В'атлуса (ФИНАЛ)]
- Восьмиугольный каменный зиккурат, под потолком вращается фиолетовый портал. На полу безголовый труп мага Натрина Йеллса (у него предмет «Волшебная палочка секретов»).
- На ступенях зиккурата фанатик Корреш Шепчущий дочитывает свиток: «Дело сделано, Анакс Апогейон слышит меня!»
- В этот миг из портала падает чудовище ДОРРЕК (аберрация со щупальцами и кальмарьим клювом, КД 15, Хиты 93, укус +6 на 4к8+4, два щупальца +6 на 1к8+4, захват СЛ 14).
- Доррек мгновенно отрывает голову Коррешу, свиток падает на песок. Первые 2 раунда Доррек жует тело Корреша и бьет героя только щупальцами!
- После победы над Дорреком портал схлопывается. Герой решает судьбу «Свитка Анакса Апогейона» (отдать магократии Аллен, отдать культу Чёрной Козы или уничтожить).

ПРАВИЛА ОТВЕТА (СТРОГО ВЕРНИ JSON):
Ты ОБЯЗАН вернуть ответ СТРОГО в формате валидного JSON-объекта со следующими полями:
{
  "reply": "Твой художественный ответ Мастера. Если нужна проверка навыка, спасбросок или бросок атаки — четко напиши в конце ответа, какой бросок d20 и с какой Сложностью (СЛ) должен сделать игрок!",
  "room": номер_текущей_комнаты_от_1_до_7,
  "hp_change": число_изменения_здоровья_игрока (например -7 при уроне, +10 при лечении или 0),
  "add_item": "Название найденного предмета" или null,
  "roll_needed": { "label": "Название проверки (например: Спасбросок Харизмы СЛ 14)", "bonus": бонус_числом_например_2, "dc": сложность_числом_например_14 } или null
}
Никакого текста до или после JSON!
"""

# ==================== ЛОГИКА TELEGRAM-БОТА ДЛЯ ВАЙБКОДИНГА ====================
SYSTEM_PROMPT = """
Ты — элитный разработчик мобильных веб-приложений и HTML5 игр.
Твоя задача — вернуть ПОЛНЫЙ рабочий код запрошенного файла.
ЖЁСТКИЕ ПРАВИЛА:
1. Если создаешь index.html — начни строго с <!DOCTYPE html> и закончи </html>.
2. Если создаешь .js файл — пиши ТОЛЬКО чистый JavaScript код без тегов <script>.
3. Не пиши никаких приветствий, пояснений и markdown-оболочек ```.
"""

def clean_code(raw_text: str, filename: str) -> str:
    text = raw_text.strip()
    text = re.sub(r"^```[a-zA-Z]*\n", "", text)
    text = re.sub(r"\n```$", "", text)
    text = text.strip()
    if filename.endswith(".html"):
        start = text.find("<!DOCTYPE")
        if start == -1:
            start = text.find("<html")
        end = text.rfind("</html>")
        if start != -1 and end != -1:
            text = text[start:end + 7]
    return text

async def generate_with_ai(prompt: str, sys_prompt: str) -> str:
    # 1. Пробуем через быстрый Groq Llama 3.3
    models_to_try = ["llama-3.3-70b-versatile", "llama3-70b-8192"]
    for m in models_to_try:
        try:
            chat_completion = groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": prompt}
                ],
                model=m,
                temperature=0.5,
                max_tokens=7500
            )
            return chat_completion.choices[0].message.content
        except Exception as e:
            print(f"Groq {m} error: {e}")

    # 2. Резерв через Gemini
    if ai_client:
        for gm in ["gemini-2.0-flash", "gemini-1.5-flash"]:
            try:
                resp = ai_client.models.generate_content(
                    model=gm,
                    contents=prompt,
                    config={"system_instruction": sys_prompt}
                )
                return resp.text
            except Exception as e:
                print(f"Gemini {gm} error: {e}")

    raise RuntimeError("Все модели временно недоступны.")

async def process_task(task_text: str, message: types.Message):
    file_match = re.search(r"([a-zA-Z0-9_-]+\.(?:html|js|css|json))", task_text)
    target_file = file_match.group(1) if file_match else "index.html"
    status_msg = await message.reply(f"⚙️ Работаю над файлом `{target_file}`...")

    reset_words = ["с нуля", "заново", "перепиши полностью"]
    is_reset = any(w in task_text.lower() for w in reset_words)

    current_code = ""
    file_sha = None
    try:
        f_obj = gh.get_contents(target_file)
        file_sha = f_obj.sha
        if not is_reset:
            current_code = f_obj.decoded_content.decode("utf-8")
    except Exception:
        pass

    prompt = f"Целевой файл: {target_file}\n"
    if current_code:
        prompt += f"Текущий код файла:\n{current_code}\n\n"
    prompt += f"Задача от пользователя:\n{task_text}\n\nВерни полный код файла {target_file}."

    try:
        raw_result = await generate_with_ai(prompt, SYSTEM_PROMPT)
        new_code = clean_code(raw_result, target_file)
        commit_msg = f"Update {target_file}: {task_text[:35]}"
        if file_sha:
            gh.update_file(target_file, commit_msg, new_code, file_sha)
        else:
            gh.create_file(target_file, commit_msg, new_code)

        await status_msg.edit_text(
            f"✅ **Готово! Обновлен файл:** `{target_file}`\n"
            f"🚀 **Открыть игру:** {VERCEL_URL}"
        )
    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка: {str(e)}")

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

        messages = [{"role": "system", "content": DND_SCENARIO_PROMPT}]
        messages.append({
            "role": "system",
            "content": f"ТЕКУЩЕЕ СОСТОЯНИЕ ИГРОКА: Комната №{state.get('room', 1)}, Здоровье: {state.get('hp', 28)}/{state.get('maxHp', 28)}, КД: {state.get('ac', 16)}, Инвентарь: {', '.join(state.get('inventory', []))}."
        })
        for h in history[-8:]:
            messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})
        messages.append({"role": "user", "content": user_action})

        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.65,
            max_tokens=1200,
            response_format={"type": "json_object"}
        )
        raw_json = completion.choices[0].message.content
        parsed = json.loads(raw_json)
        return web.json_response(parsed, headers=CORS_HEADERS)
    except Exception as e:
        return web.json_response({
            "reply": f"Магический туман помешал связи с Древним ({str(e)}). Попробуй повторить действие!",
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
