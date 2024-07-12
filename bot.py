import os
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, BotCommand, InlineKeyboardMarkup, InlineKeyboardButton
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Получение токена из переменной окружения
TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(TOKEN)

# Функция для чтения списка предметов из файла
def read_items():
    with open('hiking_items.txt', 'r', encoding='utf-8') as file:
        return [line.strip() for line in file if line.strip()]

# Глобальные переменные для хранения данных пользователей
user_progress = {}
user_responses = {}

def get_start_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    keyboard.add(KeyboardButton('Собраться в поход'), KeyboardButton('Посмотреть список'))
    return keyboard

def get_pack_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    keyboard.add(KeyboardButton('Да'), KeyboardButton('Нет'), KeyboardButton('Отложить'))
    return keyboard

def get_final_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    keyboard.add(KeyboardButton('Редактировать список'), KeyboardButton('Посмотреть весь список'))
    keyboard.add(KeyboardButton('Собраться заново'))
    return keyboard

def reset_progress(user_id):
    user_progress[user_id] = 0
    user_responses[user_id] = {}

@bot.message_handler(commands=['start', 'reset'])
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
    items = read_items()
    object_list = "\n".join([f"- {item}" for item in items])
    bot.send_message(message.chat.id, f"Вот полный список вещей для похода:\n\n{object_list}\n\nГотовы собираться?", reply_markup=get_start_keyboard())

def ask_object(chat_id, user_id):
    items = read_items()
    current_object = user_progress.get(user_id, 0)
    
    if current_object < len(items):
        bot.send_message(chat_id, f"{items[current_object]}?", reply_markup=get_pack_keyboard())
    else:
        finish_packing(chat_id, user_id)

@bot.message_handler(func=lambda message: message.text in ['Да', 'Нет', 'Отложить'])
def handle_response(message):
    user_id = message.from_user.id
    response = message.text.lower()
    
    items = read_items()
    current_object = user_progress.get(user_id, 0)
    
    if current_object < len(items):
        user_responses.setdefault(user_id, {})[items[current_object]] = response
        user_progress[user_id] = current_object + 1
        ask_object(message.chat.id, user_id)
    else:
        finish_packing(message.chat.id, user_id)

def finish_packing(chat_id, user_id):
    bot.send_message(chat_id, "Вы закончили сбор вещей. Вот ваши списки:")
    show_lists(chat_id, user_id)
    bot.send_message(chat_id, "Что вы хотите сделать дальше?", reply_markup=get_final_keyboard())

def show_lists(chat_id, user_id):
    responses = user_responses.get(user_id, {})
    
    packed = [item for item, status in responses.items() if status == 'да']
    not_packed = [item for item, status in responses.items() if status == 'нет']
    postponed = [item for item, status in responses.items() if status == 'отложить']
    
    result = "Ваши списки:\n\n"
    result += "Собрано:\n" + "\n".join(f"- {item}" for item in packed) + "\n\n"
    result += "Не собрано:\n" + "\n".join(f"- {item}" for item in not_packed) + "\n\n"
    result += "Отложено:\n" + "\n".join(f"- {item}" for item in postponed)
    
    bot.send_message(chat_id, result)

@bot.message_handler(func=lambda message: message.text == 'Редактировать список')
def edit_list(message):
    user_id = message.from_user.id
    items = read_items()
    responses = user_responses.get(user_id, {})
    
    if not responses:
        bot.send_message(message.chat.id, "У вас пока нет сохраненных ответов. Начните сбор заново.")
        return
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    for item in items:
        status = responses.get(item, 'Не задано')
        keyboard.add(InlineKeyboardButton(f"{item} - {status}", callback_data=f"edit_{item}"))
    
    bot.send_message(message.chat.id, "Выберите предмет для редактирования:", reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_'))
def edit_item(call):
    user_id = call.from_user.id
    item = call.data.split('_', 1)[1]
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(InlineKeyboardButton("Да", callback_data=f"status_{item}_да"))
    keyboard.add(InlineKeyboardButton("Нет", callback_data=f"status_{item}_нет"))
    keyboard.add(InlineKeyboardButton("Отложить", callback_data=f"status_{item}_отложить"))
    
    bot.edit_message_text(f"Выберите статус для предмета '{item}':", 
                          call.message.chat.id, 
                          call.message.message_id, 
                          reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data.startswith('status_'))
def set_status(call):
    user_id = call.from_user.id
    _, item, status = call.data.split('_')
    
    user_responses.setdefault(user_id, {})[item] = status
    
    bot.answer_callback_query(call.id, f"Статус обновлен: {status}")
    
    # Обновляем сообщение со списком после изменения статуса
    items = read_items()
    responses = user_responses.get(user_id, {})
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    for item in items:
        current_status = responses.get(item, 'Не задано')
        keyboard.add(InlineKeyboardButton(f"{item} - {current_status}", callback_data=f"edit_{item}"))
    
    bot.edit_message_text("Выберите предмет для редактирования:", 
                          call.message.chat.id, 
                          call.message.message_id, 
                          reply_markup=keyboard)

# Добавим логирование для отладки
@bot.message_handler(func=lambda message: True)
def log_all_messages(message):
    logging.info(f"Received message: {message.text}")
    if message.text == 'Редактировать список':
        edit_list(message)
    else:
        bot.send_message(message.chat.id, "Извините, я не понимаю эту команду. Пожалуйста, используйте кнопки или команды /start и /reset.")

@bot.message_handler(func=lambda message: message.text == 'Собраться заново')
def restart_packing(message):
    user_id = message.from_user.id
    reset_progress(user_id)
    bot.send_message(message.chat.id, "Давайте начнем сбор заново. Я буду задавать вопросы о каждом предмете.", reply_markup=get_pack_keyboard())
    ask_object(message.chat.id, user_id)

@bot.message_handler(func=lambda message: message.text == 'Посмотреть весь список')
def show_full_list_after_packing(message):
    items = read_items()
    object_list = "\n".join([f"- {item}" for item in items])
    bot.send_message(message.chat.id, f"Вот полный список вещей для похода:\n\n{object_list}")
    bot.send_message(message.chat.id, "Что вы хотите сделать дальше?", reply_markup=get_final_keyboard())

@bot.message_handler(func=lambda message: True)
def unknown_command(message):
    bot.send_message(message.chat.id, "Извините, я не понимаю эту команду. Пожалуйста, используйте кнопки или команды /start и /reset.")

def set_commands():
    bot.set_my_commands([
        BotCommand("start", "Начать работу с ботом"),
        BotCommand("reset", "Сбросить прогресс и начать заново")
    ])

if __name__ == '__main__':
    set_commands()
    logging.info("Bot started")
    while True:
        try:
            bot.polling(none_stop=True)
        except Exception as e:
            logging.error(f"Bot crashed. Restarting. Error: {e}")
            time.sleep(5)
