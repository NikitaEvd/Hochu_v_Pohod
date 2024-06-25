import os
import telebot
import sqlite3
from telebot.types import ReplyKeyboardMarkup, KeyboardButton

# Получаем токен из переменной окружения
TOKEN = "7156094450:AAFJOMhaCNmLkQ2_M1gWXYGZLG-mpyuhiYw"
bot = telebot.TeleBot(TOKEN)

# Подключение к базе данных
conn = sqlite3.connect('hiking_bot.db', check_same_thread=False)
cursor = conn.cursor()

# Создание таблицы для хранения объектов
cursor.execute('''
CREATE TABLE IF NOT EXISTS objects
(id INTEGER PRIMARY KEY, name TEXT NOT NULL)
''')

# Создание таблицы для хранения прогресса пользователей
cursor.execute('''
CREATE TABLE IF NOT EXISTS user_progress
(user_id INTEGER PRIMARY KEY, current_object INTEGER DEFAULT 0)
''')

# Создание таблицы для хранения ответов пользователей
cursor.execute('''
CREATE TABLE IF NOT EXISTS user_responses
(user_id INTEGER, object_id INTEGER, status TEXT,
 PRIMARY KEY (user_id, object_id))
''')

conn.commit()

# Функция для получения списка объектов
def get_objects():
    cursor.execute("SELECT * FROM objects ORDER BY id")
    return cursor.fetchall()

# Функция для получения клавиатуры
def get_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    keyboard.add(KeyboardButton('Собран'), KeyboardButton('Отложен'), KeyboardButton('Не будет собран'))
    return keyboard

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    cursor.execute("INSERT OR REPLACE INTO user_progress (user_id, current_object) VALUES (?, 0)", (user_id,))
    conn.commit()
    bot.send_message(message.chat.id, "Привет! Давай проверим, что вы собрали в поход. Отвечайте на вопросы, используя кнопки.", reply_markup=get_keyboard())
    ask_object(message.chat.id, user_id)

def ask_object(chat_id, user_id):
    cursor.execute("SELECT current_object FROM user_progress WHERE user_id = ?", (user_id,))
    current_object = cursor.fetchone()[0]
    objects = get_objects()
    
    if current_object < len(objects):
        object = objects[current_object]
        bot.send_message(chat_id, f"Объект: {object[1]}?", reply_markup=get_keyboard())
    else:
        finish_packing(chat_id, user_id)

@bot.message_handler(func=lambda message: True)
def handle_response(message):
    user_id = message.from_user.id
    response = message.text.lower()
    
    if response not in ['собран', 'отложен', 'не будет собран']:
        bot.send_message(message.chat.id, "Пожалуйста, используйте кнопки для ответа.", reply_markup=get_keyboard())
        return
    
    cursor.execute("SELECT current_object FROM user_progress WHERE user_id = ?", (user_id,))
    current_object = cursor.fetchone()[0]
    objects = get_objects()
    
    cursor.execute("INSERT OR REPLACE INTO user_responses (user_id, object_id, status) VALUES (?, ?, ?)",
                   (user_id, objects[current_object][0], response))
    
    cursor.execute("UPDATE user_progress SET current_object = current_object + 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    
    ask_object(message.chat.id, user_id)

def finish_packing(chat_id, user_id):
    cursor.execute("""
    SELECT o.name, ur.status
    FROM objects o
    JOIN user_responses ur ON o.id = ur.object_id
    WHERE ur.user_id = ?
    """, (user_id,))
    
    responses = cursor.fetchall()
    
    packed = [item for item, status in responses if status == 'собран']
    postponed = [item for item, status in responses if status == 'отложен']
    not_packed = [item for item, status in responses if status == 'не будет собран']
    
    result = "Вот ваши списки:\n\n"
    result += "Собрано:\n" + "\n".join(packed) + "\n\n"
    result += "Отложено:\n" + "\n".join(postponed) + "\n\n"
    result += "Не будет собрано:\n" + "\n".join(not_packed)
    
    bot.send_message(chat_id, result)
    
    # Очистка прогресса пользователя
    cursor.execute("DELETE FROM user_progress WHERE user_id = ?", (user_id,))
    cursor.execute("DELETE FROM user_responses WHERE user_id = ?", (user_id,))
    conn.commit()

# Функция для добавления объектов (для владельца бота)
@bot.message_handler(commands=['add_object'])
def add_object(message):
    # Здесь должна быть проверка на права владельца
    object_name = message.text.split(maxsplit=1)[1]
    cursor.execute("INSERT INTO objects (name) VALUES (?)", (object_name,))
    conn.commit()
    bot.reply_to(message, f"Объект '{object_name}' добавлен в список.")

# Функция для удаления объектов (для владельца бота)
@bot.message_handler(commands=['remove_object'])
def remove_object(message):
    # Здесь должна быть проверка на права владельца
    object_name = message.text.split(maxsplit=1)[1]
    cursor.execute("DELETE FROM objects WHERE name = ?", (object_name,))
    conn.commit()
    bot.reply_to(message, f"Объект '{object_name}' удален из списка.")

# Функция для просмотра списка объектов (для владельца бота)
@bot.message_handler(commands=['list_objects'])
def list_objects(message):
    # Здесь должна быть проверка на права владельца
    objects = get_objects()
    object_list = "\n".join([f"{obj[0]}. {obj[1]}" for obj in objects])
    bot.reply_to(message, f"Список объектов:\n{object_list}")

if __name__ == '__main__':
    bot.polling(none_stop=True)
