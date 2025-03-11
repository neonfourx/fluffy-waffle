from telegram.constants import ParseMode
import logging
from datetime import datetime

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    InputFile
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ConversationHandler,
    PicklePersistence
)
#num_tracks=0
# <<< ВАЖНО: УКАЗАТЬ СВОЙ ТОКЕН И ADMIN_CHAT_ID >>>
BOT_TOKEN = "7327729790:AAGpTMokRbruUDvEI3gKsNI9pDAiXk8pCek"  # Замените на свой реальный токен
ADMIN_CHAT_ID = 6234941994          # Замените на ваш реальный chat_id администратора

# Включаем логирование (по желанию, для отладки)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# -----------------------------------------------------------------------------
# Храним (временно, в памяти) список всех заказов по их ID.
# В реальном проекте, лучше использовать БД.
#
# Пример структуры ORDERS_DB[order_id]:
# {
#   "order_id": str,
#   "user_id": int,
#   "username": str,
#   "created_at": datetime,
#   "num_tracks": int,
#   "type_order": "mixing" или "beat",
#   "status": "Ожидает подтверждения" или "Подтверждён",
#   "price_rub": int,
#   "description": str,
#   "materials_file_id": str,  # file_id загруженного архива от пользователя
# }
# -----------------------------------------------------------------------------
ORDERS_DB = {}
ORDER_COUNTER = 1  # Счётчик заказов (просто чтобы генерировать ID)

# -----------------------------------------------------------------------------
# Список состояний для ConversationHandler (логика заказа сведения)
# -----------------------------------------------------------------------------
(
    STATE_CHOOSE_MAIN_MENU,
    STATE_NEW_ORDER_MENU,
    STATE_HELP_MENU,
    STATE_ABOUT_MENU,
    STATE_MY_ORDERS_MENU,

    STATE_MIXING_ASK_TRACKS,
    STATE_MIXING_WAIT_MATERIALS,
    STATE_MIXING_WAIT_DESCRIPTION,
    STATE_MIXING_WAIT_PAYMENT_CONFIRM
) = range(9)

# -----------------------------------------------------------------------------
# Вспомогательные функции для формирования клавиатур
# -----------------------------------------------------------------------------
def main_menu_keyboard():
    """Клавиатура главного меню."""
    buttons = [
        [InlineKeyboardButton("Новый заказ", callback_data="main_new_order")],
        [InlineKeyboardButton("Мои заказы", callback_data="main_my_orders")],
        [InlineKeyboardButton("Помощь", callback_data="main_help")],
        [InlineKeyboardButton("О нас", callback_data="main_about")],
    ]
    return InlineKeyboardMarkup(buttons)

def new_order_menu_keyboard():
    """Подменю - Новый заказ."""
    buttons = [
        [InlineKeyboardButton("Заказать сведение", callback_data="new_order_mixing")],
        [InlineKeyboardButton("Купить бит", callback_data="new_order_beat")],
        [InlineKeyboardButton("Назад", callback_data="back_to_main")],
    ]
    return InlineKeyboardMarkup(buttons)

def help_menu_keyboard():
    """Подменю - Помощь."""
    buttons = [
        [InlineKeyboardButton("Назад", callback_data="back_to_main")],
    ]
    return InlineKeyboardMarkup(buttons)

def about_menu_keyboard():
    """Подменю - О нас."""
    buttons = [
        [InlineKeyboardButton("Назад", callback_data="back_to_main")],
    ]
    return InlineKeyboardMarkup(buttons)

def my_orders_menu_keyboard(user_orders):
    """
    Формируем кнопки со списком заказов текущего пользователя.
    user_orders – это список заказов (словарей) для данного пользователя.
    """
    buttons = []
    for order in user_orders:
        order_id = order["order_id"]
        status = order["status"]
        text_btn = f"Заказ №{order_id} ({status})"
        buttons.append([InlineKeyboardButton(text_btn, callback_data=f"order_details:{order_id}")])

    # Кнопка назад
    buttons.append([InlineKeyboardButton("Назад", callback_data="back_to_main")])
    return InlineKeyboardMarkup(buttons)

def order_details_keyboard(order_id):
    """Клавиатура для меню деталей заказа."""
    buttons = [
        [InlineKeyboardButton("Назад", callback_data="back_to_my_orders")],
    ]
    return InlineKeyboardMarkup(buttons)

def mixing_order_payment_keyboard():
    """Клавиатура, когда бот просит пользователя подтвердить оплату или отменить заказ."""
    buttons = [
        [InlineKeyboardButton("Подтвердить оплату", callback_data="mixing_confirm_payment")],
        [InlineKeyboardButton("Отменить заказ", callback_data="mixing_cancel_order")],
    ]
    return InlineKeyboardMarkup(buttons)

def go_to_main_menu_keyboard():
    """Кнопка выхода в главное меню (используется в тексте ошибки/спора)."""
    buttons = [
        [InlineKeyboardButton("Выйти в главное меню", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(buttons)

def admin_order_keyboard(order_id):
    """
    Клавиатура для администратора: принять заказ или оспорить оплату.
    """
    buttons = [
        [InlineKeyboardButton("Принять заказ", callback_data=f"admin_accept:{order_id}")],
        [InlineKeyboardButton("Оспорить оплату", callback_data=f"admin_dispute:{order_id}")],
    ]
    return InlineKeyboardMarkup(buttons)

# -----------------------------------------------------------------------------
# /start команда – отправляет главное меню
# -----------------------------------------------------------------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """При /start выводим главное меню."""
    await update.message.reply_text(
        text=("<b>Салют бро!</b>🎶\nИщешь чистый и качественный звук - <b>тебе к нам!l</b> Мы занимаемся всем, что нужно для твоего трека: сведение, мастеринг, тюнинг вокала, также биты под любой формат и стиль.\n\n"
        "Наши услуги:\n"
        "🎙️ Сведение — 5000р\n\n"
        "🥁 Биты:\n    • Exclusive права - от 20000р\n    • Premium Trackout (Multitrack) - от 6000р\n    • Premium lease - от 3000р\n\n"
        "Всегда открыты для новых проектов и людей. Пишите в любое время - обсудим ваши идеи и найдём лучший звук для вашего трека.\n\n"
        "Для начала выберите действие:"),
        reply_markup=main_menu_keyboard(),
        parse_mode=ParseMode.HTML
    )
    return STATE_CHOOSE_MAIN_MENU

# -----------------------------------------------------------------------------
# CALLBACK_QUERY – обрабатываем все нажатия на inline-кнопки
# -----------------------------------------------------------------------------
async def callbacks_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Роутер для callback_data."""
    query = update.callback_query
    data = query.data
    await query.answer()  # Закрываем 'часики' на кнопке

    # --- Главное меню ---
    if data == "main_new_order":
        # Переходим в подменю "Новый заказ"
        await query.message.edit_text(
            text="Выберите тип заказа:",
            reply_markup=new_order_menu_keyboard()
        )
        return STATE_NEW_ORDER_MENU

    elif data == "main_my_orders":
        # Переходим в подменю "Мои заказы"
        user_id = query.from_user.id
        user_orders = [o for o in ORDERS_DB.values() if o["user_id"] == user_id]
        if not user_orders:
            await query.message.edit_text(
                text="У вас пока нет заказов.",
                reply_markup=main_menu_keyboard()
            )
            return STATE_CHOOSE_MAIN_MENU
        else:
            await query.message.edit_text(
                text="Ваши заказы:",
                reply_markup=my_orders_menu_keyboard(user_orders)
            )
            return STATE_MY_ORDERS_MENU

    elif data == "main_help":
        # Подменю "Помощь"
        help_text = (
            "Помощь по заказу сведения:\n"
            "1) Подготовьте исходные дороги вокала в формате .wav или .aiff\n"
            "2) Бит тоже в формате .wav\n"
            "3) Если у бита есть трек-аут (дорожки каждого инструмента), также приложите их в формате .wav\n"
            "\n"
            "Помощь по покупке битов (права и лицензии):\n"
            "1) Для неэксклюзивной лицензии покупатель может использовать бит, но авторские права сохраняются за продавцом.\n"
            "2) Для эксклюзивной лицензии покупатель получает полные права, и бит снимается с продажи.\n"
            "\n"
            "Если возникли вопросы, свяжитесь с нами по контактам из раздела 'О нас'."
        )
        await query.message.edit_text(
            text=help_text,
            reply_markup=help_menu_keyboard()
        )
        return STATE_HELP_MENU

    elif data == "main_about":
        # Подменю "О нас"
        about_text = (
            "О нас:\n"
            "- Мы профессионально занимаемся сведением и мастерингом.\n"
            "- Продаём биты разного жанра.\n"
            "- Примеры работ и сотрудничество с известными артистами см. ниже.\n"
            "\n"
            "Контакты для связи:\n"
            "- Telegram: @fourxprod\n"
            "- Примеры работ: (сюда можно добавить ссылки)\n"
            "- Клиенты: (перечислите известных исполнителей, если есть)\n"
        )
        await query.message.edit_text(
            text=about_text,
            reply_markup=about_menu_keyboard()
        )
        return STATE_ABOUT_MENU

    elif data == "back_to_main":
        # Возвращаемся в главное меню
        await query.message.edit_text(
            text="Главное меню:",
            reply_markup=main_menu_keyboard()
        )
        return STATE_CHOOSE_MAIN_MENU

    # --- Подменю "Мои заказы" ---
    elif data.startswith("order_details:"):
        # Показать детали конкретного заказа
        _, order_id_str = data.split(":")
        order_id = order_id_str
        order = ORDERS_DB.get(order_id)
        if not order:
            # Если вдруг такого заказа нет (может быть удалён)
            await query.message.edit_text(
                text="Заказ не найден.",
                reply_markup=my_orders_menu_keyboard([])
            )
            return STATE_MY_ORDERS_MENU

        details_text = (
            f"**Детали заказа №{order_id}**\n"
            f"Дата создания: {order['created_at'].strftime('%d.%m.%Y %H:%M')}\n"
            f"Тип заказа: {'Сведение' if order['type_order'] == 'mixing' else 'Бит'}\n"
            f"Кол-во треков: {order.get('num_tracks', '-')}\n"
            f"Сумма оплаты: {order.get('price_rub', 0)} руб.\n"
            f"Техническое задание: {order.get('description', '-')}\n"
            f"Статус: {order['status']}\n"
        )
        await query.message.edit_text(
            text=details_text,
            parse_mode="Markdown",
            reply_markup=order_details_keyboard(order_id)
        )
        return STATE_MY_ORDERS_MENU

    elif data == "back_to_my_orders":
        # Вернуться к списку заказов
        user_id = query.from_user.id
        user_orders = [o for o in ORDERS_DB.values() if o["user_id"] == user_id]
        await query.message.edit_text(
            text="Ваши заказы:",
            reply_markup=my_orders_menu_keyboard(user_orders)
        )
        return STATE_MY_ORDERS_MENU

    # --- Подменю "Новый заказ" ---
    elif data == "new_order_beat":
        # Пока просто показываем "Скоро" и кнопку "Выйти в главное меню"
        await query.message.edit_text(
            text="Раздел покупки битов: Скоро!\n\nВы можете вернуться в главное меню:",
            reply_markup=go_to_main_menu_keyboard()
        )
        # Не завершаем разговор, остаёмся в состоянии главного меню после выхода
        return STATE_CHOOSE_MAIN_MENU

    elif data == "new_order_mixing":
        # Переходим к сценарию "Заказать сведение": спросить кол-во треков
        await query.message.edit_text(
            text="Сколько треков хотите заказать для сведения? (Напишите число)",
        )
        return STATE_MIXING_ASK_TRACKS

    # --- Оформление "Заказать сведение": финальные шаги ---
    elif data == "mixing_confirm_payment":
        # Пользователь нажал «Подтвердить оплату»
        # Посылаем уведомление администратору
        user_data = context.user_data
        current_order = user_data.get("current_order", {})
        if not current_order:
            # Заказ не найден, возможно уже удалён
            await query.message.edit_text(
                text="Кажется, заказ уже неактивен. Начните заново.",
                reply_markup=main_menu_keyboard()
            )
            return STATE_CHOOSE_MAIN_MENU

        order_id = current_order["order_id"]
        # Обновляем общий DB
        ORDERS_DB[order_id] = current_order

        # Формируем сообщение администратору
        text_for_admin = (
            "Ебать тебе дропнули деньги!\n\n"
            f"Ник клиента: {current_order['name']}\n"
            f"Тг-айди клиента: @{current_order['username']}\n"
            f"Дата создания заказа: {current_order['created_at'].strftime('%d.%m.%Y %H:%M')}\n"
            f"Кол-во треков: {current_order['num_tracks']}\n"
            f"Сумма оплаты: {current_order['price_rub']} руб.\n"
            f"Техническое задание: {current_order['description']}\n"
            "Материалы: (см. вложения выше)\n\n"
            "Ожидает блядского подтверждения сука!"
        )

        # Отправляем сообщение админу
        try:
            # Если есть файл (zip) – пересылаем
            materials_file_id = current_order.get("materials_file_id")
            if materials_file_id:
                await context.bot.send_document(
                    chat_id=ADMIN_CHAT_ID,
                    document=materials_file_id,
                    caption=text_for_admin,
                    reply_markup=admin_order_keyboard(order_id)
                )
            else:
                # Если почему-то нет файла
                await context.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=text_for_admin,
                    reply_markup=admin_order_keyboard(order_id)
                )
        except Exception as e:
            logging.error(f"Ошибка при отправке админу: {e}")

        # Сообщение пользователю
        await query.message.edit_text(
            text="Спасибо! Мы получили ваше подтверждение оплаты.\n"
                 "Ожидайте подтверждения от администратора.",
            reply_markup=main_menu_keyboard()
        )

        # Очищаем current_order
        user_data["current_order"] = {}
        return STATE_CHOOSE_MAIN_MENU

    elif data == "mixing_cancel_order":
        # Пользователь нажал «Отменить заказ», удаляем данные из памяти
        user_data = context.user_data
        #user_data["current_order"]["order_id"] = None
        del ORDERS_DB[user_data["current_order"]["order_id"]]

        #del  user_data["current_order"]
        await query.message.edit_text(
            text="Заказ был отменён. Возвращаю вас в главное меню.",
            reply_markup=main_menu_keyboard()
        )
        return STATE_CHOOSE_MAIN_MENU

    # --- Администраторские кнопки ---
    elif data.startswith("admin_accept:"):
        _, order_id_str = data.split(":")
        order_id = order_id_str
        order = ORDERS_DB.get(order_id)
        if order:
            # Обновляем статус
            order["status"] = "Подтверждён"
            ORDERS_DB[order_id] = order

            # Отправляем клиенту сообщение о подтверждении
            user_id = order["user_id"]
            text_for_user = (
                "Ваш заказ был подтверждён!\n"
                f"Связаться с администратором можно здесь: @fourxprod\n"
                "Спасибо за заказ."
            )
            try:
                await context.bot.send_message(chat_id=user_id, text=text_for_user)
            except Exception as e:
                logging.error(f"Ошибка при уведомлении клиента: {e}")

            # Редактируем сообщение админу (чтобы убрать кнопки)
            await query.message.edit_text(
                text="Заказ подтверждён, клиенту отправлено уведомление.",
            )
        else:
            await query.message.edit_text("Заказ не найден в БД.")
        return ConversationHandler.END

    elif data.startswith("admin_dispute:"):
        _, order_id_str = data.split(":")
        order_id = order_id_str
        order = ORDERS_DB.get(order_id)
        if order:
            # Удаляем заказ или ставим статус "отменён" – решайте, как удобнее.
            # В тексте задачи сказано "оплата не была получена, заказ расформирован."
            # Для наглядности – просто удалим из ORDERS_DB.
            del ORDERS_DB[order_id]

            # Уведомляем клиента
            user_id = order["user_id"]
            text_for_user = (
                "Оплата не была получена, заказ расформирован.\n"
                "В случае если вы произвели оплату, но она не была получена,\n"
                "то свяжитесь по контактам: @fourxprod"
            )
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=text_for_user,
                    reply_markup=go_to_main_menu_keyboard()
                )
            except Exception as e:
                logging.error(f"Ошибка при уведомлении клиента: {e}")

            await query.message.edit_text("Заказ оспорен: клиенту отправлено уведомление.")
        else:
            await query.message.edit_text("Заказ не найден в БД.")
        return ConversationHandler.END

    # Если ничего не подошло:
    await query.message.reply_text("Неизвестная команда. Возврат в главное меню.")
    return STATE_CHOOSE_MAIN_MENU

# -----------------------------------------------------------------------------
# Логика ConversationHandler для шага: попросить у пользователя кол-во треков
# -----------------------------------------------------------------------------
async def mixing_ask_tracks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пользователь вводит (в сообщении) кол-во треков."""
    message = update.message
    text = message.text
    user_data = context.user_data

    # Проверяем, что это число
    if not text.isdigit():
        await message.reply_text("Пожалуйста, введите число (кол-во треков).")
        return STATE_MIXING_ASK_TRACKS

    num_tracks = int(text)
    user_data["current_order"] = {
        "order_id": None,
        "user_id": message.from_user.id,
        "username": message.from_user.username or "N/A",  # Оставляем для Telegram-username
        "name": message.from_user.first_name + (" " + message.from_user.last_name if message.from_user.last_name else ""),  # Добавляем имя
        "created_at": datetime.now(),
        "num_tracks": num_tracks,
        "type_order": "mixing",
        "status": "Ожидает подтверждения",
        "price_rub": 5000 * num_tracks,
        "description": "",
        "materials_file_id": None,
    }

    await message.reply_text(
        "Отправьте, пожалуйста, ZIP-архив с материалами (дороги вокала и бит)."
    )
    return STATE_MIXING_WAIT_MATERIALS

# -----------------------------------------------------------------------------
# Принимаем ZIP (или любой файл) с материалами
# -----------------------------------------------------------------------------
async def mixing_receive_materials(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ждём от пользователя архив с материалами."""
    message = update.message
    user_data = context.user_data
    current_order = user_data.get("current_order", {})

    if not message.document:
        # Если пользователь прислал не документ
        await message.reply_text("Пожалуйста, пришлите архив (файл) с материалами.")
        return STATE_MIXING_WAIT_MATERIALS

    # Сохраняем file_id
    file_id = message.document.file_id
    current_order["materials_file_id"] = file_id
    user_data["current_order"] = current_order

    # Переходим к запросу тех. задания
    await message.reply_text("Опишите ваши пожелания, предпочтения, референсы и т.д.")
    return STATE_MIXING_WAIT_DESCRIPTION

# -----------------------------------------------------------------------------
# Принимаем описание (тех. задание)
# -----------------------------------------------------------------------------
async def mixing_receive_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получаем тех. задание от пользователя."""
    message = update.message
    user_data = context.user_data
    current_order = user_data.get("current_order", {})

    description = message.text
    current_order["description"] = description

    # Генерируем order_id, сохраняем заказ в БД (пока статус "Ожидает подтверждения")
    global ORDER_COUNTER
    order_id = str(ORDER_COUNTER)
    ORDER_COUNTER += 1
    current_order["order_id"] = order_id
    ORDERS_DB[order_id] = current_order

    # Переходим к шагу оплаты
    await message.reply_text(
        text=(
            
            "Реквизиты для оплаты по СБП:\n"
            "Номер телефона: +7 923 635 69 84\n"
            "Банк: Т-Банк / Сбербанк\n"
            "Имя получателя: Степан Б. П.\n"
            "Сумма оплаты: "+str(current_order['price_rub'])+"\n\n"
            "После оплаты нажмите «Подтвердить оплату», "
            "или «Отменить заказ» чтобы прервать оформление."
        ),
        reply_markup=mixing_order_payment_keyboard()
    )
    return STATE_MIXING_WAIT_PAYMENT_CONFIRM

# -----------------------------------------------------------------------------
# Создаём ConversationHandler
# -----------------------------------------------------------------------------
def main():
    application = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start_command)],
        states={
            STATE_CHOOSE_MAIN_MENU: [
                CallbackQueryHandler(callbacks_router),
            ],
            STATE_NEW_ORDER_MENU: [
                CallbackQueryHandler(callbacks_router),
            ],
            STATE_HELP_MENU: [
                CallbackQueryHandler(callbacks_router),
            ],
            STATE_ABOUT_MENU: [
                CallbackQueryHandler(callbacks_router),
            ],
            STATE_MY_ORDERS_MENU: [
                CallbackQueryHandler(callbacks_router),
            ],
            STATE_MIXING_ASK_TRACKS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, mixing_ask_tracks)
            ],
            STATE_MIXING_WAIT_MATERIALS: [
                MessageHandler(filters.Document.ALL, mixing_receive_materials),
                MessageHandler(filters.TEXT, mixing_receive_materials),
            ],
            STATE_MIXING_WAIT_DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, mixing_receive_description)
            ],
            STATE_MIXING_WAIT_PAYMENT_CONFIRM: [
                CallbackQueryHandler(callbacks_router),
            ],
        },
        fallbacks=[
            CommandHandler("start", start_command),
        ],
    )

    # Добавляем основной ConversationHandler
    application.add_handler(conv_handler)

    # Обработчик нажатий на кнопки у администратора
    application.add_handler(CallbackQueryHandler(callbacks_router))

    # Запускаем бота (Long Polling)
    application.run_polling()

if __name__ == "__main__":
    main()
