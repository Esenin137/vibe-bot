import os
import re
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
Ты — элитный разработчик мобильных веб-приложений и текстовых игр.
Ты умеешь работать как с главным файлом index.html, так и со вспомогательными файлами (.js, .css, .json).
ЖЁСТКИЕ ПРАВИЛА:
1. Выдавай ТОЛЬКО чистый код запрашиваемого файла без пояснений до или после кода!
2. Если пишем index.html — начни с <!DOCTYPE html> и закончи на </html>.
3. Если пишем .js файл (например, chapter1.js с массивом сцен) — выдавай только чистый валидный JavaScript-код.
4. Не используй проблемные новые CSS-свойства (inset, dvh, clamp, place-items).
"""

def clean_code(raw_text: str, filename: str) -> str:
    raw_text = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL | re.IGNORECASE).strip()
    
    # Если внутри блока ```...```, достаем содержимое
    match = re.search(r"```(?:html|javascript|js|css|json)?\s*(.*?)\s*```", raw_text, re.DOTALL | re.IGNORECASE)
    if match:
        raw_text = match.group(1).strip()

    if filename.endswith(".html"):
        match_html = re.search(r"(<!DOCTYPE html>.*</html>|<html.*</html>)", raw_text, re.DOTALL | re.IGNORECASE)
        if match_html:
            return match_html.group(1).strip()
    return raw_text.strip()

def generate_code_with_ai(prompt: str) -> str:
    errors = []
    if groq_client:
        try:
            avail_models = [
                m.id for m in groq_client.models.list().data
                if not any(bad in m.id.lower() for bad in ["whisper", "guard", "tts", "vision"])
            ]
            preferred = [m for m in avail_models if any(k in m.lower() for k in ["llama-3.3", "llama-3.1", "qwen", "llama"])]
            models_to_try = preferred + [m for m in avail_models if m not in preferred]

            for g_model in models_to_try[:4]:
                try:
                    chat_completion = groq_client.chat.completions.create(
                        messages=[
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": prompt}
                        ],
                        model=g_model,
                        temperature=0.3,
                        max_tokens=8000,
                    )
                    return chat_completion.choices[0].message.content
                except Exception as e:
                    errors.append(f"Groq ({g_model}): {str(e)[:120]}")
        except Exception as e:
            errors.append(f"Groq List Error: {str(e)[:150]}")

    if ai_client:
        for m_name in ["gemini-1.5-flash", "gemini-2.0-flash-lite", "gemini-1.5-pro"]:
            try:
                response = ai_client.models.generate_content(
                    model=m_name,
                    contents=prompt,
                    config={"system_instruction": SYSTEM_PROMPT}
                )
                return response.text
            except Exception as e:
                errors.append(f"Gemini ({m_name}): {str(e)[:120]}")

    raise Exception("Детали ошибок API:\n" + "\n".join(errors[:4]))

async def process_task(task_text: str, message: types.Message):
    # Определяем, какой файл просит создать/изменить пользователь (по умолчанию index.html)
    file_match = re.search(r"([a-zA-Z0-9_-]+\.(?:html|js|css|json))", task_text)
    target_file = file_match.group(1) if file_match else "index.html"

    status_msg = await message.reply(f"⚙️ Работаю над файлом `{target_file}`...")

    try:
        repo_files = [f.path for f in gh.get_contents("")]
    except Exception:
        repo_files = []

    try:
        current_file = gh.get_contents(target_file)
        current_code = current_file.decoded_content.decode("utf-8")
        file_sha = current_file.sha
    except Exception:
        current_code = ""
        file_sha = None

    # Подгружаем контекст index.html, если создаем вспомогательный файл, чтобы ИИ знал имена переменных
    main_context = ""
    if target_file != "index.html" and "index.html" in repo_files:
        try:
            main_context = gh.get_contents("index.html").decoded_content.decode("utf-8")[:6000]
        except Exception:
            pass

    if "с нуля" in task_text.lower() or not current_code:
        prompt = (
            f"Файлы в проекте: {', '.join(repo_files)}\n"
            f"{f'Код главного файла index.html для контекста:{chr(10)}{main_context}{chr(10)}' if main_context else ''}"
            f"Задача от пользователя:\n{task_text}\n\n"
            f"Напиши полный рабочий код для файла {target_file} с нуля."
        )
    else:
        prompt = (
            f"Файлы в проекте: {', '.join(repo_files)}\n"
            f"Текущий код файла {target_file}:\n{current_code}\n\n"
            f"Задача от пользователя:\n{task_text}\n\n"
            f"Напиши обновленный файл {target_file} целиком."
        )

    try:
        raw_output = generate_code_with_ai(prompt)
        new_code = clean_code(raw_output, target_file)
        commit_msg = f"Vibe update {target_file}: {task_text[:30]}"
        
        if file_sha:
            gh.update_file(target_file, commit_msg, new_code, file_sha)
        else:
            gh.create_file(target_file, commit_msg, new_code)

        await status_msg.edit_text(
            f"✅ **Готово!** Обновлен файл: `{target_file}`\n\n"
            f"📂 **Файлы проекта:** `{', '.join(repo_files) if repo_files else target_file}`\n"
            f"🚀 **Проверяй билд:** {VERCEL_URL}"
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
        
