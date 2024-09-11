import os
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, BotCommand, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
import logging
import time
import traceback
import hashlib
import re
from messages import *

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
        logger.error(FILE_NOT_FOUND_ERROR)
        return []
    except Exception as e:
        logger.error(FILE_READ_ERROR.format(e))
        return []

user_progress = {}
user_responses = {}

# Функции создания клавиатур

def get_start_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    keyboard.add(KeyboardButton(BUTTON_PACK), KeyboardButton(BUTTON_SHOW_LIST))
    return keyboard

def get_pack_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    keyboard.add(KeyboardButton(BUTTON_TAKE), KeyboardButton(BUTTON_TAKE_LATER), KeyboardButton(BUTTON_SKIP))
    return keyboard

def get_final_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.row(InlineKeyboardButton(BUTTON_EDIT_LIST, callback_data="edit_list"))
    keyboard.row(InlineKeyboardButton(BUTTON_SHOW_FULL_LIST, callback_data="show_full_list"))
    keyboard.row(InlineKeyboardButton(BUTTON_RESTART_PACKING, callback_data="restart_packing"))
    return keyboard

def reset_progress(user_id):
    user_progress[user_id] = 0
    user_responses[user_id] = {}

# Работа со списком

def get_item_name(item):
    name_without_description = re.sub(r'\s*\(.*?\)\s*', '', item).strip()
    clean_name = re.sub(r'[*_`]', '', name_without_description)
    return clean_name

def get_status_icon(status):
    if status.lower() == BUTTON_TAKE.lower():
        return "✅"  
    elif status.lower() == BUTTON_SKIP.lower():
        return "❌"  
    elif status.lower() == BUTTON_TAKE_LATER.lower():
        return "⏳"  
    else:
        return "❓"  

# Хендлеры сообщений

@bot.message_handler(commands=[COMMAND_START, COMMAND_RESET])
def start(message):
    logger.info(f"Received start/reset command from user {message.from_user.id}")
    user_id = message.from_user.id
    reset_progress(user_id)
    bot.send_message(message.chat.id, START_MESSAGE, reply_markup=get_start_keyboard())

@bot.message_handler(func=lambda message: message.text == BUTTON_PACK)
def pack(message):
    logger.info(f"User {message.from_user.id} started packing")
    user_id = message.from_user.id
    reset_progress(user_id)
    bot.send_message(message.chat.id, PACK_START_MESSAGE, reply_markup=get_pack_keyboard())
    ask_object(message.chat.id, user_id)

@bot.message_handler(func=lambda message: message.text == BUTTON_SHOW_LIST)
def show_full_list(message):
    logger.info(f"User {message.from_user.id} requested full list")
    items = read_items()
    object_list = "\n".join([f"• {item}" for item in items])
    
    # Создаем клавиатуру с кнопкой "Начать сборы"
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    keyboard.add(KeyboardButton(BUTTON_PACK))
    
    # Отправляем сообщение с списком вещей, используя Markdown для форматирования
    bot.send_message(message.chat.id, 
                     SHOW_FULL_LIST_PROMPT.format(object_list), 
                     reply_markup=keyboard, 
                     parse_mode='Markdown')

def ask_object(chat_id, user_id):
    items = read_items()
    current_object = user_progress.get(user_id, 0)

    if current_object < len(items):
        logger.debug(f"Asking user {user_id} about item: {items[current_object]}")
        try:
            bot.send_message(chat_id, ITEM_PROMPT.format(items[current_object]), 
                             reply_markup=get_pack_keyboard(),
                             parse_mode='Markdown')
        except telebot.apihelper.ApiException as e:
            logger.error(f"Failed to send message with Markdown. Sending without formatting. Error: {e}")
            bot.send_message(chat_id, ITEM_PROMPT.format(items[current_object]), 
                             reply_markup=get_pack_keyboard())
    else:
        finish_packing(chat_id, user_id)

@bot.message_handler(func=lambda message: message.text in [BUTTON_TAKE, BUTTON_TAKE_LATER, BUTTON_SKIP])
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
    bot.send_message(chat_id, PACKING_FINISHED_MESSAGE, reply_markup=ReplyKeyboardRemove())
    show_lists(chat_id, user_id)
    final_keyboard = get_final_keyboard()
    logger.info(f"Sending final keyboard to user {user_id}: {final_keyboard}")
    bot.send_message(chat_id, WHAT_NEXT_MESSAGE, reply_markup=final_keyboard)

def show_lists(chat_id, user_id):
    responses = user_responses.get(user_id, {})

    packed = [item for item, status in responses.items() if status.lower() == BUTTON_TAKE.lower()]
    not_packed = [item for item, status in responses.items() if status.lower() == BUTTON_TAKE_LATER.lower()]
    postponed = [item for item, status in responses.items() if status.lower() == BUTTON_SKIP.lower()]

    result = "Вот, что получилось:\n\n"
    
    if packed:
        result += "Уже в рюкзаке:\n" + "\n".join(f"- {item}" for item in packed) + "\n\n"
    
    if not_packed:
        result += "Не забыть положить позже:\n" + "\n".join(f"- {item}" for item in not_packed) + "\n\n"
    
    if postponed:
        result += "Не будете брать в этот поход:\n" + "\n".join(f"- {item}" for item in postponed)

    # Удаляем лишние пустые строки в конце
    result = result.rstrip()

    try:
        bot.send_message(chat_id, result, parse_mode='Markdown')
    except telebot.apihelper.ApiException as e:
        logger.error(f"Failed to send message with Markdown. Sending without formatting. Error: {e}")
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
            bot.answer_callback_query(call.id, NO_SAVED_RESPONSES)
            bot.send_message(call.message.chat.id, NO_SAVED_RESPONSES)
    except Exception as e:
        logger.error(f"Error in handle_edit_list for user {call.from_user.id}: {str(e)}")
        logger.error(traceback.format_exc())
        bot.answer_callback_query(call.id, GENERAL_ERROR)
        bot.send_message(call.message.chat.id, GENERAL_ERROR)

def generate_short_callback(prefix, data):
    """Generate a short callback data using a hash function."""
    hash_object = hashlib.md5(data.encode())
    return f"{prefix}_{hash_object.hexdigest()[:10]}"

def edit_list(message):
    logger.debug(f"Entered edit_list function for user {message.chat.id}")
    try:
        user_id = message.chat.id
        items = read_items()
        responses = user_responses.get(user_id, {})

        if not responses:
            logger.info(f"No saved responses for user {user_id}")
            bot.send_message(message.chat.id, NO_SAVED_RESPONSES)
            return

        logger.debug(f"Creating keyboard for item editing for user {user_id}")
        keyboard = InlineKeyboardMarkup(row_width=1)
        for item in items:
            status = responses.get(item, 'Не задано')
            callback_data = generate_short_callback("edit", item)
            item_name = get_item_name(item)
            status_icon = get_status_icon(status)
            button_text = f"{item_name} {status_icon}"
            keyboard.add(InlineKeyboardButton(button_text, callback_data=callback_data))

        keyboard.add(InlineKeyboardButton(BUTTON_BACK, callback_data="back_to_final"))

        logger.debug(f"Sending edit list message to user {user_id}")
        try:
            bot.edit_message_text(CHOOSE_ITEM_TO_EDIT, 
                                  message.chat.id, 
                                  message.message_id, 
                                  reply_markup=keyboard)
        except telebot.apihelper.ApiTelegramException as api_error:
            logger.error(f"Telegram API error: {str(api_error)}")
            if "message is not modified" in str(api_error).lower():
                logger.info("Message content is the same, sending new message instead of editing")
                bot.send_message(message.chat.id, CHOOSE_ITEM_TO_EDIT, reply_markup=keyboard)
            else:
                raise
    except Exception as e:
        logger.error(f"Error in edit_list for user {message.chat.id}: {str(e)}")
        logger.error(traceback.format_exc())
        bot.send_message(message.chat.id, EDIT_LIST_ERROR)

@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_'))
def edit_item(call):
    logger.info(f"Received edit callback from user {call.from_user.id}")
    try:
        user_id = call.from_user.id
        item_hash = call.data.split('_', 1)[1]

        items = read_items()
        full_item = next((item for item in items if generate_short_callback("edit", item).split('_')[1] == item_hash), None)

        if full_item is None:
            logger.error(f"Item not found for hash {item_hash}")
            bot.answer_callback_query(call.id, GENERAL_ERROR)
            return

        keyboard = InlineKeyboardMarkup(row_width=1)
        statuses = [BUTTON_TAKE, BUTTON_TAKE_LATER, BUTTON_SKIP]
        for status in statuses:
            callback_data = generate_short_callback("status", f"{full_item}_{status}")
            keyboard.add(InlineKeyboardButton(status, callback_data=callback_data))
        keyboard.add(InlineKeyboardButton(BUTTON_BACK, callback_data="back_to_edit"))

        bot.edit_message_text(CHOOSE_ITEM_STATUS.format(full_item), 
                              call.message.chat.id, 
                              call.message.message_id, 
                              reply_markup=keyboard,
                              parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error in edit_item for user {call.from_user.id}: {str(e)}")
        logger.error(traceback.format_exc())
        bot.answer_callback_query(call.id, GENERAL_ERROR)
        bot.send_message(call.message.chat.id, EDIT_ITEM_ERROR)

@bot.callback_query_handler(func=lambda call: call.data.startswith('status_'))
def set_status(call):
    logger.info(f"Received status callback from user {call.from_user.id}")
    try:
        user_id = call.from_user.id
        status_hash = call.data.split('_', 1)[1]

        items = read_items()
        full_item = None
        chosen_status = None

        for item in items:
            for status in [BUTTON_TAKE, BUTTON_TAKE_LATER, BUTTON_SKIP]:
                if generate_short_callback("status", f"{item}_{status}").split('_')[1] == status_hash:
                    full_item = item
                    chosen_status = status
                    break
            if full_item:
                break

        if not full_item or not chosen_status:
            logger.error(f"Item or status not found for hash {status_hash}")
            bot.answer_callback_query(call.id, GENERAL_ERROR)
            return

        user_responses.setdefault(user_id, {})[full_item] = chosen_status

        status_icon = get_status_icon(chosen_status)
        bot.answer_callback_query(call.id, f"{STATUS_UPDATED}: {status_icon}")

        # Обновляем сообщение с текущим статусом редактирования
        edit_list(call.message)
    except Exception as e:
        logger.error(f"Error in set_status for user {call.from_user.id}: {str(e)}")
        logger.error(traceback.format_exc())
        bot.answer_callback_query(call.id, GENERAL_ERROR)
        bot.send_message(call.message.chat.id, UPDATE_STATUS_ERROR)

@bot.callback_query_handler(func=lambda call: call.data == "back_to_edit")
def edit_list_callback(call):
    logger.debug(f"Returning to edit list for user {call.from_user.id}")
    user_id = call.from_user.id
    items = read_items()
    responses = user_responses.get(user_id, {})

    keyboard = InlineKeyboardMarkup(row_width=1)
    for item in items:
        status = responses.get(item, 'Не задано')
        callback_data = generate_short_callback("edit", item)
        item_name = get_item_name(item)
        status_icon = get_status_icon(status)
        button_text = f"{item_name} {status_icon}"
        keyboard.add(InlineKeyboardButton(button_text, callback_data=callback_data))

    keyboard.add(InlineKeyboardButton(BUTTON_BACK, callback_data="back_to_final"))

    bot.edit_message_text(CHOOSE_ITEM_TO_EDIT, 
                          call.message.chat.id, 
                          call.message.message_id, 
                          reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data == "back_to_final")
def back_to_final(call):
    logger.info(f"Returning to final menu for user {call.from_user.id}")
    user_id = call.from_user.id
    
    # Показываем обновленные списки
    show_lists(call.message.chat.id, user_id)
    
    # Отправляем сообщение с финальным меню и клавиатурой
    bot.send_message(call.message.chat.id, WHAT_NEXT_MESSAGE, reply_markup=get_final_keyboard())
    
    # Удаляем предыдущее сообщение с кнопками редактирования
    bot.delete_message(call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == "restart_packing")
def restart_packing(call):
    logger.info(f"User {call.from_user.id} requested to restart packing")
    user_id = call.from_user.id
    reset_progress(user_id)
    bot.delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, RESTART_PACKING_MESSAGE, reply_markup=get_pack_keyboard())
    ask_object(call.message.chat.id, user_id)

@bot.callback_query_handler(func=lambda call: call.data == "show_full_list")
def show_full_list_after_packing(call):
    logger.info(f"User {call.from_user.id} requested full list after packing")
    items = read_items()
    object_list = "\n".join([f"- {item}" for item in items])
    bot.send_message(call.message.chat.id, SHOW_FULL_LIST_PROMPT.format(object_list))
    bot.edit_message_text(WHAT_NEXT_MESSAGE, 
                          call.message.chat.id, 
                          call.message.message_id, 
                          reply_markup=get_final_keyboard())

@bot.message_handler(func=lambda message: True)
def echo_all(message):
    logger.debug(f"Received message: '{message.text}' from user {message.from_user.id}")
    bot.reply_to(message, UNKNOWN_COMMAND)

def set_commands():
    bot.set_my_commands([
        BotCommand(COMMAND_START, COMMAND_START_DESCRIPTION),
        BotCommand(COMMAND_RESET, COMMAND_RESET_DESCRIPTION)
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
