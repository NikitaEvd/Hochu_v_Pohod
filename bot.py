import os
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, BotCommand, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
import logging
import time
import traceback

# Расширенное логирование
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Получение токена
TOKEN = os.environ.get('BOT_TOKEN')
if TOKEN is None:
    raise ValueError("Произошла ошибка: переменная окружения BOT_TOKEN не может быть 'None'")

bot = telebot.TeleBot(TOKEN)

# Чтение файла
def read_items():
    try:
        with open('hiking_items.txt', 'r', encoding='utf-8') as file:
            return [line.strip() for line in file if line.strip()]
    except FileNotFoundError:
        logger.error("Файл 'hiking_items.txt' не найден")
        return []
    except Exception as e:
        logger.error(f"Ошибка при чтении файла: {e}")
        return []

user_progress = {}
user_responses = {}

# Функции создания клавиатур
def get_start_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    keyboard.add(KeyboardButton('Собраться в поход'), KeyboardButton('Посмотреть список'))
    return keyboard

def get_pack_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    keyboard.add(KeyboardButton('Беру'), KeyboardButton('Возьму позже'), KeyboardButton('В этот поход не буду брать'))
    return keyboard

def get_final_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.row(InlineKeyboardButton("Редактировать список", callback_data="edit_list"))
    keyboard.row(InlineKeyboardButton("Посмотреть весь список", callback_data="show_full_list"))
    keyboard.row(InlineKeyboardButton("Собраться заново", callback_data="restart_packing"))
    return keyboard

def reset_progress(user_id):
    user_progress[user_id] = 0
    user_responses[user_id] = {}

# Хендлеры сообщений
@bot.message_handler(commands=['start', 'reset'])
def start(message):
    logger.info(f"Received start/reset command from user {message.from_user.id}")
    user_id = message.from_user.id
    reset_progress(user_id)
    welcome_message = ("Привет! Я бот, который помогает собраться в поход. "
                       "Начнем собираться или вы хотите проверить список вещей?")
    bot.send_message(message.chat.id, welcome_message, reply_markup=get_start_keyboard())

@bot.message_handler(func=lambda message: message.text == 'Собраться в поход')
def pack(message):
    logger.info(f"User {message.from_user.id} started packing")
    user_id = message.from_user.id
    reset_progress(user_id)
    bot.send_message(message.chat.id, "Отлично, тогда начнем! Не забудьте:", reply_markup=get_pack_keyboard())
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
        logger.debug(f"Asking user {user_id} about item: {items[current_object]}")
        bot.send_message(chat_id, f"{items[current_object]}?", reply_markup=get_pack_keyboard())
    else:
        finish_packing(chat_id, user_id)

@bot.message_handler(func=lambda message: message.text in ['Беру', 'Возьму позже', 'В этот поход не буду брать'])
def handle_response(message):
    user_id = message.from_user.id
    response = message.text.lower()

    items = read_items()
    current_object = user_progress.get(user_id, 0)

    if current_object < len(items):
        logger.debug(f"User {user_id} responded {response} to item {items[current_object]}")
        user_responses.setdefault(user_id, {})[items[current_object]] = response
        user_progress[user_id] = current_object + 1
        ask_object(message.chat.id, user_id)
    else:
        finish_packing(message.chat.id, user_id)

def finish_packing(chat_id, user_id):
    logger.info(f"Finishing packing for user {user_id}")
    bot.send_message(chat_id, "Ура, список закончился.", reply_markup=ReplyKeyboardRemove())
    show_lists(chat_id, user_id)
    final_keyboard = get_final_keyboard()
    logger.info(f"Sending final keyboard to user {user_id}: {final_keyboard}")
    bot.send_message(chat_id, "Что дальше?", reply_markup=final_keyboard)

def show_lists(chat_id, user_id):
    responses = user_responses.get(user_id, {})

    packed = [item for item, status in responses.items() if status == 'беру']
    not_packed = [item for item, status in responses.items() if status == 'возьму позже']
    postponed = [item for item, status in responses.items() if status == 'в этот поход не буду брать']

    result = "Вот, что получилось:\n\n"
    result += "Уже в рюкзаке:\n" + "\n".join(f"- {item}" for item in packed) + "\n\n"
    result += "Не забыть положить позже:\n" + "\n".join(f"- {item}" for item in not_packed) + "\n\n"
    result += "Не будете брать в этот поход:\n" + "\n".join(f"- {item}" for item in postponed)

    bot.send_message(chat_id, result)

@bot.callback_query_handler(func=lambda call: call.data == "edit_list")
def handle_edit_list(call):
    logger.info(f"Received 'Редактировать список' callback from user {call.from_user.id}")
    try:
        if user_responses.get(call.from_user.id):
            logger.debug(f"User {call.from_user.id} has saved responses. Proceeding to edit_list.")
            edit_list(call.message)
        else:
            logger.warning(f"User {call.from_user.id} has no saved responses.")
            bot.answer_callback_query(call.id, "У вас нет сохраненных ответов. Начните сбор заново.")
            bot.send_message(call.message.chat.id, "У вас пока нет сохраненных ответов. Начните сбор заново.")
    except Exception as e:
        logger.error(f"Error in handle_edit_list for user {call.from_user.id}: {str(e)}")
        logger.error(traceback.format_exc())
        bot.answer_callback_query(call.id, "Произошла ошибка при обработке запроса.")
        bot.send_message(call.message.chat.id, "Извините, произошла ошибка при обработке вашего запроса.")

def edit_list(message):
    logger.debug(f"Entered edit_list function for user {message.chat.id}")
    try:
        user_id = message.chat.id
        items = read_items()
        responses = user_responses.get(user_id, {})

        if not responses:
            logger.info(f"No saved responses for user {user_id}")
            bot.send_message(message.chat.id, "У вас пока нет сохраненных ответов. Начните сбор заново.")
            return

        logger.debug(f"Creating keyboard for item editing for user {user_id}")
        keyboard = InlineKeyboardMarkup(row_width=1)
        for item in items:
            status = responses.get(item, 'Не задано')
            callback_data = f"edit_{item[:45]}"
            keyboard.add(InlineKeyboardButton(f"{item} - {status}", callback_data=callback_data))

        keyboard.add(InlineKeyboardButton("Назад", callback_data="back_to_final"))

        logger.debug(f"Sending edit list message to user {user_id}")
        bot.edit_message_text("Выберите предмет для редактирования:", 
                              message.chat.id, 
                              message.message_id, 
                              reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Error in edit_list for user {message.chat.id}: {str(e)}")
        logger.error(traceback.format_exc())
        bot.send_message(message.chat.id, "Извините, произошла ошибка при отображении списка для редактирования.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_'))
def edit_item(call):
    logger.info(f"Received edit callback from user {call.from_user.id}")
    try:
        user_id = call.from_user.id
        item_prefix = call.data.split('_', 1)[1]

        items = read_items()
        full_item = next((i for i in items if i.startswith(item_prefix)), item_prefix)

        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(InlineKeyboardButton("Беру", callback_data=f"status_{full_item[:45]}_беру"))
        keyboard.add(InlineKeyboardButton("Возьму позже", callback_data=f"status_{full_item[:45]}_возьму позже"))
        keyboard.add(InlineKeyboardButton("В этот поход не буду брать", callback_data=f"status_{full_item[:45]}_в этот поход не буду брать"))
        keyboard.add(InlineKeyboardButton("Назад", callback_data="back_to_edit"))

        bot.edit_message_text(f"Выберите статус для предмета '{full_item}':", 
                              call.message.chat.id, 
                              call.message.message_id, 
                              reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Error in edit_item for user {call.from_user.id}: {str(e)}")
        logger.error(traceback.format_exc())
        bot.answer_callback_query(call.id, "Произошла ошибка при обработке запроса.")
        bot.send_message(call.message.chat.id, "Извините, произошла ошибка при редактировании предмета.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('status_'))
def set_status(call):
    logger.info(f"Received status callback from user {call.from_user.id}")
    user_id = call.from_user.id
    _, item_prefix, status = call.data.split('_')

    items = read_items()
    full_item = next((i for i in items if i.startswith(item_prefix)), item_prefix)

    user_responses.setdefault(user_id, {})[full_item] = status

    bot.answer_callback_query(call.id, f"Статус обновлен: {status}")

    edit_list_callback(call)

@bot.callback_query_handler(func=lambda call: call.data == "back_to_edit")
def edit_list_callback(call):
    logger.debug(f"Returning to edit list for user {call.from_user.id}")
    user_id = call.from_user.id
    items = read_items()
    responses = user_responses.get(user_id, {})

    keyboard = InlineKeyboardMarkup(row_width=1)
    for item in items:
        status = responses.get(item, 'Не задано')
        callback_data = f"edit_{item[:45]}"
        keyboard.add(InlineKeyboardButton(f"{item} - {status}", callback_data=callback_data))

    keyboard.add(InlineKeyboardButton("Назад", callback_data="back_to_final"))

    bot.edit_message_text("Выберите предмет для редактирования:", 
                          call.message.chat.id, 
                          call.message.message_id, 
                          reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data == "back_to_final")
def back_to_final(call):
    logger.info(f"Returning to final menu for user {call.from_user.id}")
    bot.edit_message_text("Что вы хотите сделать дальше?", 
                          call.message.chat.id, 
                          call.message.message_id, 
                          reply_markup=get_final_keyboard())

@bot.callback_query_handler(func=lambda call: call.data == "restart_packing")
def restart_packing(call):
    logger.info(f"User {call.from_user.id} requested to restart packing")
    user_id = call.from_user.id
    reset_progress(user_id)
    bot.delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, "Давайте начнем сбор заново. Я буду задавать вопросы о каждом предмете.", reply_markup=get_pack_keyboard())
    ask_object(call.message.chat.id, user_id)

@bot.callback_query_handler(func=lambda call: call.data == "show_full_list")
def show_full_list_after_packing(call):
    logger.info(f"User {call.from_user.id} requested full list after packing")
    items = read_items()
    object_list = "\n".join([f"- {item}" for item in items])
    bot.send_message(call.message.chat.id, f"Вот полный список вещей для похода:\n\n{object_list}")
    bot.edit_message_text("Что вы хотите сделать дальше?", 
                          call.message.chat.id, 
                          call.message.message_id, 
                          reply_markup=get_final_keyboard())

@bot.message_handler(func=lambda message: True)
def echo_all(message):
    logger.debug(f"Received message: '{message.text}' from user {message.from_user.id}")
    bot.reply_to(message, "Извините, я не понимаю эту команду. Пожалуйста, используйте /start или /reset.")

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
            logger.error(traceback.format_exc())
            time.sleep(10)
