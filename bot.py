import os
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, BotCommand, InlineKeyboardMarkup, InlineKeyboardButton
import logging
import time

# Настройка логирования
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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
    logger.info(f"Received start/reset command from user {message.from_user.id}")
    user_id = message.from_user.id
    reset_progress(user_id)
    welcome_message = ("Привет! Я бот, который помогает собираться в поход. "
                       "Готовы ли вы начать собираться в поход или хотите посмотреть список вещей?")
    bot.send_message(message.chat.id, welcome_message, reply_markup=get_start_keyboard())

@bot.message_handler(func=lambda message: message.text == 'Собраться в поход')
def pack(message):
    logger.info(f"User {message.from_user.id} started packing")
    user_id = message.from_user.id
    reset_progress(user_id)
    bot.send_message(message.chat.id, "Отлично! Давайте проверим, что вы собрали в поход. Я буду задавать вопросы о каждом предмете.", reply_markup=get_pack_keyboard())
    ask_object(message.chat.id, user_id)

@bot.message_handler(func=lambda message: message.text == 'Посмотреть список')
def show_full_list(message):
    logger.info(f"User {message.from_user.id} requested full list")
    items = read_items()
    object_list = "\n".join([f"- {item}" for item in items])
    bot.send_message(message.chat.id, f"Вот полный список вещей для похода:\n\n{object_list}\n\nГотовы собираться?", reply_markup=get_start_keyboard())

def ask_object(chat_id, user_id):
    items = read_items()
    current_object = user_progress.get(user_id, 0)
    
    if current_object < len(items):
        logger.info(f"Asking user {user_id} about item: {items[current_object]}")
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
        logger.info(f"User {user_id} responded {response} to item {items[current_object]}")
        user_responses.setdefault(user_id, {})[items[current_object]] = response
        user_progress[user_id] = current_object + 1
        ask_object(message.chat.id, user_id)
    else:
        finish_packing(message.chat.id, user_id)

def finish_packing(chat_id, user_id):
    logger.info(f"Finishing packing for user {user_id}")
    bot.send_message(chat_id, "Вы закончили сбор вещей. Вот ваши списки:")
    show_lists(chat_id, user_id)
    final_keyboard = get_final_keyboard()
    logger.info(f"Sending final keyboard to user {user_id}: {final_keyboard}")
    bot.send_message(chat_id, "Что вы хотите сделать дальше?", reply_markup=final_keyboard)

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
def handle_edit_list(message):
    logger.info(f"Received 'Редактировать список' command from user {message.from_user.id}")
    edit_list(message)

def edit_list(message):
    logger.info(f"Entered edit_list function for user {message.from_user.id}")
    user_id = message.from_user.id
    items = read_items()
    responses = user_responses.get(user_id, {})
    
    if not responses:
        logger.info(f"No saved responses for user {user_id}")
        bot.send_message(message.chat.id, "У вас пока нет сохраненных ответов. Начните сбор заново.")
        return
    
    logger.info(f"Creating keyboard for item editing for user {user_id}")
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    for item in items:
        status = responses.get(item, 'Не задано')
        keyboard.add(KeyboardButton(f"{item} - {status}"))
    
    logger.info(f"Sending edit list message to user {user_id}")
    bot.send_message(message.chat.id, "Выберите предмет для редактирования:", reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_'))
def edit_item(call):
    logger.info(f"Received edit callback from user {call.from_user.id}")
    user_id = call.from_user.id
    item = call.data.split('_', 1)[1]
    
    # Находим полное имя item из списка items
    items = read_items()
    full_item = next((i for i in items if i.startswith(item)), item)
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(InlineKeyboardButton("Да", callback_data=f"status_{full_item[:45]}_да"))
    keyboard.add(InlineKeyboardButton("Нет", callback_data=f"status_{full_item[:45]}_нет"))
    keyboard.add(InlineKeyboardButton("Отложить", callback_data=f"status_{full_item[:45]}_отложить"))
    
    bot.edit_message_text(f"Выберите статус для предмета '{full_item}':", 
                          call.message.chat.id, 
                          call.message.message_id, 
                          reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data.startswith('status_'))
def set_status(call):
    logger.info(f"Received status callback from user {call.from_user.id}")
    user_id = call.from_user.id
    _, item_prefix, status = call.data.split('_')
    
    # Находим полное имя item из списка items
    items = read_items()
    full_item = next((i for i in items if i.startswith(item_prefix)), item_prefix)
    
    user_responses.setdefault(user_id, {})[full_item] = status
    
    bot.answer_callback_query(call.id, f"Статус обновлен: {status}")
    
    # Обновляем сообщение со списком после изменения статуса
    responses = user_responses.get(user_id, {})
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    for item in items:
        current_status = responses.get(item, 'Не задано')
        callback_data = f"edit_{item[:50]}"
        keyboard.add(InlineKeyboardButton(f"{item} - {current_status}", callback_data=callback_data))
    
    bot.edit_message_text("Выберите предмет для редактирования:", 
                          call.message.chat.id, 
                          call.message.message_id, 
                          reply_markup=keyboard)

@bot.message_handler(func=lambda message: message.text == 'Собраться заново')
def restart_packing(message):
    logger.info(f"User {message.from_user.id} requested to restart packing")
    user_id = message.from_user.id
    reset_progress(user_id)
    bot.send_message(message.chat.id, "Давайте начнем сбор заново. Я буду задавать вопросы о каждом предмете.", reply_markup=get_pack_keyboard())
    ask_object(message.chat.id, user_id)

@bot.message_handler(func=lambda message: message.text == 'Посмотреть весь список')
def show_full_list_after_packing(message):
    logger.info(f"User {message.from_user.id} requested full list after packing")
    items = read_items()
    object_list = "\n".join([f"- {item}" for item in items])
    bot.send_message(message.chat.id, f"Вот полный список вещей для похода:\n\n{object_list}")
    bot.send_message(message.chat.id, "Что вы хотите сделать дальше?", reply_markup=get_final_keyboard())

@bot.message_handler(func=lambda message: True)
def echo_all(message):
    logger.info(f"Received message: '{message.text}' from user {message.from_user.id}")
    if message.text == 'Редактировать список':
        logger.info("Calling handle_edit_list directly")
        handle_edit_list(message)
    else:
        bot.reply_to(message, "Извините, я не понимаю эту команду. Пожалуйста, используйте кнопки или команды /start и /reset.")

def set_commands():
    bot.set_my_commands([
        BotCommand("start", "Начать работу с ботом"),
        BotCommand("reset", "Сбросить прогресс и начать заново")
    ])

if __name__ == '__main__':
    set_commands()
    logger.info("Bot started")
    while True:
        try:
            logger.info("Starting bot polling")
            bot.polling(none_stop=True)
        except Exception as e:
            logger.error(f"Bot crashed. Restarting. Error: {e}")
            time.sleep(5)
