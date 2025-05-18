import sqlite3
import datetime
import matplotlib.pyplot as plt
import io
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, JobQueue
from telegram import Update
from telegram.ext import CallbackContext

# Токен бота
TOKEN = '8197710075:AAHJWTUTR6-uU6zXL4V1bJd6pt2YT6hSFzY'

# Инициализация базы данных SQLite
def init_db():
    conn = sqlite3.connect('mood.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS moods 
                 (user_id INTEGER, timestamp TEXT, mood TEXT)''')
    conn.commit()
    conn.close()

# Сохранение настроения в базу данных
def save_mood(user_id, mood):
    conn = sqlite3.connect('mood.db')
    c = conn.cursor()
    timestamp = datetime.datetime.now().isoformat()
    c.execute("INSERT INTO moods (user_id, timestamp, mood) VALUES (?, ?, ?)", 
              (user_id, timestamp, mood))
    conn.commit()
    conn.close()

# Получение настроений за указанный период (в днях)
def get_moods(user_id, days):
    conn = sqlite3.connect('mood.db')
    c = conn.cursor()
    start_date = (datetime.datetime.now() - datetime.timedelta(days=days)).isoformat()
    c.execute("SELECT mood, timestamp FROM moods WHERE user_id = ? AND timestamp >= ?", 
              (user_id, start_date))
    moods = c.fetchall()
    conn.close()
    return moods

# Создание графика настроений
def create_mood_graph(moods, period):
    mood_counts = {'Отличное': 0, 'Хорошее': 0, 'Грустное': 0, 'Плохое': 0}
    dates = []
    for mood, timestamp in moods:
        mood_counts[mood] += 1
        date = datetime.datetime.fromisoformat(timestamp).date()
        if date not in dates:
            dates.append(date)

    # Подготовка данных для графика
    labels = ['Положительное (Отличное/Хорошее)', 'Отрицательное (Грустное/Плохое)']
    good_moods = mood_counts['Отличное'] + mood_counts['Хорошее']
    bad_moods = mood_counts['Грустное'] + mood_counts['Плохое']
    total = good_moods + bad_moods
    sizes = [good_moods, bad_moods] if total > 0 else [1, 0]
    colors = ['#4CAF50', '#F44336']  # Зеленый для хорошего, красный для плохого

    # Создание круговой диаграммы
    plt.figure(figsize=(6, 6))
    plt.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=140)
    plt.title(f'Статистика настроения за {period} дней')
    
    # Сохранение графика в память
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close()
    return buf

# Команда /start
def start(update: Update, context: CallbackContext):
    update.message.reply_text(
        'Привет! Я MoodBuddy, твой бот для отслеживания настроения. '
        'Используй /mood, чтобы записать свое настроение, или /stats, чтобы посмотреть статистику.'
    )

# Команда /mood
def mood(update: Update, context: CallbackContext):
    update.message.reply_text(
        'Какое у тебя настроение? Выбери: Отличное, Хорошее, Грустное, Плохое'
    )
    context.user_data['awaiting_mood'] = True

# Обработка текстовых сообщений
def handle_message(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    text = update.message.text

    # Проверка, ожидается ли ввод настроения
    if context.user_data.get('awaiting_mood'):
        valid_moods = ['Отличное', 'Хорошее', 'Грустное', 'Плохое']
        if text in valid_moods:
            save_mood(user_id, text)
            update.message.reply_text(f'Настроение "{text}" записано!')
            context.user_data['awaiting_mood'] = False
        else:
            update.message.reply_text('Пожалуйста, выбери одно из: Отличное, Хорошее, Грустное, Плохое')
    else:
        update.message.reply_text('Я не знаю, что с этим делать. Используй /mood или /stats.')

# Команда /stats
def stats(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    period = 7  # По умолчанию неделя
    if context.args:
        try:
            period = int(context.args[0])
            if period not in [7, 30]:
                raise ValueError
        except ValueError:
            update.message.reply_text('Укажи период: 7 или 30 дней. Например: /stats 7')
            return

    moods = get_moods(user_id, period)
    if not moods:
        update.message.reply_text(f'Нет данных о настроении за последние {period} дней.')
        return

   # Подсчет статистики
    good_moods = sum(1 for mood, _ in moods if mood in ['Отличное', 'Хорошее'])
    total_moods = len(moods)
    good_percentage = (good_moods / total_moods * 100) if total_moods > 0 else 0

    # Создание и отправка графика
    graph = create_mood_graph(moods, period)
    update.message.reply_photo(photo=graph, 
                              caption=f'За {period} дней:\n'
                                      f'Положительное настроение: {good_percentage:.1f}%\n'
                                      f'Всего записей: {total_moods}')

# Напоминание о записи настроения
def daily_reminder(context: CallbackContext):
    job = context.job
    chat_id = job.context
    context.bot.send_message(chat_id=chat_id, 
                            text='Эй, не забудь записать свое настроение! Используй /mood')

# Команда для включения напоминаний
def set_reminder(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    context.job_queue.run_daily(daily_reminder, 
                               time=datetime.time(hour=20, minute=0),  # 20:00 ежедневно
                               context=chat_id)
    update.message.reply_text('Напоминания включены! Я буду писать каждый день в 20:00.')

# Основная функция
def main():
    init_db()
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    jq = updater.job_queue

    # Обработчики команд
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("mood", mood))
    dp.add_handler(CommandHandler("stats", stats))
    dp.add_handler(CommandHandler("remind", set_reminder))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    # Запуск бота
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()