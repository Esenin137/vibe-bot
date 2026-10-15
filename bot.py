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
Ты — элитный разработчик мобильных веб-приложений и HTML5 игр.
Сгенерируй ПОЛНЫЙ, рабочий файл index.html (HTML + CSS + JS в одном файле).
ЖЁСТКИЕ ПРАВИЛА:
1. Начни ответ строго с <!DOCTYPE html> и ОБЯЗАТЕЛЬНО закончи закрывающими тегами </script></body></html>. Никакого текста до или после кода!
2. Пиши компактный, но красивый и функциональный код (до 250–300 строк), чтобы файл гарантированно поместился целиком и не оборвался на середине!
3. НЕ используй новые CSS-свойства (ЗАПРЕЩЕНЫ: inset, dvh, clamp, min(), max(), aspect-ratio, place-items, gap во flex). Используй только классические top/left/right/bottom, 100vh, display: flex, margin/padding и стандартные размеры в px/% для 100% совместимости со всеми версиями мобильных браузеров и WebView.
4. Все кнопки и клики должны надежно работать через стандартный addEventListener('click', ...) и 'touchstart'.
"""

def clean_html(raw_text: str) -> str:
    # Убираем блок рассуждений <think>...</think>, если модель его добавила
    raw_text = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL | re.IGNORECASE)
    
    # Если внутри есть блок ```html ... ```, достаем только его содержимое
    match = re.search(r"```(?:html)?\s*(<!DOCTYPE html>.*?</html>)\s*```", raw_text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
        
    # Иначе просто вырезаем от <!DOCTYPE html> (или <html) до </html>
    match2 = re.search(r"(<!DOCTYPE html>.*</html>|<html.*</html>)", raw_text, re.DOTALL | re.IGNORECASE)
    if match2:
        return match2.group(1).strip()
        
    # Если модель все равно не успела закрыть тег, аккуратно закрываем сами
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = "\n".join(cleaned.split("\n")[1:])
    if cleaned.endswith("```"):
        cleaned = "\n".join(cleaned.split("\n")[:-1])
    cleaned = cleaned.strip()
    
    if "<!doctype html>" in cleaned.lower():
        idx = cleaned.lower().find("<!doctype html>")
        cleaned = cleaned[idx:]
        
    return cleaned

def generate_code_with_ai(prompt: str) -> str:
    errors = []

    if groq_client:
        try:
            avail_models = [
                m.id for m in groq_client.models.list().data
                if not any(bad in m.id.lower() for bad in ["whisper", "guard", "tts", "vision"])
            ]
            # Приоритет отдаем проверенным моделям Llama и Qwen без лишних "рассуждений"
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
    status_msg = await message.reply("⚙️ Архитектор думает и пишет код...")
    
    try:
        current_file = gh.get_contents("index.html")
        current_code = current_file.decoded_content.decode("utf-8")
        file_sha = current_file.sha
    except Exception:
        current_code = ""
        file_sha = None

    # Если просят написать "с нуля" или старый файл слишком огромный/битый, начинаем с чистого листа
    if "с нуля" in task_text.lower() or len(current_code) > 25000 or "</html>" not in current_code.lower():
        prompt = f"Задача от пользователя:\n{task_text}\n\nНапиши полный рабочий файл index.html с нуля (компактно, до 250 строк, обязательно закрой </html>)."
    else:
        prompt = f"Текущий код проекта:\n{current_code}\n\nЗадача от пользователя:\n{task_text}\n\nНапиши обновленный файл index.html целиком (компактно, обязательно закрой </html>)."

    try:
        raw_output = generate_code_with_ai(prompt)
        new_code = clean_html(raw_output)

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
                    
