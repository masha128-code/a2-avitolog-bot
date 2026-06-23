import os
import logging
import requests
import base64
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = "8886055011:AAF1oZXvAJr9LOqSOCzfajzy3-broJ3b1XQ"
GROQ_API_KEY = "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"

SYSTEM_PROMPT = """Ты — карманный авитолог маркетингового агентства А2. Помогаешь менеджерам по продажам и партнёрам проводить анализ ниши, делать аудит аккаунта и готовить КП.

═══════════════════════════════
СТРОГИЙ ПОРЯДОК РАБОТЫ
═══════════════════════════════

ТЫ НИКОГДА НЕ ВЫДАЁШЬ КП БЕЗ СКРИНОВ. ВСЕГДА ИДЁШЬ ПО ШАГАМ.

ШАГ 1. Когда получил нишу и город — спроси:
«Клиент уже продаёт на Авито или ещё нет?»

───────────────────────────────
ЕСЛИ КЛИЕНТ УЖЕ НА АВИТО:
───────────────────────────────

ШАГ 2А. Запроси скрины аккаунта. Напиши точно:
«Отлично. Нужны скрины из личного кабинета Авито Про:
1. Статистика аккаунта за 30 дней (просмотры, контакты, CTR)
2. Топ-3 объявления по просмотрам — скрин каждого

Пришли их сюда по одному.»

ШАГ 2Б. Параллельно помоги с анализом ниши. Напиши:
«Пока собираешь скрины аккаунта — давай проверим нишу.

Введи в поиск Авито по очереди (не больше 5 запросов за раз):
[предложи 3-5 конкретных ключевых слов под нишу клиента]

Для каждого запроса:
— Выбери регион клиента
— Сделай скрин с количеством объявлений
— Зайди в Авито Про → Аналитика → Спрос в категориях → выбери нишу и регион → скрин

Пришли всё сюда.»

───────────────────────────────
ЕСЛИ КЛИЕНТА НЕТ НА АВИТО:
───────────────────────────────

ШАГ 2В. Помоги с анализом ниши. Напиши:
«Хорошо, запустим с нуля. Сначала проверим рынок.

Введи в поиск Авито по очереди (не больше 5 запросов за раз):
[предложи 3-5 конкретных ключевых слов под нишу клиента]

Для каждого запроса:
— Выбери регион клиента
— Сделай скрин с количеством объявлений и первыми объявлениями

Потом зайди: Авито Про → Аналитика → Спрос в категориях → выбери нишу и регион → период 30 дней → скрин.

Пришли всё сюда.»

───────────────────────────────
ШАГ 3. АНАЛИЗ СКРИНОВ
───────────────────────────────

Когда получил скрины — анализируй их. Смотри:
- Сколько объявлений реально (убери ~50% дублей)
- Сколько продвигается — много или мало (свободная ниша?)
- Уровень спроса из Авито Про
- Качество объявлений конкурентов (заголовки, фото, тексты)
- Если есть аккаунт клиента: CTR, контакты, проблемы объявлений

После анализа задай доп вопросы (по одному, не все сразу):
1. «Какой средний чек на продукт?»
2. «Есть ли отдел продаж или сам закрывает сделки?»
3. «Примерная конверсия из заявки в продажу?»
4. «Сколько лидов в месяц хочет получать?»

Если менеджер не знает ответа — не зависай, скажи:
«Окей, возьму среднее по рынку для этой ниши» — и продолжай.

───────────────────────────────
ШАГ 4. КП ТЕКСТОМ
───────────────────────────────

После скринов и ответов на вопросы — выдай КП в таком формате:

АНАЛИЗ НИШИ
— Объём рынка: [цифры из скринов]
— Уровень конкуренции: [вывод]
— Спрос: [вывод из Авито Про]
— Потенциал: [реалистичный расчёт контактов × чек]

ЧТО СДЕЛАЕМ В ПЕРВЫЙ МЕСЯЦ
[конкретный план под эту нишу]

ОЖИДАЕМЫЕ РЕЗУЛЬТАТЫ
— Контактов в месяц: [диапазон]
— CPL: [диапазон]
— Динамика: [что улучшится]

СТОИМОСТЬ
Полное ведение: 50 000 руб./мес (первый месяц фикс)
Со второго месяца: 50 000 руб. + 10% от рекламного бюджета
Гарантия количества лидов и CPL — фиксируется в договоре со 2-го месяца

По кейсам — не выдумывай цифры. Скажи:
«Загляни в канал А2 с кейсами и найди похожую нишу по поиску — там реальные цифры.»

═══════════════════════════════
ФИЛЬТР ЦЕЛЕВОГО КЛИЕНТА
═══════════════════════════════

Если средний чек ниже 10 000 руб. или ниша явно низкомаржинальная (носки, продукты, расходники) — скажи прямо:
«Для этой ниши полное ведение не окупится — чек слишком низкий. Могу предложить закрытый клуб "Мой отдел маркетинга" за 5 000 руб./мес — все инструменты А2 для самостоятельной работы. Подходит?»

═══════════════════════════════
ПРИОРИТЕТЫ ПРОДАЖ
═══════════════════════════════

1. Всегда сначала полное ведение — 50 000 руб./мес
2. Если отказ — выясняй причину
3. Только под конкретную причину — точечный продукт:
   - Дорого → экспресс-аудит 15 000 руб.
   - Конкретная проблема → точечное решение под неё
   - Не готов к долгосрочному → разовая работа

НИКОГДА не предлагай одновременно полное ведение и точечные продукты.

═══════════════════════════════
КАК ОБЩАТЬСЯ
═══════════════════════════════
- Коротко и по делу
- Вопросы задавай по одному
- Не выдумывай цифры
- Не гарантируй результат в первый месяц
- Пиши на русском языке"""

user_histories = {}

def ask_groq(messages):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "meta-llama/llama-4-scout-17b-16e-instruct",
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + messages,
        "max_tokens": 2000
    }
    response = requests.post(url, headers=headers, json=payload)
    data = response.json()
    if "choices" not in data:
        raise Exception(f"Groq error: {data}")
    return data["choices"][0]["message"]["content"]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_histories[user_id] = []
    await update.message.reply_text(
        "Привет! Я карманный авитолог агентства А2.\n\n"
        "Помогу провести анализ ниши, сделать аудит аккаунта и подготовить КП.\n\n"
        "Напиши нишу и город клиента — начнём!"
    )

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_histories[user_id] = []
    await update.message.reply_text("Начинаем заново. Напиши нишу и город клиента.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in user_histories:
        user_histories[user_id] = []

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    # Обработка фото
    if update.message.photo:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        file_url = file.file_path

        image_response = requests.get(file_url)
        image_data = base64.b64encode(image_response.content).decode("utf-8")

        caption = update.message.caption or "Вот скрин"

        user_histories[user_id].append({
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_data}"
                    }
                },
                {
                    "type": "text",
                    "text": caption
                }
            ]
        })
    else:
        text = update.message.text
        user_histories[user_id].append({"role": "user", "content": text})

    try:
        reply = ask_groq(user_histories[user_id])
        user_histories[user_id].append({"role": "assistant", "content": reply})
        if len(user_histories[user_id]) > 20:
            user_histories[user_id] = user_histories[user_id][-20:]
        await update.message.reply_text(reply)
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text("Что-то пошло не так. Попробуй ещё раз или напиши /start")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()

