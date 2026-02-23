from aiogram import Router
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command
from app.repo import list_services, average_rating_for_service, list_bookings, get_or_create_user, get_service, get_master
from app.utils import format_rating
from aiogram.types import CallbackQuery
from app.keyboards import main_menu_kb
from app.handlers.admin import is_admin

router = Router()

@router.message(Command('start'))
async def cmd_start(message: Message):
    owner = is_admin(message.from_user.id)
    kb = main_menu_kb(is_owner=owner)
    await message.answer('👋 Привет! Я ваш помощник по записи и вопросам. Выберите действие:', reply_markup=kb)

@router.message(lambda message: message.text and '💇' in message.text)
async def show_services(message: Message):
    from app.repo import average_rating_for_service
    services = await list_services()
    if not services:
        await message.answer('😔 Пока нет доступных услуг. Администратор скоро добавит. Попробуйте позже!')
        return
    
    # Pagination: show first 5 services
    PAGE_SIZE = 5
    page_items = services[:PAGE_SIZE]
    
    rows = []
    for s in page_items:
        avg, cnt = await average_rating_for_service(s['id'])
        rating_str = format_rating(avg, cnt)
        btn_text = f"{s['name']} — {s['price']}€"
        if rating_str:
            btn_text += f" {rating_str}"
        rows.append([InlineKeyboardButton(text=btn_text, callback_data=f"book:service:{s['id']}")])
    
    # Add pagination buttons if needed
    if len(services) > PAGE_SIZE:
        rows.append([InlineKeyboardButton(text='➡️ Далее', callback_data='services:page:1')])
    
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    await message.answer('💇 Выберите услугу для записи:', reply_markup=kb)


# Support quick-reply keyboard buttons (ReplyKeyboardMarkup) used in /start
@router.message(lambda message: message.text and message.text.strip() in ['💇 Услуги'])
async def cmd_services_button(message: Message):
    # reuse existing show_services flow
    await show_services(message)

@router.message(lambda message: message.text and message.text.strip() == '📅 Мои записи')
async def cmd_my_booking(message: Message):
    await message.answer('Функция "Мои записи" пока не реализована. Скоро будет доступна в удобном интерфейсе.')


@router.message(lambda message: message.text and message.text.strip() == '🏢 О нас')
async def cmd_about(message: Message):
    await message.answer('Мы — уютный салон с профессиональными мастерами. Для записи используйте кнопку "💇 Услуги" в главном меню.')


@router.message(lambda message: message.text and message.text.strip() == '💬 Контакты')
async def cmd_contacts(message: Message):
    await message.answer('Контакты: +1 234 567 890\nАдрес: ул. Примерная, 1\nРаботаем: 09:00–18:00')


@router.message(lambda message: message.text and message.text.strip() == '⭐ Отзывы')
async def cmd_reviews_button(message: Message):
    # Show latest reviews (read-only) and, if user has completed bookings, offer a button to leave a review
    rows = await list_services()  # reuse services call to ensure DB is accessible
    from app.repo import list_reviews
    recent = await list_reviews(limit=5)
    if recent:
        text = 'Последние отзывы:\n'
        for r in recent:
            rating = '⭐' * int(r['rating'] or 0)
            txt = (r['text'] or '').strip()
            text += f"{rating} — {txt}\n"
        await message.answer(text)
    else:
        await message.answer('Пока нет отзывов. Будьте первым!')

    # Check if user has any completed bookings to allow leaving a review
    user = await get_or_create_user(message.from_user.id)
    all_bookings = await list_bookings()
    completed = [b for b in all_bookings if b['user_id'] == user['id'] and b['status'] == 'completed']
    if completed:
        kb_rows = [[InlineKeyboardButton(text='Оставить отзыв', callback_data='start_leave_review')]]
        kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
        await message.answer('Вы можете оставить отзыв по завершённой записи:', reply_markup=kb)
    else:
        await message.answer('У вас пока нет завершённых записей для отзыва.')


@router.callback_query(lambda c: c.data and c.data == 'start_leave_review')
async def cb_start_leave_review(query: CallbackQuery):
    user = await get_or_create_user(query.from_user.id)
    all_bookings = await list_bookings()
    completed = [b for b in all_bookings if b['user_id'] == user['id'] and b['status'] == 'completed']
    if not completed:
        await query.answer('У вас нет завершённых записей для отзыва', show_alert=True)
        return
    # For each completed booking, send a message with rating buttons and option to add text
    for b in completed:
        svc = None
        mstr = None
        try:
            if b['service_id']:
                svc = await get_service(b['service_id'])
            if b['master_id']:
                mstr = await get_master(b['master_id'])
        except Exception:
            pass
        title = f"Запись {b['date']} {b['time']}"
        if svc:
            title += f" — {svc['name']}"
        if mstr:
            title += f" ({mstr['name']})"
        # rating buttons
        row1 = [InlineKeyboardButton(text=str(i), callback_data=f'review:rating:{i}:booking:{b["id"]}') for i in range(1,6)]
        row2 = [InlineKeyboardButton(text='Добавить комментарий', callback_data=f'review:text:booking:{b["id"]}')]
        kb = InlineKeyboardMarkup(inline_keyboard=[row1, row2])
        try:
            await query.message.answer(title, reply_markup=kb)
        except Exception:
            try:
                await query.message.bot.send_message(query.from_user.id, title, reply_markup=kb)
            except Exception:
                pass
    await query.answer()


@router.message(lambda message: message.text and message.text.strip() == '🧠 AI-помощник')
async def cmd_helper(message: Message):
    await message.answer('Напишите /start чтобы вернуться в главное меню или выберите нужную кнопку для действий.')
