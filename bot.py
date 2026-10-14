import os
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

SYSTEM_PROMPT = """
Ты — элитный разработчик мобильных веб-приложений и HTML5/Canvas игр.
Твоя цель: сгенерировать ПОЛНЫЙ, рабочий файл index.html, содержащий CSS и JS внутри.
Правила:
1. Обязателен метатег viewport для мобильных устройств: <meta name="viewport" content="width=device-width, initial-scale=1.0">
2. Приложение/игра должно поддерживать сенсорное управление (Touch events, Pointer events).
3. Верни ТОЛЬКО чистый исходный код без тройных кавычек ```html и без пояснительного текста.
"""

def generate_code_with_ai(prompt: str) -> str:
    errors = []

    # 1. Автоматически ищем доступные текстовые модели в Groq и пробуем их
    if groq_client:
        try:
            avail_models = [
                m.id for m in groq_client.models.list().data
                if "whisper" not in m.id.lower() and "guard" not in m.id.lower() and "tts" not in m.id.lower()
            ]
            # Ставим самые мощные модели (llama / qwen / deepseek) первыми в очередь
            preferred = [m for m in avail_models if any(k in m.lower() for k in ["llama-3.3", "llama-3.1", "qwen", "deepseek", "llama"])]
            models_to_try = preferred + [m for m in avail_models if m not in preferred]

            for g_model in models_to_try[:4]:
                try:
                    chat_completion = groq_client.chat.completions.create(
                        messages=[
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": prompt}
                        ],
                        model=g_model,
                        temperature=0.5,
                    )
                    return chat_completion.choices[0].message.content
                except Exception as e:
                    errors.append(f"Groq ({g_model}): {str(e)[:120]}")
        except Exception as e:
            errors.append(f"Groq Key/List Error: {str(e)[:150]}")
    else:
        errors.append("GROQ_API_KEY пуст в настройках Render")

    # 2. Пробуем модели Gemini
    if ai_client:
        for m_name in ["gemini-3.8-flash-lite", "gemini-3.8-pro", "gemini-3.8-flash", "gemini-2.5-pro"]:
            try:
                response = ai_client.models.generate_content(
                    model=m_name,
                    contents=prompt,
                    config={"system_instruction": SYSTEM_PROMPT}
                )
                return response.text
            except Exception as e:
                errors.append(f"Gemini ({m_name}): {str(e)[:120]}")
    else:
        errors.append("GEMINI_API_KEY пуст в настройках Render")

    raise Exception("Детали ошибок API:\n" + "\n".join(errors[:4]))

async def process_task(task_text: str, message: types.Message):
    status_msg = await message.reply("⚙️ Архитектор думает и пишет код...")
    
    try:
        current_file = gh.get_contents("index.html")
        current_code = current_file.decoded_content.decode("utf-8")
        file_sha = current_file.sha
    except Exception:
        current_code = ""
        file_sha = None

    prompt = f"Текущий код проекта:\n{current_code}\n\nЗадача от пользователя:\n{task_text}\n\nНапиши обновленный файл index.html целиком."

    try:
        raw_output = generate_code_with_ai(prompt)
        new_code = raw_output.strip()
        
        if new_code.startswith("```"):
            new_code = "\n".join(new_code.split("\n")[1:])
        if new_code.endswith("```"):
            new_code = "\n".join(new_code.split("\n")[:-1])
        new_code = new_code.strip()

        commit_msg = f"Vibe update: {task_text[:40]}"
        if file_sha:
            gh.update_file("index.html", commit_msg, new_code, file_sha)
        else:
            gh.create_file("index.html", commit_msg, new_code)

        await status_msg.edit_text(
            f"✅ **Готово!**\n\n📝 **Задача:** {task_text}\n🚀 **Проверяй билд:** {VERCEL_URL}"
        )
    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка:\n{str(e)[:3500]}")

@dp.message(F.voice)
async def handle_voice(message: types.Message):
    wait_msg = await message.reply("🎙 Распознаю голос...")
    file_id = message.voice.file_id
    file = await bot.get_file(file_id)
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

async def handle_ping(request):
    return web.Response(text="Bot is running!")

async def start_dummy_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def main():
    print("Бот запущен...")
    await start_dummy_web_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
    
