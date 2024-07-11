import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, BotCommand, InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3

TOKEN = '7208220434:AAEL3jd7Cec-0bYQ5d1ohT0zOkcoHYt-Y0s'
bot = telebot.TeleBot(TOKEN)

# Подключение к базе данных
conn = sqlite3.connect('hiking_bot.db', check_same_thread=False)
cursor = conn.cursor()

# Создание таблиц
cursor.execute('''
CREATE TABLE IF NOT EXISTS objects
(id INTEGER PRIMARY KEY, name TEXT NOT NULL)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS user_progress
(user_id INTEGER PRIMARY KEY, current_object INTEGER DEFAULT 0)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS user_responses
(user_id INTEGER, object_id INTEGER, status TEXT,
 PRIMARY KEY (user_id, object_id))
''')

# Добавление начальных объектов, если их нет
cursor.execute("SELECT COUNT(*) FROM objects")
if cursor.fetchone()[0] == 0:
    cursor.executemany("INSERT INTO objects (name) VALUES (?)", 
                       [('Палатка',), ('Спальник',), ('Пенка',), ('Фонарик',), ('Аптечка',)])
conn.commit()

def get_start_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    keyboard.add(KeyboardButton('Собраться в поход'), KeyboardButton('Посмотреть список'))
    return keyboard

def get_pack_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    keyboard.add(KeyboardButton('Собран'), KeyboardButton('Не собран'), KeyboardButton('Отложен'))
    return keyboard

def get_final_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    keyboard.add(KeyboardButton('Редактировать список'), KeyboardButton('Посмотреть весь список'))
    keyboard.add(KeyboardButton('Собраться заново'))
    return keyboard

def reset_progress(user_id):
    cursor.execute("DELETE FROM user_progress WHERE user_id = ?", (user_id,))
    cursor.execute("DELETE FROM user_responses WHERE user_id = ?", (user_id,))
    cursor.execute("INSERT OR REPLACE INTO user_progress (user_id, current_object) VALUES (?, 0)", (user_id,))
    conn.commit()

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    reset_progress(user_id)
    welcome_message = ("Привет! Я бот, который помогает собираться в поход. "
                       "Готовы ли вы начать собираться в поход или хотите посмотреть список вещей?")
    bot.send_message(message.chat.id, welcome_message, reply_markup=get_start_keyboard())

@bot.message_handler(func=lambda message: message.text == 'Собраться в поход')
def pack(message):
    user_id = message.from_user.id
    reset_progress(user_id)
    bot.send_message(message.chat.id, "Отлично! Давайте проверим, что вы собрали в поход. Я буду задавать вопросы о каждом предмете.", reply_markup=get_pack_keyboard())
    ask_object(message.chat.id, user_id)

@bot.message_handler(func=lambda message: message.text == 'Посмотреть список')
def show_full_list(message):
    cursor.execute("SELECT name FROM objects ORDER BY id")
    objects = cursor.fetchall()
    object_list = "\n".join([f"- {obj[0]}" for obj in objects])
    bot.send_message(message.chat.id, f"Вот полный список вещей для похода:\n\n{object_list}\n\nГотовы собираться?", reply_markup=get_start_keyboard())

def ask_object(chat_id, user_id):
    cursor.execute("SELECT current_object FROM user_progress WHERE user_id = ?", (user_id,))
    current_object = cursor.fetchone()[0]
    cursor.execute("SELECT * FROM objects ORDER BY id")
    objects = cursor.fetchall()
    
    if current_object < len(objects):
        object = objects[current_object]
        bot.send_message(chat_id, f"Вы собрали {object[1]}?", reply_markup=get_pack_keyboard())
    else:
        finish_packing(chat_id, user_id)

@bot.message_handler(func=lambda message: message.text in ['Собран', 'Не собран', 'Отложен'])
def handle_response(message):
    user_id = message.from_user.id
    response = message.text.lower()
    
    cursor.execute("SELECT current_object FROM user_progress WHERE user_id = ?", (user_id,))
    current_object = cursor.fetchone()[0]
    cursor.execute("SELECT * FROM objects ORDER BY id")
    objects = cursor.fetchall()
    
    cursor.execute("INSERT OR REPLACE INTO user_responses (user_id, object_id, status) VALUES (?, ?, ?)",
                   (user_id, objects[current_object][0], response))
    
    cursor.execute("UPDATE user_progress SET current_object = current_object + 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    
    ask_object(message.chat.id, user_id)

def finish_packing(chat_id, user_id):
    bot.send_message(chat_id, "Вы закончили сбор вещей. Вот ваши списки:")
    show_lists(chat_id, user_id)
    bot.send_message(chat_id, "Что вы хотите сделать дальше?", reply_markup=get_final_keyboard())

def show_lists(chat_id, user_id):
    cursor.execute("""
    SELECT o.name, ur.status
    FROM objects o
    LEFT JOIN user_responses ur ON o.id = ur.object_id AND ur.user_id = ?
    ORDER BY o.id
    """, (user_id,))
    
    responses = cursor.fetchall()
    
    packed = [item for item, status in responses if status == 'собран']
    not_packed = [item for item, status in responses if status == 'не собран']
    postponed = [item for item, status in responses if status == 'отложен']
    
    result = "Ваши списки:\n\n"
    result += "Собрано:\n" + "\n".join(f"- {item}" for item in packed) + "\n\n"
    result += "Не собрано:\n" + "\n".join(f"- {item}" for item in not_packed) + "\n\n"
    result += "Отложено:\n" + "\n".join(f"- {item}" for item in postponed)
    
    bot.send_message(chat_id, result)

@bot.message_handler(func=lambda message: message.text == 'Редактировать список')
def edit_list(message):
    user_id = message.from_user.id
    cursor.execute("""
    SELECT o.id, o.name, ur.status
    FROM objects o
    LEFT JOIN user_responses ur ON o.id = ur.object_id AND ur.user_id = ?
    ORDER BY o.id
    """, (user_id,))
    
    objects = cursor.fetchall()
    
    keyboard = InlineKeyboardMarkup()
    for obj_id, name, status in objects:
        status = status if status else 'Не задано'
        keyboard.add(InlineKeyboardButton(f"{name} - {status}", callback_data=f"edit_{obj_id}"))
    
    bot.send_message(message.chat.id, "Выберите предмет для редактирования:", reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_'))
def edit_item(call):
    user_id = call.from_user.id
    obj_id = int(call.data.split('_')[1])
    
    cursor.execute("SELECT name FROM objects WHERE id = ?", (obj_id,))
    obj_name = cursor.fetchone()[0]
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("Собран", callback_data=f"status_{obj_id}_собран"))
    keyboard.add(InlineKeyboardButton("Не собран", callback_data=f"status_{obj_id}_не собран"))
    keyboard.add(InlineKeyboardButton("Отложен", callback_data=f"status_{obj_id}_отложен"))
    
    bot.edit_message_text(f"Выберите статус для предмета '{obj_name}':", 
                          call.message.chat.id, 
                          call.message.message_id, 
                          reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data.startswith('status_'))
def set_status(call):
    user_id = call.from_user.id
    _, obj_id, status = call.data.split('_')
    obj_id = int(obj_id)
    
    cursor.execute("INSERT OR REPLACE INTO user_responses (user_id, object_id, status) VALUES (?, ?, ?)",
                   (user_id, obj_id, status))
    conn.commit()
    
    bot.answer_callback_query(call.id, f"Статус обновлен: {status}")
    edit_list(call.message)

@bot.message_handler(func=lambda message: message.text == 'Посмотреть весь список')
def show_full_list(message):
    cursor.execute("SELECT name FROM objects ORDER BY id")
    objects = cursor.fetchall()
    object_list = "\n".join([f"- {obj[0]}" for obj in objects])
    bot.send_message(message.chat.id, f"Вот полный список вещей для похода:\n\n{object_list}")
    bot.send_message(message.chat.id, "Что вы хотите сделать дальше?", reply_markup=get_final_keyboard())

@bot.message_handler(func=lambda message: message.text == 'Собраться заново')
def restart_packing(message):
    user_id = message.from_user.id
    reset_progress(user_id)
    bot.send_message(message.chat.id, "Давайте начнем сбор заново. Я буду задавать вопросы о каждом предмете.", reply_markup=get_pack_keyboard())
    ask_object(message.chat.id, user_id)

@bot.message_handler(commands=['reset'])
def reset(message):
    user_id = message.from_user.id
    reset_progress(user_id)
    bot.send_message(message.chat.id, "Ваш прогресс сброшен. Хотите начать собираться заново или посмотреть список вещей?", reply_markup=get_start_keyboard())

def set_commands():
    bot.set_my_commands([
        BotCommand("start", "Начать работу с ботом"),
        BotCommand("reset", "Сбросить прогресс и начать заново")
    ])

if __name__ == '__main__':
    set_commands()
    bot.polling(none_stop=True)
