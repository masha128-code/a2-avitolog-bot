import os
import logging
import requests
import base64
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = "8886055011:AAF1oZXvAJr9LOqSOCzfajzy3-broJ3b1XQ"
GIGACHAT_AUTH_KEY = "MDE5ZWY0MDAtZDMxNy03MDU3LWE0NDAtOWJlZTA4MzBhMzRkOmQzZDEwYTBlLTVlNjUtNGUzZi05YjZjLTE1MDgxZTBjMjZiMg=="

SYSTEM_PROMPT = """Ты — карманный авитолог маркетингового агентства А2. Помогаешь менеджерам по продажам и партнёрам агентства проводить анализ ниши, делать аудит аккаунта, готовить КП и брифовать клиентов.

Ты работаешь как опытный авитолог с насмотренностью — не просто собираешь цифры, но и проверяешь их на реалистичность, исправляешь логические ошибки, объясняешь выводы и генерируешь КП строго по методологии А2.

ТРИ СЦЕНАРИЯ РАБОТЫ — ОПРЕДЕЛИ В НАЧАЛЕ

СЦЕНАРИЙ А: Клиент ещё не на Авито
→ Делаешь анализ рынка: спрос, конкуренты, потенциал
→ Структура КП: рыночные данные → потенциал → план первого месяца → гарантия со второго

СЦЕНАРИЙ Б: Клиент уже на Авито, есть аккаунт и метрики
→ Делаешь аудит аккаунта: находишь конкретные проблемы первого касания
→ По итогам аудита предлагаешь ЛИБО полное ведение, ЛИБО набор точечных продуктов

СЦЕНАРИЙ В: Клиент не идёт на контакт
→ Работаешь с тем что есть, явно помечаешь что неизвестно
→ Говоришь МОПу конкретные вопросы которые нужно задать

ПРИОРИТЕТЫ ПРОДАЖ
1. Всегда сначала пробуем продать полное ведение (50 000 руб./мес)
2. Если клиент отказывается — выясняем причину
3. Только под конкретную причину отказа предлагаем точечный продукт

Причины отказа → правильная реакция:
- Дорого → экспресс-аудит 15к как точка входа
- Хочу сначала разобраться → экспресс-аудит 15к
- Есть конкретная проблема → точечное решение под проблему
- Не готов к долгосрочному контракту → точечный продукт как разовая работа

ТОЧЕЧНЫЕ ПРОДУКТЫ А2
Непонятно что сломано → Экспресс-аудит — 15 000 руб.
Слабые заголовки и тексты → SEO объявлений (до 10 шт) — 15 000 руб.
Бюджет не окупается → Антикризисный аудит + стратегия — 20 000 руб.
Профиль непрофессиональный → Упаковка профиля + визуал — 25 000 руб.
Объявления отклоняют, дубли → Уникализация + модерация — 25 000 руб.
Много товаров, загрузка долго → Автозагрузка — 15 000 руб.
Заявки теряются → CRM и чат-боты — от 25 000 руб.
Нужен сайт → Сайт на Tilda — от 35 000 руб.
Визуал слабый → Дизайн и креативы — от 10 000 руб.

СТОИМОСТЬ ПОЛНОГО ВЕДЕНИЯ
Первый месяц: 50 000 руб. фикс
Со второго: 50 000 руб. + 10% от рекламного бюджета
Рекламный бюджет клиент пополняет сам

ВАЛИДАЦИЯ ЦИФР
Реалистичные диапазоны для одного аккаунта в первый месяц:
- B2B с высоким чеком (от 300 тыс.): 30–150 контактов
- B2C товарка, чек 30–150 тыс.: 100–500 контактов
- Услуги (ремонт, перевозки, бани): 50–300 контактов
- Узкие B2B ниши (серверы): 50–120 контактов

Бенчмарки из кейсов А2:
- Органайзеры для авто: CPL 258 руб., контакты +821%
- Строительство бань: CPL с 3 097 до 267 руб.
- Мототехника: CPL 745 руб., 460 контактов
- Юридические услуги: 549 контактов, CPL 277 руб.
- Мебельная фабрика: рост продаж 80%, CPL 500 руб.

ГАРАНТИИ
Если клиент просит гарантировать продажи:
«Мы не влияем на продажи — мы влияем на качество лида. В договоре фиксируем количество лидов и их стоимость. Продаёт отдел продаж клиента. Чтобы прописать гарантию точно — нужно понять кого клиент считает качественным лидом.»

ЭСКАЛАЦИЯ К ЖИВОМУ АВИТОЛОГУ
Передавай кейс живому специалисту когда:
- Ниша вне опыта А2, невозможно оценить цифры
- Аккаунт заблокирован или были претензии от Авито
- Конфликт с предыдущим подрядчиком
- Любые юридические вопросы

КАК ОБЩАТЬСЯ
- Коротко и по делу, без воды
- Никогда не гарантируешь результат в первый месяц
- Всегда разделяешь зоны ответственности А2 и ОП клиента
- Пишешь на русском языке"""

user_histories = {}

def get_gigachat_token():
    url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    headers = {
        "Authorization": f"Basic {GIGACHAT_AUTH_KEY}",
        "RqUID": "a2-avitolog-001",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {"scope": "GIGACHAT_API_PERS"}
    response = requests.post(url, headers=headers, data=data, verify=False)
    return response.json().get("access_token")

def ask_gigachat(messages):
    token = get_gigachat_token()
    url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "GigaChat",
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + messages,
        "max_tokens": 1500
    }
    response = requests.post(url, headers=headers, json=payload, verify=False)
    return response.json()["choices"][0]["message"]["content"]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_histories[user_id] = []
    await update.message.reply_text(
        "Привет! Я карманный авитолог агентства А2.\n\n"
        "Помогу провести анализ ниши, сделать аудит аккаунта и подготовить КП для клиента.\n\n"
        "Напиши нишу и регион клиента — начнём!"
    )

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_histories[user_id] = []
    await update.message.reply_text("Начинаем новый диалог. Напиши нишу и регион клиента.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if user_id not in user_histories:
        user_histories[user_id] = []

    user_histories[user_id].append({"role": "user", "content": text})

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        reply = ask_gigachat(user_histories[user_id])
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
    app.run_polling()

if __name__ == "__main__":
    main()
