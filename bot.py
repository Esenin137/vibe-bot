import os
import asyncio
from aiogram import Bot, Dispatcher, F, types
from github import Github
from google import genai
from groq import Groq
from aiohttp import web

TG_TOKEN = os.getenv("TG_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
GROQ_KEY = os.getenv("GROQ_API_KEY")
VERCEL_URL = os.getenv("VERCEL_URL")

bot = Bot(token=TG_TOKEN)
dp = Dispatcher()
groq_client = Groq(api_key=GROQ_KEY)
ai_client = genai.Client(api_key=GEMINI_KEY)
gh = Github(GITHUB_TOKEN).get_repo(GITHUB_REPO)

SYSTEM_PROMPT = """
Ты — элитный разработчик мобильных веб-приложений и HTML5/Canvas игр.
Твоя цель: сгенерировать ПОЛНЫЙ, рабочий файл index.html, содержащий CSS и JS внутри.
Правила:
1. Обязателен метатег viewport для мобильных устройств: <meta name="viewport" content="width=device-width, initial-scale=1.0">
2. Приложение/игра должно поддерживать сенсорное управление (Touch events, Pointer events).
3. Верни ТОЛЬКО чистый исходный код без тройных кавычек ```html и без пояснительного текста.
"""

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
        # Здесь мы указали нужную модель, которую просит Google
        response = ai_client.models.generate_content(
            model="gemini-3.8-flash",
            contents=prompt,
            config={"system_instruction": SYSTEM_PROMPT}
        )

        new_code = response.text.strip()
        if new_code.startswith("```"):
            new_code = "\n".join(new_code.split("\n")[1:])
        if new_code.endswith("```"):
            new_code = "\n".join(new_code.split("\n")[:-1])
        new_code = new_code.strip()

        commit
        
