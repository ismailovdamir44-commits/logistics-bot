import os
import asyncio

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)


# ============================================================
# НАСТРОЙКИ
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("Не найден BOT_TOKEN")


# ============================================================
# КАНАЛЫ ГОРОДОВ
#
# ВАЖНО:
# Здесь указывается КАНАЛ ГОРОДА ОТПРАВЛЕНИЯ.
#
# Например:
# Ташкент -> Самарканд = канал Ташкента
# Ташкент -> Бухара    = канал Ташкента
#
# ЗАМЕНИ @username на свои реальные каналы.
# ============================================================

CITY_CHANNELS = {
    "Ташкент": "@tashkent_lg",
    "Самарканд": "@samarkand_lg",
    "Бухара": "@bukhara_lg",
    "Андижан": "@andijon_lg",
    "Фергана": "@fergana_lg",
    "Наманган": "@namangan_lg",
    "Кашкадарья": "@qashqadaryo_lg",
    "Сурхандарья": "@surkhandarya_lg",
    "Хорезм": "@khorezm_lg",
    "Навои": "@navoi_lg",
    "Джизак": "@jizzakh_lg",
    "Сырдарья": "@syrdarya_lg",
    "Каракалпакстан": "@karakalpakstan_lg",
}


# ============================================================
# ГОРОДА
# ============================================================

CITIES = list(CITY_CHANNELS.keys())


# ============================================================
# ЗАПУСК БОТА
# ============================================================

bot = Bot(token=BOT_TOKEN)

dp = Dispatcher(storage=MemoryStorage())


# ============================================================
# СОСТОЯНИЯ ЗАЯВКИ
# ============================================================

class OrderForm(StatesGroup):
    from_city = State()
    to_city = State()
    cargo = State()
    weight = State()
    phone = State()


# ============================================================
# ВРЕМЕННОЕ ХРАНИЛИЩЕ ЗАЯВОК
#
# Для первого варианта данные хранятся в памяти.
# Позже можно подключить SQLite/PostgreSQL.
# ============================================================

orders = {}

order_counter = 0


# ============================================================
# КЛАВИАТУРА ГОРОДОВ
# ============================================================

def cities_keyboard(prefix="from"):
    buttons = []

    row = []

    for city in CITIES:
        row.append(
            InlineKeyboardButton(
                text=city,
                callback_data=f"{prefix}:{city}"
            )
        )

        if len(row) == 2:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ============================================================
# СТАРТ
# ============================================================

@dp.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):

    await state.clear()

    await state.set_state(OrderForm.from_city)

    await message.answer(
        "🚚 <b>Logistics Bot</b>\n\n"
        "Я помогу найти доставщика для вашего груза.\n\n"
        "📍 Выберите город отправления:",
        parse_mode="HTML",
        reply_markup=cities_keyboard("from")
    )


# ============================================================
# ВЫБОР ГОРОДА ОТПРАВЛЕНИЯ
# ============================================================

@dp.callback_query(
    OrderForm.from_city,
    F.data.startswith("from:")
)
async def from_city_handler(
    callback: CallbackQuery,
    state: FSMContext
):

    city = callback.data.replace("from:", "", 1)

    if city not in CITY_CHANNELS:
        await callback.answer(
            "❌ Такой город не настроен.",
            show_alert=True
        )
        return

    await state.update_data(from_city=city)

    await state.set_state(OrderForm.to_city)

    await callback.message.edit_text(
        f"📍 <b>Откуда:</b> {city}\n\n"
        "Теперь выберите город назначения:",
        parse_mode="HTML",
        reply_markup=cities_keyboard("to")
    )

    await callback.answer()


# ============================================================
# ВЫБОР ГОРОДА НАЗНАЧЕНИЯ
# ============================================================

@dp.callback_query(
    OrderForm.to_city,
    F.data.startswith("to:")
)
async def to_city_handler(
    callback: CallbackQuery,
    state: FSMContext
):

    city = callback.data.replace("to:", "", 1)

    await state.update_data(to_city=city)

    await state.set_state(OrderForm.cargo)

    await callback.message.edit_text(
        f"📍 <b>Куда:</b> {city}\n\n"
        "📦 Напишите, что нужно доставить.\n\n"
        "Например: документы, коробка, одежда.",
        parse_mode="HTML"
    )

    await callback.answer()


# ============================================================
# ОПИСАНИЕ ГРУЗА
# ============================================================

@dp.message(OrderForm.cargo)
async def cargo_handler(
    message: Message,
    state: FSMContext
):

    cargo = message.text.strip()

    if not cargo:
        await message.answer(
            "❌ Напишите описание груза."
        )
        return

    await state.update_data(cargo=cargo)

    await state.set_state(OrderForm.weight)

    await message.answer(
        "⚖️ Укажите вес груза в килограммах.\n\n"
        "Например: 5"
    )


# ============================================================
# ВЕС
# ============================================================

@dp.message(OrderForm.weight)
async def weight_handler(
    message: Message,
    state: FSMContext
):

    weight = message.text.strip()

    if not weight:
        await message.answer(
            "❌ Укажите вес груза."
        )
        return

    await state.update_data(weight=weight)

    await state.set_state(OrderForm.phone)

    await message.answer(
        "📞 Отправьте номер телефона для связи с вами."
    )


# ============================================================
# ТЕЛЕФОН И СОЗДАНИЕ ЗАЯВКИ
# ============================================================

@dp.message(OrderForm.phone)
async def phone_handler(
    message: Message,
    state: FSMContext
):

    phone = message.text.strip()

    if not phone:
        await message.answer(
            "❌ Укажите номер телефона."
        )
        return

    await state.update_data(phone=phone)

    data = await state.get_data()

    from_city = data["from_city"]
    to_city = data["to_city"]
    cargo = data["cargo"]
    weight = data["weight"]
    phone = data["phone"]

    # --------------------------------------------------------
    # ГЛАВНОЕ:
    #
    # Канал определяется ТОЛЬКО по from_city.
    #
    # Если:
    # from_city = "Ташкент"
    #
    # то:
    # channel = CITY_CHANNELS["Ташкент"]
    #
    # Город назначения НЕ используется для выбора канала.
    # --------------------------------------------------------

    channel = CITY_CHANNELS.get(from_city)

    if not channel:
        await message.answer(
            "❌ Для этого города пока не настроен канал."
        )

        await state.clear()
        return

    global order_counter

    order_counter += 1

    order_id = order_counter

    # Сохраняем заявку
    orders[order_id] = {
        "client_id": message.from_user.id,
        "client_name": message.from_user.full_name,
        "client_username": message.from_user.username,
        "from_city": from_city,
        "to_city": to_city,
        "cargo": cargo,
        "weight": weight,
        "phone": phone,
        "status": "searching",
        "driver_id": None,
    }

    # Кнопка для доставщика
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚚 ВЗЯТЬ ЗАЯВКУ",
                    callback_data=f"take:{order_id}"
                )
            ]
        ]
    )

    # --------------------------------------------------------
    # ЗАЯВКА ОТПРАВЛЯЕТСЯ ИМЕННО В КАНАЛ ГОРОДА ОТПРАВЛЕНИЯ
    # --------------------------------------------------------

    order_text = (
        "🚚 <b>НОВАЯ ЗАЯВКА</b>\n\n"
        f"🆔 Заявка №{order_id}\n\n"
        f"📍 <b>Откуда:</b> {from_city}\n"
        f"📍 <b>Куда:</b> {to_city}\n"
        f"📦 <b>Груз:</b> {cargo}\n"
        f"⚖️ <b>Вес:</b> {weight} кг\n\n"
        "🚚 Ищем доставщика...\n\n"
        "👇 Если вы готовы выполнить доставку, "
        "нажмите кнопку:"
    )

    try:

        sent_message = await bot.send_message(
            chat_id=channel,
            text=order_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )

        # Сохраняем сообщение канала
        orders[order_id]["channel_message_id"] = sent_message.message_id
        orders[order_id]["channel"] = channel

        await message.answer(
            "✅ <b>Заявка создана!</b>\n\n"
            f"🆔 Номер заявки: {order_id}\n"
            f"📍 {from_city} → {to_city}\n"
            f"📦 {cargo}\n"
            f"⚖️ {weight} кг\n\n"
            "🔎 Ищем доставщика.\n"
            "Как только доставщик возьмёт заявку, "
            "я сообщу вам.",
            parse_mode="HTML"
        )

    except Exception as error:

        print("Ошибка отправки заявки:", error)

        # Если сообщение не отправилось,
        # удаляем заявку из памяти
        orders.pop(order_id, None)

        await message.answer(
            "❌ Не удалось отправить заявку.\n\n"
            "Проверьте, что бот добавлен в канал "
            "и имеет права администратора."
        )

    await state.clear()


# ============================================================
# ДОСТАВЩИК БЕРЁТ ЗАЯВКУ
# ============================================================

@dp.callback_query(
    F.data.startswith("take:")
)
async def take_order_handler(
    callback: CallbackQuery
):

    try:
        order_id = int(
            callback.data.replace("take:", "", 1)
        )
    except ValueError:

        await callback.answer(
            "❌ Ошибка заявки.",
            show_alert=True
        )

        return

    # Проверяем существование заявки
    order = orders.get(order_id)

    if not order:

        await callback.answer(
            "❌ Заявка уже недоступна.",
            show_alert=True
        )

        return

    # --------------------------------------------------------
    # ПРОВЕРЯЕМ, НЕ ВЗЯЛ ЛИ ЕЁ УЖЕ ДРУГОЙ ДОСТАВЩИК
    # --------------------------------------------------------

    if order["status"] != "searching":

        await callback.answer(
            "❌ Эту заявку уже взял другой доставщик.",
            show_alert=True
        )

        return

    driver = callback.from_user

    driver_id = driver.id
    driver_name = driver.full_name
    driver_username = driver.username

    # --------------------------------------------------------
    # ЗАКРЕПЛЯЕМ ЗАЯВКУ
    # --------------------------------------------------------

    order["status"] = "taken"
    order["driver_id"] = driver_id
    order["driver_name"] = driver_name
    order["driver_username"] = driver_username

    # --------------------------------------------------------
    # УБИРАЕМ КНОПКУ ИЗ КАНАЛА
    # --------------------------------------------------------

    try:

        await callback.message.edit_reply_markup(
            reply_markup=None
        )

    except Exception as error:

        print(
            "Не удалось убрать кнопку:",
            error
        )

    # --------------------------------------------------------
    # СООБЩЕНИЕ ДОСТАВЩИКУ
    # --------------------------------------------------------

    await callback.answer(
        "✅ Вы взяли заявку!",
        show_alert=True
    )

    await callback.message.answer(
        f"🚚 <b>Заявка №{order_id} закреплена за вами.</b>\n\n"
        f"📍 {order['from_city']} → {order['to_city']}\n"
        f"📦 Груз: {order['cargo']}\n"
        f"⚖️ Вес: {order['weight']} кг\n\n"
        f"📞 Телефон клиента: {order['phone']}",
        parse_mode="HTML"
    )

    # --------------------------------------------------------
    # СООБЩЕНИЕ КЛИЕНТУ
    # --------------------------------------------------------

    client_id = order["client_id"]

    driver_contact = (
        f"@{driver_username}"
        if driver_username
        else "username не указан"
    )

    try:

        await bot.send_message(
            chat_id=client_id,
            text=(
                f"🎉 <b>Доставщик найден!</b>\n\n"
                f"🆔 Заявка №{order_id}\n"
                f"📍 {order['from_city']} → "
                f"{order['to_city']}\n\n"
                f"🚚 <b>Доставщик:</b> {driver_name}\n"
                f"📱 <b>Telegram:</b> {driver_contact}\n"
                f"📞 <b>Телефон:</b> {order['phone']}\n\n"
                "Свяжитесь с доставщиком для "
                "уточнения деталей доставки."
            ),
            parse_mode="HTML"
        )

    except Exception as error:

        print(
            "Не удалось отправить сообщение клиенту:",
            error
        )


# ============================================================
# ОБРАБОТКА НЕИЗВЕСТНЫХ СООБЩЕНИЙ
# ============================================================

@dp.message()
async def unknown_message(message: Message):

    await message.answer(
        "Чтобы создать заявку, нажмите /start"
    )


# ============================================================
# ЗАПУСК
# ============================================================

async def main():

    print("===================================")
    print("🚚 LOGISTICS BOT ЗАПУЩЕН")
    print("===================================")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
