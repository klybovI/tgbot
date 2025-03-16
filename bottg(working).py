import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    CallbackContext,
    MessageHandler,
    filters,
)
import sqlite3
import matplotlib.pyplot as plt
from datetime import datetime
import os

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация базы данных
conn = sqlite3.connect('user_data.db', check_same_thread=False)
cursor = conn.cursor()

# Удаление существующей таблицы, если она есть
cursor.execute('DROP TABLE IF EXISTS user_ratings')

# Создание таблицы с правильными столбцами
cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_ratings (
        user_id INTEGER,
        date TEXT,
        sleep INTEGER,
        mood INTEGER,
        productivity INTEGER,
        energy INTEGER
    )
''')
conn.commit()

# Токен бота
TOKEN = "6190615488:AAE2EabWEF4pZBXHTvRiWuv6Z7mS2iyrAwU"

async def start(update: Update, context: CallbackContext) -> None:
    keyboard = [[InlineKeyboardButton("Начнем!", callback_data='start_questions')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        await update.message.reply_text(
            "Привет! Я бот для отслеживания твоего состояния. Нажми 'Начнем!' чтобы продолжить.",
            reply_markup=reply_markup,
        )

async def start_questions(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "Оцени качество своего сна:",
        reply_markup=create_rating_keyboard(),
    )
    context.user_data['state'] = 'sleep'

def create_rating_keyboard():
    keyboard = [
        [InlineKeyboardButton(str(i), callback_data=str(i)) for i in range(1, 6)],
        [InlineKeyboardButton(str(i), callback_data=str(i)) for i in range(6, 11)],
    ]
    return InlineKeyboardMarkup(keyboard)

async def handle_rating(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    rating = int(query.data)

    if 'state' not in context.user_data:
        context.user_data['state'] = 'sleep'

    if context.user_data['state'] == 'sleep':
        context.user_data['sleep'] = rating
        await query.edit_message_text(text="Оцени качество своего сна: Выбрано {}".format(rating))
        await query.message.reply_text(
            "Как твое настроение?",
            reply_markup=create_rating_keyboard(),
        )
        context.user_data['state'] = 'mood'
    elif context.user_data['state'] == 'mood':
        context.user_data['mood'] = rating
        await query.edit_message_text(text="Настроение: Выбрано {}".format(rating))
        await query.message.reply_text(
            "Что на счёт продуктивности?",
            reply_markup=create_rating_keyboard(),
        )
        context.user_data['state'] = 'productivity'
    elif context.user_data['state'] == 'productivity':
        context.user_data['productivity'] = rating
        await query.edit_message_text(text="Продуктивность: Выбрано {}".format(rating))
        await query.message.reply_text(
            "Насколько полон энергии?",
            reply_markup=create_rating_keyboard(),
        )
        context.user_data['state'] = 'energy'
    elif context.user_data['state'] == 'energy':
        context.user_data['energy'] = rating
        await query.edit_message_text(text="Энергия: Выбрано {}".format(rating))

        # Сохранение в БД
        cursor.execute('''
            INSERT INTO user_ratings (user_id, date, sleep, mood, productivity, energy)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            user_id,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            context.user_data['sleep'],
            context.user_data['mood'],
            context.user_data['productivity'],
            context.user_data['energy'],
        ))
        conn.commit()

        # Предложение графиков
        keyboard = [
            [InlineKeyboardButton("Показать графики", callback_data='show_graphs')],
            [InlineKeyboardButton("Новый день", callback_data='new_day')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(
            "Хочешь посмотреть свои графики?",
            reply_markup=reply_markup,
        )

async def show_graphs(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    # Получение данных из БД
    cursor.execute('''
        SELECT date, sleep, mood, productivity, energy
        FROM user_ratings
        WHERE user_id = ?
        ORDER BY date
    ''', (user_id,))
    data = cursor.fetchall()

    if not data:
        await query.message.reply_text("Нет данных для построения графиков.")
        return

    # Построение графиков
    dates = [row[0] for row in data]
    metrics = {
        'Сон': [row[1] for row in data],
        'Настроение': [row[2] for row in data],
        'Продуктивность': [row[3] for row in data],
        'Энергия': [row[4] for row in data],
    }

    for name, values in metrics.items():
        plt.figure()
        plt.plot(dates, values, marker='o')
        plt.title(name)
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(f'{name}.png')
        plt.close()

        with open(f'{name}.png', 'rb') as photo:
            await query.message.reply_photo(photo=photo)
        os.remove(f'{name}.png')

    # Предложение начать новый день
    keyboard = [[InlineKeyboardButton("Да! Начинаем новый день!", callback_data='new_day')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text(
        "Провели свои анализы, начинаем новый день?",
        reply_markup=reply_markup,
    )

async def new_day(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "Оцени качество своего сна:",
        reply_markup=create_rating_keyboard(),
    )
    context.user_data['state'] = 'sleep'

def main() -> None:
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(start_questions, pattern='^start_questions$'))
    application.add_handler(CallbackQueryHandler(handle_rating, pattern='^[0-9]+$'))
    application.add_handler(CallbackQueryHandler(show_graphs, pattern='^show_graphs$'))
    application.add_handler(CallbackQueryHandler(new_day, pattern='^new_day$'))

    application.run_polling()

if __name__ == '__main__':
    main()
