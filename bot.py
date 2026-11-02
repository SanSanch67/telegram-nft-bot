import asyncio
import logging
import re
import sys
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, F, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

# ТОКЕН ТВОЕГО БОТА (получи у @BotFather)
TOKEN = "9090731044:AAHilgjhbUgnyUs1m-knRZY6-1W5nMLbd_Q"

# Инициализируем бота и диспетчер
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())


# Состояния для создания оффера через FSM
class OfferStates(StatesGroup):
  waiting_for_user = State()
  waiting_for_nft_link = State()
  waiting_for_stars = State()


# 1. Команда /start
@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
  await message.answer("привет")


# 2. Команда /ofer — запуск создания оффера
@dp.message(Command("ofer"))
async def command_ofer_handler(message: Message, state: FSMContext) -> None:
  await state.set_state(OfferStates.waiting_for_user)
  await message.answer(
      "Отправь юзернейм пользователя или ссылку на его профиль (например,"
      " `t.me/ONwvw` или `@username`):"
  )


# Шаг 1: Получаем юзернейм/профиль
@dp.message(OfferStates.waiting_for_user)
async def process_user(message: Message, state: FSMContext) -> None:
  await state.update_data(user_profile=message.text.strip())
  await state.set_state(OfferStates.waiting_for_nft_link)
  await message.answer("Отправь ссылку на подарок (например,"
                       " `http://t.me/nft/ChillFlame-207363`):")


# Шаг 2: Получаем ссылку на NFT-подарок
@dp.message(OfferStates.waiting_for_nft_link)
async def process_nft_link(message: Message, state: FSMContext) -> None:
  link = message.text.strip()
  # Проверяем ссылку на соответствие нужному формату (название-цифры)
  match = re.search(r"/nft/([a-zA-Z0-9_]+)-(\d+)", link)
  if not match:
    await message.answer(
        "❌ Неверный формат ссылки. Ссылка должна содержать `/nft/Название-Номер`,"
        " например `http://t.me/nft/ChillFlame-207363`. Попробуй еще раз:"
    )
    return

  await state.update_data(nft_link=link)
  await state.set_state(OfferStates.waiting_for_stars)
  await message.answer("Укажи цену за подарок в звездах (только число, например:"
                       " `150`):")


# Шаг 3: Получаем цену и генерируем финальное сообщение с оффером
@dp.message(OfferStates.waiting_for_stars)
async def process_stars(message: Message, state: FSMContext) -> None:
  stars = message.text.strip()
  if not stars.isdigit():
    await message.answer("❌ Цена должна состоять только из цифр. Введи число:")
    return

  data = await state.get_data()
  user_profile = data["user_profile"]
  nft_link = data["nft_link"]
  await state.clear()

  # Парсим название и ID для подарка
  match = re.search(r"/nft/([a-zA-Z0-9_]+)-(\d+)", nft_link)
  nft_name = match.group(1)
  nft_id = match.group(2)

  # Форматируем ссылку на профиль (если юзер ввел без t.me/, подставляем)
  clean_profile = user_profile.replace("@", "")
  if "t.me/" not in clean_profile:
    profile_url = f"t.me/{clean_profile}"
  else:
    profile_url = clean_profile

  # Текст подарка со скрытой ссылкой: название + #ид
  gift_display = f'<a href="{nft_link}">{nft_name}#{nft_id}</a>'
  user_link_html = f'<a href="https://{profile_url}">Зверев</a>'

  # Таймер (6 часов от текущего момента)
  end_time = datetime.now() + timedelta(hours=6)
  time_str = end_time.strftime("%H:%M")

  # Формируем текст оффера
  text = (
      f"{user_link_html} предлагает Вам {stars} stars за коллекционный предмет"
      f" {gift_display}\n\n⏱ Действует до {time_str}"
  )

  # Кнопки для первого этапа (Принять / Отказаться)
  keyboard = InlineKeyboardMarkup(
      inline_keyboard=[
          [
              InlineKeyboardButton(
                  text="🟢 Принять", callback_data=f"accept_{stars}_{nft_name}_{nft_id}_{nft_link}"
              ),
              InlineKeyboardButton(text="🔴 Отказаться", callback_data="decline"),
          ]
      ]
  )

  # Отправляем сообщение в этот же чат (картинка подтянется из превью ссылки автоматически, если включен сайт)
  # Чтобы превью работало корректно, ссылка на nft должна идти в тексте.
  await message.answer(text, reply_markup=keyboard, disable_web_page_preview=False)


# Обработка нажатия кнопки «Отказаться»
@dp.callback_query(F.data == "decline")
async def callback_decline(callback: CallbackQuery) -> None:
  try:
    await callback.message.delete()
  except Exception:
    await callback.answer("Сообщение уже удалено", show_alert=True)


# Обработка нажатия кнопки «Принять»
@dp.callback_query(F.data.startswith("accept_"))
async def callback_accept(callback: CallbackQuery) -> None:
  parts = callback.data.split("_")
  stars = parts[1]
  nft_name = parts[2]
  nft_id = parts[3]
  nft_link = parts[4]

  gift_display = f'<a href="{nft_link}">{nft_name}#{nft_id}</a>'
  user_link_html = '<a href="https://t.me/ONwvw">Зверев</a>'

  # Новый текст после принятия
  new_text = (
      f"Подарок: {gift_display} успешно продан!\n\n"
      f"• передайте подарок {user_link_html} для зачисления {stars} stars"
  )

  # Новые кнопки (друг под другом)
  new_keyboard = InlineKeyboardMarkup(
      inline_keyboard=[
          [
              InlineKeyboardButton(
                  text="1. Передать подарок", url="https://t.me/ONwvw"
              )
          ],
          [
              InlineKeyboardButton(
                  text="2. Как это сделать", callback_data="how_to_do"
              )
          ],
      ]
  )

  # Обновляем сообщение (текст и кнопки)
  await callback.message.edit_text(
      new_text, reply_markup=new_keyboard, disable_web_page_preview=True
  )
  await callback.answer()


# Всплывающее окно с инструкцией по кнопке «Как это сделать»
@dp.callback_query(F.data == "how_to_do")
async def callback_how_to(callback: CallbackQuery) -> None:
  instruction_text = (
      "Инструкция по передаче подарка:\n\n"
      "1. Зайдите в профиль пользователя.\n"
      "2. Нажмите на иконку подарков / инвентарь.\n"
      "3. Выберите нужный предмет и нажмите кнопку «Передать».\n"
      "4. Подтвердите отправку."
  )
  await callback.answer(instruction_text, show_alert=True)


# Запуск бота
async def main() -> None:
  logging.basicConfig(level=logging.INFO, stream=sys.stdout)
  print("Бот запущен и готов к работе!")
  await dp.start_polling(bot)


if __name__ == "__main__":
  asyncio.run(main())