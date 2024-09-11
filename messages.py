# Текстовые сообщения для телеграм-бота

# Общие сообщения
START_MESSAGE = ("Привет! Я бот, который помогает собраться в поход. "
                 "Начнем собираться или вы хотите посмотреть весь список?")
PACK_START_MESSAGE = "Отлично, тогда начнем! Берите все по списку:"
SHOW_FULL_LIST_PROMPT = "Вот полный список вещей для похода:\n\n{}\n\nГотовы собираться?"
PACKING_FINISHED_MESSAGE = "Ура, список закончился!"
WHAT_NEXT_MESSAGE = "Что дальше?"
ITEM_PROMPT = "{}"
NO_SAVED_RESPONSES = "У вас пока нет сохраненных ответов. Начните сбор заново."
CHOOSE_ITEM_TO_EDIT = "Выберите пункт для редактирования:"
CHOOSE_ITEM_STATUS = "Выберите статус '{}':"
STATUS_UPDATED = "Статус обновлен: {}"
RESTART_PACKING_MESSAGE = "Давайте начнем сбор заново. Берите все по списку:"
UNKNOWN_COMMAND = "Извините, я не понимаю эту команду. Пожалуйста, используйте /start или /reset."

# Сообщения об ошибках
FILE_NOT_FOUND_ERROR = "Файл 'hiking_items.txt' не найден"
FILE_READ_ERROR = "Ошибка при чтении файла: {}"
GENERAL_ERROR = "Извините, произошла ошибка при обработке вашего запроса."
EDIT_LIST_ERROR = "Извините, произошла ошибка при отображении списка для редактирования."
EDIT_ITEM_ERROR = "Извините, произошла ошибка при редактировании предмета."
UPDATE_STATUS_ERROR = "Извините, произошла ошибка при обновлении статуса предмета."

# Названия кнопок
BUTTON_PACK = 'Собраться в поход'
BUTTON_SHOW_LIST = 'Посмотреть список'
BUTTON_TAKE = 'Беру'
BUTTON_TAKE_LATER = 'Возьму позже'
BUTTON_SKIP = 'В этот поход не буду брать'
BUTTON_EDIT_LIST = "Редактировать список"
BUTTON_SHOW_FULL_LIST = "Посмотреть весь список"
BUTTON_RESTART_PACKING = "Собраться заново"
BUTTON_BACK = "Назад"

# Названия команд
COMMAND_START = "start"
COMMAND_RESET = "reset"
COMMAND_START_DESCRIPTION = "Начать работу с ботом"
COMMAND_RESET_DESCRIPTION = "Сбросить прогресс и начать заново"

# Форматирование списков
PACKING_RESULT = """Вот, что получилось:

Уже в рюкзаке:
{}

То, что возьмете позже:
{}

В этом походе не пригодится:
{}"""

ITEM_STATUS_FORMAT = "{} - {}"
