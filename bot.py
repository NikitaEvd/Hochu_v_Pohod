import os
import telebot
import sqlite3
from telebot.types import ReplyKeyboardMarkup, KeyboardButton

# Получаем токен из переменной окружения
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
bot = telebot.TeleBot(TOKEN)

# Подключение к базе данных
conn = sqlite3.connect('hiking_bot.db', check_same_thread=False)
cursor = conn.cursor()

# Создание таблиц, если они не существуют
cursor.execute('''
CREATE TABLE IF NOT EXISTS items
(id INTEGER PRIMARY KEY, name TEXT NOT NULL)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS user_progress
(user_id INTEGER PRIMARY KEY, current_item INTEGER DEFAULT 0)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS user_responses
(user_id INTEGER, item_id INTEGER, response TEXT,
 PRIMARY KEY (user_id, item_id))
''')

conn.commit()

# Функция для получения списка предметов
def get_items():
    cursor.execute("SELECT * FROM items")
    return cursor.fetchall()

# Функция для получения клавиатуры
def get_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    keyboard.add(KeyboardButton('Да'), KeyboardButton('Нет'), KeyboardButton('Нужно собрать'))
    return keyboard

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    cursor.execute("INSERT OR REPLACE INTO user_progress (user_id, current_item) VALUES (?, 0)", (user_id,))
    conn.commit()
    bot.send_message(message.chat.id, "Привет! Давай соберемся в поход. Отвечай на вопросы, используя кнопки.", reply_markup=get_keyboard())
    ask_item(message.chat.id, user_id)

def ask_item(chat_id, user_id):
    cursor.execute("SELECT current_item FROM user_progress WHERE user_id = ?", (user_id,))
    current_item = cursor.fetchone()[0]
    items = get_items()
    
    if current_item < len(items):
        item = items[current_item]
        bot.send_message(chat_id, f"Взяли ли вы {item[1]}?", reply_markup=get_keyboard())
    else:
        finish_packing(chat_id, user_id)

@bot.message_handler(func=lambda message: True)
def handle_response(message):
    user_id = message.from_user.id
    response = message.text.lower()
    
    if response not in ['да', 'нет', 'нужно собрать']:
        bot.send_message(message.chat.id, "Пожалуйста, используйте кнопки для ответа.", reply_markup=get_keyboard())
        return
    
    cursor.execute("SELECT current_item FROM user_progress WHERE user_id = ?", (user_id,))
    current_item = cursor.fetchone()[0]
    items = get_items()
    
    cursor.execute("INSERT OR REPLACE INTO user_responses (user_id, item_id, response) VALUES (?, ?, ?)",
                   (user_id, items[current_item][0], response))
    
    cursor.execute("UPDATE user_progress SET current_item = current_item + 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    
    ask_item(message.chat.id, user_id)

def finish_packing(chat_id, user_id):
    cursor.execute("""
    SELECT i.name, ur.response
    FROM items i
    JOIN user_responses ur ON i.id = ur.item_id
    WHERE ur.user_id = ?
    """, (user_id,))
    
    responses = cursor.fetchall()
    
    packed = [item for item, resp in responses if resp == 'да']
    not_packed = [item for item, resp in responses if resp == 'нет']
    to_pack = [item for item, resp in responses if resp == 'нужно собрать']
    
    result = "Вот ваши списки:\n\n"
    result += "Собрано:\n" + "\n".join(packed) + "\n\n"
    result += "Не взято:\n" + "\n".join(not_packed) + "\n\n"
    result += "Нужно собрать:\n" + "\n".join(to_pack)
    
    bot.send_message(chat_id, result)
    
    # Очистка прогресса пользователя
    cursor.execute("DELETE FROM user_progress WHERE user_id = ?", (user_id,))
    cursor.execute("DELETE FROM user_responses WHERE user_id = ?", (user_id,))
    conn.commit()

# Функция для добавления предметов (для администратора)
@bot.message_handler(commands=['add_item'])
def add_item(message):
    # Здесь должна быть проверка на права администратора
    item_name = message.text.split(maxsplit=1)[1]
    cursor.execute("INSERT INTO items (name) VALUES (?)", (item_name,))
    conn.commit()
    bot.reply_to(message, f"Предмет '{item_name}' добавлен в список.")

if __name__ == '__main__':
    bot.polling(none_stop=True)