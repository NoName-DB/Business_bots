from aiogram import Router
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command
import os
from app.repo import create_master, create_service, list_bookings, set_master_schedule, delete_master, delete_service, update_master, update_service, get_master, get_service, set_booking_status, get_booking, get_user_by_id, list_masters, list_services
from app.utils import get_args_from_message as get_args
from app.scheduler import add_exception, list_exceptions
# cancellation helpers
from app.auto_complete import cancel_auto_complete
from app.reminders import cancel_reminders
from app.keyboards import admin_menu_kb, settings_kb, main_menu_kb

router = Router()
# Read admin IDs from environment using getenv (safer & consistent)
ADMIN_IDS = [int(x) for x in os.getenv('ADMIN_IDS','').split(',') if x]

# Simple in-memory staging for multi-step admin dialogs (per admin user)
STAGED_EDITS = {}
# Format: STAGED_EDITS[user_id] = { 'type': 'master'|'service', 'id': int, 'step': 'name'|'bio'|'contact'|..., 'data': {...} }

# Validation limits
MAX_NAME_LEN = 100
MAX_BIO_LEN = 1000
MAX_CONTACT_LEN = 200
MAX_DESC_LEN = 2000
MIN_PRICE = 0.0
MAX_PRICE = 1_000_000.0
MIN_DURATION = 1
MAX_DURATION = 24 * 60  # minutes


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

@router.message(Command('admin'))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer('Доступ запрещён')
        return
    kb = admin_menu_kb()
    await message.answer('Админ‑панель — выберите действие:', reply_markup=kb)


# Admin keyboard UI wrappers: map reply keyboard buttons to existing handlers or placeholders
@router.message(lambda m: m.from_user and m.from_user.id in ADMIN_IDS and m.text and m.text.strip() == '📅 Просмотр записей')
async def admin_view_bookings_button(message: Message):
    await cmd_list_bookings(message)


@router.message(lambda m: m.from_user and m.from_user.id in ADMIN_IDS and m.text and m.text.strip() == '⚙️ Настройки')
async def admin_show_settings(message: Message):
    kb = settings_kb()
    await message.answer('Настройки — выберите действие:', reply_markup=kb)

# Settings keyboard button handlers
@router.message(lambda m: m.from_user and m.from_user.id in ADMIN_IDS and m.text and m.text.strip() == '🌴 Отправить мастера в отпуск')
async def admin_send_master_on_vacation(message: Message):
    await message.answer('Функция будет доступна позже (заморожено для MVP)')

@router.message(lambda m: m.from_user and m.from_user.id in ADMIN_IDS and m.text and m.text.strip() == '🗓 Настроить дни/часы')
async def admin_set_days_hours(message: Message):
    await message.answer('Функция будет доступна позже (заморожено для MVP)')

@router.message(lambda m: m.from_user and m.from_user.id in ADMIN_IDS and m.text and m.text.strip() == 'Настроить обеденный перерыв')
async def admin_set_lunch_break(message: Message):
    await message.answer('Функция будет доступна позже (заморожено для MVP)')

@router.message(lambda m: m.from_user and m.from_user.id in ADMIN_IDS and m.text and m.text.strip() == '📍 Настроить код страны')
async def admin_set_country_code(message: Message):
    await message.answer('Функция будет доступна позже (заморожено для MVP)')

@router.message(lambda m: m.from_user and m.from_user.id in ADMIN_IDS and m.text and m.text.strip() == '📤 Экспорт в CSV')
async def admin_export_csv(message: Message):
    # Delegate to existing export command
    await cmd_export_bookings(message)

@router.message(lambda m: m.from_user and m.from_user.id in ADMIN_IDS and m.text and m.text.strip() == '⬅️ Назад в меню')
async def admin_settings_back(message: Message):
    kb = admin_menu_kb()
    await message.answer('Возврат в админ‑меню:', reply_markup=kb)


@router.message(lambda m: m.from_user and m.from_user.id in ADMIN_IDS and m.text and m.text.strip() == '➕ Добавить мастера')
async def admin_add_master_button(message: Message):
    # Start interactive add-master flow via button (friendly demo UX)
    user_id = message.from_user.id
    STAGED_EDITS[user_id] = {'type': 'master_add', 'step': 'name', 'data': {}}
    await message.answer('Введите данные мастера. Бот проведёт вас по шагам.')


@router.message(lambda m: m.from_user and m.from_user.id in ADMIN_IDS and m.text and m.text.strip() == '➖ Удалить мастера')
async def admin_delete_master_button(message: Message):
    from app.repo import list_masters
    masters = await list_masters()
    if not masters:
        await message.answer('Нет мастеров для удаления')
        return
    
    kb_rows = []
    for m in masters:
        kb_rows.append([InlineKeyboardButton(text=m['name'], callback_data=f"admin:delete_master:choose:{m['id']}")])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
    await message.answer('Выберите мастера для удаления:', reply_markup=kb)


@router.message(lambda m: m.from_user and m.from_user.id in ADMIN_IDS and m.text and m.text.strip() == '🧾 Просмотр заявок')
async def admin_view_requests_button(message: Message):
    # no specific handler implemented for manual requests in admin UI — placeholder
    await message.answer('Функция будет доступна в следующей версии')


@router.message(lambda m: m.from_user and m.from_user.id in ADMIN_IDS and m.text and m.text.strip() == '⭐ Просмотр отзывов')
async def admin_view_reviews_button(message: Message):
    # delegate to reviews listing handler if available
    try:
        from app.handlers.reviews import cmd_list_reviews
        await cmd_list_reviews(message)
    except Exception:
        await message.answer('Функция будет доступна в следующей версии')


@router.message(lambda m: m.from_user and m.from_user.id in ADMIN_IDS and m.text and m.text.strip() == '🧠 AI-помощник')
async def admin_ai_button(message: Message):
    await message.answer('Функция будет доступна в следующей версии')

@router.message(lambda m: m.from_user and m.from_user.id in ADMIN_IDS and m.text and m.text.strip() == '🛠️ Настроить услуги')
async def admin_manage_services_button(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='➕ Добавить услугу', callback_data='admin:service:add')],
        [InlineKeyboardButton(text='✏️ Изменить услугу', callback_data='admin:service:edit')],
        [InlineKeyboardButton(text='🗑 Удалить услугу', callback_data='admin:service:delete')]
    ])
    await message.answer('Управление услугами — выберите действие:', reply_markup=kb)


@router.message(lambda m: m.from_user and m.from_user.id in ADMIN_IDS and m.text and m.text.strip() == '🏠 Главное меню')
async def admin_back_to_main(message: Message):
    kb = main_menu_kb(is_owner=True)
    await message.answer('Возврат в главное меню:', reply_markup=kb)


# Handle main menu button that opens admin panel (label used in main menu)
@router.message(lambda m: m.from_user and m.from_user.id in ADMIN_IDS and m.text and m.text.strip() == '🏠 Админ-меню')
async def admin_open_menu_from_main(message: Message):
    # delegate to /admin handler which shows the admin keyboard
    await cmd_admin(message)

# TODO: FROZEN — legacy command fallback for admin, not used in demo UI
@router.message(Command('add_master'))
async def cmd_add_master(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer('Доступ запрещён')
        return
    args = get_args(message)
    if not args or '|' not in args:
        await message.answer('Использование: /add_master Имя|bio|контакт')
        return
    name, bio, contact = [x.strip() for x in args.split('|', 2)]
    mid = await create_master(name, bio, contact)
    await message.answer(f'Мастер добавлен с id={mid}')

# TODO: FROZEN — legacy command fallback for admin, not used in demo UI
@router.message(Command('add_service'))
async def cmd_add_service(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer('Доступ запрещён')
        return
    args = get_args(message)
    if not args or '|' not in args:
        await message.answer('Использование: /add_service Название|цена|длительность_мин|описание')
        return
    name, price, duration, description = [x.strip() for x in args.split('|', 3)]
    try:
        price_v = float(price)
        duration_v = int(duration)
    except Exception:
        await message.answer('Неверный формат цены или длительности')
        return
    sid = await create_service(name, description, price_v, duration_v)
    await message.answer(f'Услуга добавлена id={sid}')

# TODO: FROZEN — legacy command fallback for admin, not used in demo UI
@router.message(Command('set_schedule'))
async def cmd_set_schedule(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer('Доступ запрещён')
        return
    args = get_args(message)
    # usage: /set_schedule master_id|weekday(0-6)|09:00|17:00|interval_minutes
    if not args or '|' not in args:
        await message.answer('Использование: /set_schedule master_id|weekday(0-6)|start|end|[interval_minutes]')
        return
    parts = [x.strip() for x in args.split('|')]
    try:
        master_id = int(parts[0])
        weekday = int(parts[1])
        start = parts[2]
        end = parts[3]
        interval = int(parts[4]) if len(parts) > 4 else None
    except Exception:
        await message.answer('Неверный формат аргументов')
        return
    await set_master_schedule(master_id, weekday, start, end, interval)
    await message.answer('Расписание сохранено')

@router.message(Command('add_exception'))
async def cmd_add_exception(message: Message):
    # TODO: FROZEN for MVP demo — advanced master exception management not part of MVP
    if not is_admin(message.from_user.id):
        await message.answer('Доступ запрещён')
        return
    args = get_args(message)
    # usage: /add_exception master_id|YYYY-MM-DD|available(0|1)|[start]|[end]|[note]
    if not args or '|' not in args:
        await message.answer('Использование: /add_exception master_id|YYYY-MM-DD|available(0|1)|[start]|[end]|[note]')
        return
    parts = [x.strip() for x in args.split('|')]
    try:
        master_id = int(parts[0])
        date_s = parts[1]
        available = int(parts[2])
        start = parts[3] if len(parts) > 3 and parts[3] else None
        end = parts[4] if len(parts) > 4 and parts[4] else None
        note = parts[5] if len(parts) > 5 else None
    except Exception:
        await message.answer('Неверный формат аргументов')
        return
    await add_exception(master_id, date_s, available, start, end, note)
    await message.answer('Исключение добавлено/обновлено')

@router.message(Command('list_exceptions'))
async def cmd_list_exceptions(message: Message):
    # TODO: FROZEN for MVP demo — advanced master exception management not part of MVP
    if not is_admin(message.from_user.id):
        await message.answer('Доступ запрещён')
        return
    args = get_args(message)
    if not args:
        await message.answer('Использование: /list_exceptions master_id')
        return
    try:
        master_id = int(args.strip())
    except Exception:
        await message.answer('Неверный master_id')
        return
    rows = await list_exceptions(master_id)
    if not rows:
        await message.answer('Исключений нет')
        return
    text = ''
    for r in rows:
        text += f"{r['date']} available={r['available']} {r['start_time'] or ''}-{r['end_time'] or ''} {r['note'] or ''}\n"
    await message.answer(text)

@router.message(Command('list_bookings'))
async def cmd_list_bookings(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer('Доступ запрещён')
        return
    args = get_args(message)
    # optional args: start|end (YYYY-MM-DD)
    if args and '|' in args:
        start, end = [x.strip() for x in args.split('|',1)]
        rows = await list_bookings()
        rows = [r for r in rows if (r['date'] >= start and r['date'] <= end)]
    else:
        rows = await list_bookings()
    if not rows:
        await message.answer('Записей нет')
        return
    from app.repo import get_user_by_id, get_service, get_master
    text = ''
    for r in rows[:200]:
        user = await get_user_by_id(r['user_id']) if r['user_id'] else None
        service = await get_service(r['service_id']) if r['service_id'] else None
        master = await get_master(r['master_id']) if r['master_id'] else None
        
        user_name = user['name'] if user else "неизвестный"
        user_phone = user['phone'] if user else ""
        service_name = service['name'] if service else "неизвестная"
        master_name = master['name'] if master else "без выбора"
        
        text += f"ID: {r['id']}\n"
        text += f"Клиент: {user_name}\n"
        if user_phone:
            text += f"Телефон: {user_phone}\n"
        text += f"Услуга: {service_name}\n"
        text += f"Мастер: {master_name}\n"
        text += f"Дата: {r['date']}\n"
        text += f"Время: {r['time']}\n"
        text += f"Статус: {r['status']}\n\n"
    await message.answer(text)


@router.message(Command('complete_booking'))
async def cmd_complete_booking(message: Message):
    """Mark a booking as completed and send a review request to the client."""
    if not is_admin(message.from_user.id):
        await message.answer('🚫 Доступ запрещён. Только для администраторов.')
        return
    args = get_args(message)
    if not args:
        await message.answer('Использование: /complete_booking booking_id\nПример: /complete_booking 123')
        return
    try:
        bid = int(args.strip())
    except Exception:
        await message.answer('Неверный booking_id. Укажите число, например: 123')
        return
    await set_booking_status(bid, 'completed')
    b = await get_booking(bid)
    if not b:
        await message.answer('❌ Бронирование не найдено. Проверьте ID.')
        return
    # send review prompt to the user
    user = await get_user_by_id(b['user_id'])
    if not user or not user['tg_id']:
        await message.answer('❌ Не удалось найти Telegram ID клиента. Возможно, пользователь не зарегистрирован.')
        return
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    rows = [[InlineKeyboardButton(text=str(i), callback_data=f'review:rating:{i}:booking:{bid}') for i in range(1,6)], [InlineKeyboardButton(text='Добавить комментарий', callback_data=f'review:text:booking:{bid}')]]
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    try:
        await message.bot.send_message(user['tg_id'], 'Спасибо, что выбрали нас! ⭐ Как прошёл ваш визит? Оцените от 1 до 5 и поделитесь впечатлениями.', reply_markup=kb)
        await message.answer('✅ Отлично! Клиенту отправлен запрос на отзыв. 📝')
    except Exception as e:
        await message.answer('❌ Ошибка при отправке сообщения клиенту: ' + str(e))

@router.message(Command('cancel_booking'))
async def cmd_cancel_booking(message: Message):
    # Admin command to mark a booking as cancelled (avoids manual DB edits).
    if not is_admin(message.from_user.id):
        await message.answer('🚫 Доступ запрещён. Только для администраторов.')
        return
    args = get_args(message)
    if not args:
        await message.answer('Использование: /cancel_booking booking_id')
        return
    try:
        bid = int(args.strip())
    except Exception:
        await message.answer('Неверный booking_id. Укажите число, например: 123')
        return
    await set_booking_status(bid, 'cancelled')
    # cancel any scheduled tasks for this booking
    try:
        cancel_auto_complete(bid)
    except Exception:
        pass
    try:
        cancel_reminders(bid)
    except Exception:
        pass
    b = await get_booking(bid)
    if not b:
        await message.answer('❌ Бронирование не найдено. Проверьте ID.')
        return
    await message.answer('✅ Бронирование отменено.')


@router.message(Command('export_bookings'))
async def cmd_export_bookings(message: Message):
    # TODO: FROZEN for MVP demo — exported data analytics not part of client demo
    # To enable: uncomment code below and ensure app.admin_utils is imported
    if not is_admin(message.from_user.id):
        await message.answer('Доступ запрещён')
        return
    from app.admin_utils import export_bookings_csv_bytes
    from aiogram.types import InputFile
    from io import BytesIO
    try:
        data = await export_bookings_csv_bytes()
        bio = BytesIO(data)
        bio.seek(0)
        # send BytesIO directly as document; some aiogram versions accept file-like objects
        await message.bot.send_document(message.chat.id, bio, filename='export.csv', caption='Экспорт записей', disable_notification=True)
        await message.answer('Экспорт отправлен')
    except Exception as e:
        await message.answer('Ошибка экспорта: ' + str(e))


@router.message(Command('export_reviews'))
async def cmd_export_reviews(message: Message):
    # TODO: FROZEN for MVP demo — exported data analytics not part of client demo
    # To enable: uncomment code below and ensure app.export is imported
    if not is_admin(message.from_user.id):
        await message.answer('Доступ запрещён')
        return
    from app.export import export_reviews_csv_bytes
    from io import BytesIO
    try:
        data = await export_reviews_csv_bytes()
        bio = BytesIO(data)
        bio.seek(0)
        await message.bot.send_document(message.chat.id, bio, filename='reviews_export.csv', caption='Экспорт отзывов', disable_notification=True)
        await message.answer('Экспорт отправлен')
    except Exception as e:
        await message.answer('Ошибка экспорта: ' + str(e))

@router.callback_query(lambda c: c.data and c.data.startswith('admin:delete_master:choose:'))
async def cb_delete_master_choose(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not is_admin(user_id):
        await callback.answer('Доступ запрещён', show_alert=True)
        return
    try:
        mid = int(callback.data.split(':')[-1])
    except Exception:
        await callback.answer('Неверный id', show_alert=True)
        return
    
    master = await get_master(mid)
    if not master:
        await callback.answer('Мастер не найден', show_alert=True)
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text='✅ Подтвердить', callback_data=f'admin:delete_master:confirm:{mid}'),
        InlineKeyboardButton(text='❌ Отмена', callback_data=f'admin:delete_master:cancel')
    ]])
    
    await callback.message.edit_text(
        f'Вы уверены, что хотите удалить мастера: {master["name"]}?',
        reply_markup=kb
    )
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith('admin:delete_master:confirm:'))
async def cb_delete_master_confirm(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not is_admin(user_id):
        await callback.answer('Доступ запрещён', show_alert=True)
        return
    try:
        mid = int(callback.data.split(':')[-1])
    except Exception:
        await callback.answer('Неверный id', show_alert=True)
        return
    
    master = await get_master(mid)
    master_name = master['name'] if master else 'мастер'
    
    await delete_master(mid)
    await callback.message.edit_text(f'✅ Мастер {master_name} удалён')
    await callback.answer('Удалено')


@router.callback_query(lambda c: c.data == 'admin:delete_master:cancel')
async def cb_delete_master_cancel(callback: CallbackQuery):
    await callback.message.edit_text('❌ Удаление отменено')
    await callback.answer()


@router.message(Command('delete_master'))
async def cmd_delete_master(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer('Доступ запрещён')
        return
    args = get_args(message)
    if not args:
        await message.answer('Использование: /delete_master master_id')
        return
    try:
        mid = int(args.strip())
    except Exception:
        await message.answer('Неверный master_id')
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text='Подтвердить удаление', callback_data=f'confirm_delete_master:{mid}'),
        InlineKeyboardButton(text='Отменить', callback_data=f'cancel_delete_master:{mid}')
    ]])
    await message.answer(f'Вы уверены, что хотите удалить мастера {mid}?', reply_markup=kb)


@router.callback_query(lambda c: c.data and c.data.startswith('admin:master:add:service:'))
async def cb_master_add_select_service(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not is_admin(user_id):
        await callback.answer('Доступ запрещён', show_alert=True)
        return
    
    try:
        service_id = int(callback.data.split(':')[-1])
    except Exception:
        await callback.answer('Неверный ID', show_alert=True)
        return
    
    if user_id not in STAGED_EDITS:
        await callback.answer('Сессия истекла', show_alert=True)
        return
    
    staged = STAGED_EDITS[user_id]
    if 'selected_services' not in staged['data']:
        staged['data']['selected_services'] = []
    
    # Toggle service selection
    if service_id in staged['data']['selected_services']:
        staged['data']['selected_services'].remove(service_id)
    else:
        staged['data']['selected_services'].append(service_id)
    
    await callback.answer(f'Услуга добавлена', show_alert=False)


@router.callback_query(lambda c: c.data == 'admin:master:add:services:done' or c.data.startswith('admin:master:add:confirm:'))
async def cb_master_add_confirm(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not is_admin(user_id):
        await callback.answer('Доступ запрещён', show_alert=True)
        return
    
    if user_id not in STAGED_EDITS:
        await callback.answer('Сессия истекла', show_alert=True)
        return
    
    staged = STAGED_EDITS.pop(user_id, None)
    if not staged:
        await callback.answer('Ошибка сессии', show_alert=True)
        return
    
    d = staged['data']
    try:
        mid = await create_master(d.get('name'), d.get('bio') or '', d.get('contact') or '')
        services_text = ''
        if d.get('selected_services'):
            services_text = f' (услуг: {len(d["selected_services"])})'
        await callback.message.edit_text(f'✅ Мастер {d.get("name")} создан{services_text}')
    except Exception as e:
        await callback.message.edit_text('❌ Ошибка при создании мастера: ' + str(e))
    
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith('admin:master:add:cancel:'))
async def cb_master_add_cancel(callback: CallbackQuery):
    user_id = callback.from_user.id
    STAGED_EDITS.pop(user_id, None)
    await callback.message.edit_text('❌ Создание отменено')
    await callback.answer()
async def cb_confirm_delete_master(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not is_admin(user_id):
        await callback.answer('Доступ запрещён', show_alert=True)
        return
    try:
        mid = int(callback.data.split(':',1)[1])
    except Exception:
        await callback.answer('Неверный id', show_alert=True)
        return
    await delete_master(mid)
    # edit message or send new
    try:
        await callback.message.edit_text(f'Мастер {mid} удалён')
    except Exception:
        await callback.message.answer(f'Мастер {mid} удалён')
    await callback.answer('Удалено')



@router.callback_query(lambda c: c.data and c.data.startswith('cancel_delete_master:'))
async def cb_cancel_delete_master(callback: CallbackQuery):
    try:
        mid = int(callback.data.split(':',1)[1])
    except Exception:
        await callback.answer('Неверный id', show_alert=True)
        return
    try:
        await callback.message.edit_text(f'Удаление мастера {mid} отменено')
    except Exception:
        await callback.message.answer(f'Удаление мастера {mid} отменено')
    await callback.answer('Отменено')

@router.message(Command('edit_master'))
async def cmd_edit_master(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer('Доступ запрещён')
        return
    # usage: /edit_master id|Name|bio|contact  OR /edit_master id  (start interactive)
    args = get_args(message)
    if not args:
        await message.answer('Использование: /edit_master id|Name|bio|contact  OR /edit_master id (для интерактивного редактирования)')
        return
    if '|' in args:
        try:
            parts = [x.strip() for x in args.split('|',3)]
            mid = int(parts[0])
            name = parts[1] or None
            bio = parts[2] or None
            contact = parts[3] or None
        except Exception:
            await message.answer('Неверный формат аргументов')
            return
        await update_master(mid, name=name, bio=bio, contact=contact)
        await message.answer('Мастер обновлён')
        return
    # start interactive flow
    try:
        mid = int(args.strip())
    except Exception:
        await message.answer('Неверный id')
        return
    # fetch current data
    m = await get_master(mid)
    if not m:
        await message.answer('Мастер не найден')
        return
    STAGED_EDITS[message.from_user.id] = {'type':'master', 'id': mid, 'step':'name', 'data': {'name': m['name'], 'bio': m['bio'], 'contact': m['contact']}}
    await message.answer(f"Введите новое имя мастера — кратко и понятно (пример: Иван Иванов). Оставьте пустым, чтобы сохранить текущее: {m['name']}")


@router.message(Command('edit_service'))
async def cmd_edit_service(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer('Доступ запрещён')
        return
    # usage: /edit_service id|Name|price|duration|description  OR /edit_service id (interactive)
    args = get_args(message)
    if not args:
        await message.answer('Использование: /edit_service id|Name|price|duration|description  OR /edit_service id (для интерактивного редактирования)')
        return
    if '|' in args:
        try:
            parts = [x.strip() for x in args.split('|',4)]
            sid = int(parts[0])
            name = parts[1] or None
            price = float(parts[2]) if parts[2] else None
            duration = int(parts[3]) if parts[3] else None
            desc = parts[4] or None
        except Exception:
            await message.answer('Неверный формат аргументов')
            return
        await update_service(sid, name=name, description=desc, price=price, duration_minutes=duration)
        await message.answer('Услуга обновлена')
        return
    try:
        sid = int(args.strip())
    except Exception:
        await message.answer('Неверный id')
        return
    s = await get_service(sid)
    if not s:
        await message.answer('Услуга не найдена')
        return
    STAGED_EDITS[message.from_user.id] = {'type':'service', 'id': sid, 'step':'name', 'data': {'name': s['name'], 'description': s['description'], 'price': s['price'], 'duration_minutes': s['duration_minutes']}}
    await message.answer(f"Введите новое название услуги (пример: Маникюр, оставить пустым чтобы оставить текущее: {s['name']})")

@router.message(Command('delete_service'))
async def cmd_delete_service(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer('Доступ запрещён')
        return
    args = get_args(message)
    if not args:
        await message.answer('Использование: /delete_service service_id')
        return
    try:
        sid = int(args.strip())
    except Exception:
        await message.answer('Неверный service_id')
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text='Подтвердить удаление', callback_data=f'confirm_delete_service:{sid}'),
        InlineKeyboardButton(text='Отменить', callback_data=f'cancel_delete_service:{sid}')
    ]])
    await message.answer(f'Вы уверены, что хотите удалить услугу {sid}?', reply_markup=kb)


# ===== INLINE ADMIN SERVICE MANAGEMENT =====

async def _build_services_page_admin(services, page: int):
    """Build admin service list with delete/edit options and pagination."""
    start = page * 5
    end = start + 5
    page_items = services[start:end]
    kb_rows = []
    text_lines = []
    
    for s in page_items:
        text = f"💫 {s['name']} — {s['price']}€"
        text_lines.append(text)
        kb_rows.append([
            InlineKeyboardButton(text=f'✏️ Изменить: {s["name"]}', callback_data=f'admin:service:edit:choose:{s["id"]}'),
            InlineKeyboardButton(text=f'🗑 Удалить: {s["name"]}', callback_data=f'admin:service:delete:choose:{s["id"]}')
        ])
    
    # pagination
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text='⬅️ Назад', callback_data=f'admin:services:page:{page-1}'))
    if end < len(services):
        nav_row.append(InlineKeyboardButton(text='➡️ Далее', callback_data=f'admin:services:page:{page+1}'))
    if nav_row:
        kb_rows.append(nav_row)
    
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
    text = "\n".join(text_lines) or 'Нет доступных услуг.'
    return text, kb


@router.callback_query(lambda c: c.data == 'admin:service:add')
async def cb_admin_service_add(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not is_admin(user_id):
        await callback.answer('Доступ запрещён', show_alert=True)
        return
    
    STAGED_EDITS[user_id] = {'type': 'service_add', 'step': 'name', 'data': {}}
    await callback.message.edit_text('Введите данные услуги. Бот проведёт вас по шагам.')
    await callback.answer()


@router.callback_query(lambda c: c.data == 'admin:service:edit')
async def cb_admin_service_edit(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not is_admin(user_id):
        await callback.answer('Доступ запрещён', show_alert=True)
        return
    
    services = await list_services()
    if not services:
        await callback.answer('Нет услуг для редактирования', show_alert=True)
        return
    
    text, kb = await _build_services_page_admin(services, 0)
    await callback.message.edit_text(f'Выберите услугу для редактирования:\n\n{text}', reply_markup=kb)
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith('admin:services:page:'))
async def cb_admin_services_page(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not is_admin(user_id):
        await callback.answer('Доступ запрещён', show_alert=True)
        return
    
    try:
        page = int(callback.data.split(':')[-1])
    except Exception:
        await callback.answer('Неверная страница', show_alert=True)
        return
    
    services = await list_services()
    text, kb = await _build_services_page_admin(services, page)
    await callback.message.edit_text(f'Выберите услугу для редактирования:\n\n{text}', reply_markup=kb)
    await callback.answer()


@router.callback_query(lambda c: c.data == 'admin:service:delete')
async def cb_admin_service_delete(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not is_admin(user_id):
        await callback.answer('Доступ запрещён', show_alert=True)
        return
    
    services = await list_services()
    if not services:
        await callback.answer('Нет услуг для удаления', show_alert=True)
        return
    
    # Show first 5 services with delete options
    kb_rows = []
    text_lines = ['Выберите услугу для удаления:\n']
    page_size = 5
    
    for i, s in enumerate(services[:page_size]):
        text_lines.append(f"{s['name']} — {s['price']}€")
        kb_rows.append([InlineKeyboardButton(text=f'{s["name"]}', callback_data=f'admin:service:delete:choose:{s["id"]}')])
    
    if len(services) > page_size:
        kb_rows.append([InlineKeyboardButton(text='➡️ Далее', callback_data='admin:services:delete:page:1')])
    
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
    await callback.message.edit_text('\n'.join(text_lines), reply_markup=kb)
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith('admin:services:delete:page:'))
async def cb_admin_services_delete_page(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not is_admin(user_id):
        await callback.answer('Доступ запрещён', show_alert=True)
        return
    
    try:
        page = int(callback.data.split(':')[-1])
    except Exception:
        await callback.answer('Неверная страница', show_alert=True)
        return
    
    services = await list_services()
    page_size = 5
    start = page * page_size
    end = start + page_size
    page_items = services[start:end]
    
    kb_rows = []
    text_lines = [f'Выберите услугу для удаления (стр. {page + 1}):\n']
    
    for s in page_items:
        text_lines.append(f"{s['name']} — {s['price']}€")
        kb_rows.append([InlineKeyboardButton(text=f'{s["name"]}', callback_data=f'admin:service:delete:choose:{s["id"]}')])
    
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text='⬅️ Назад', callback_data=f'admin:services:delete:page:{page-1}'))
    if end < len(services):
        nav_row.append(InlineKeyboardButton(text='➡️ Далее', callback_data=f'admin:services:delete:page:{page+1}'))
    if nav_row:
        kb_rows.append(nav_row)
    
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
    await callback.message.edit_text('\n'.join(text_lines), reply_markup=kb)
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith('admin:service:delete:choose:'))
async def cb_admin_service_delete_choose(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not is_admin(user_id):
        await callback.answer('Доступ запрещён', show_alert=True)
        return
    
    try:
        sid = int(callback.data.split(':')[-1])
    except Exception:
        await callback.answer('Неверный id', show_alert=True)
        return
    
    service = await get_service(sid)
    if not service:
        await callback.answer('Услуга не найдена', show_alert=True)
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text='✅ Да', callback_data=f'admin:service:delete:confirm:{sid}'),
        InlineKeyboardButton(text='❌ Нет', callback_data='admin:service:delete:cancel')
    ]])
    
    await callback.message.edit_text(
        f'Удалить услугу: {service["name"]}?',
        reply_markup=kb
    )
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith('admin:service:delete:confirm:'))
async def cb_admin_service_delete_confirm(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not is_admin(user_id):
        await callback.answer('Доступ запрещён', show_alert=True)
        return
    
    try:
        sid = int(callback.data.split(':')[-1])
    except Exception:
        await callback.answer('Неверный id', show_alert=True)
        return
    
    service = await get_service(sid)
    service_name = service['name'] if service else 'услуга'
    
    await delete_service(sid)
    await callback.message.edit_text(f'✅ Услуга "{service_name}" удалена')
    await callback.answer('Удалено')


@router.callback_query(lambda c: c.data == 'admin:service:delete:cancel')
async def cb_admin_service_delete_cancel(callback: CallbackQuery):
    await callback.message.edit_text('❌ Удаление отменено')
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith('admin:service:edit:choose:'))
async def cb_admin_service_edit_choose(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not is_admin(user_id):
        await callback.answer('Доступ запрещён', show_alert=True)
        return
    
    try:
        sid = int(callback.data.split(':')[-1])
    except Exception:
        await callback.answer('Неверный id', show_alert=True)
        return
    
    s = await get_service(sid)
    if not s:
        await callback.answer('Услуга не найдена', show_alert=True)
        return
    
    STAGED_EDITS[user_id] = {'type': 'service', 'id': sid, 'step': 'name', 'data': {'name': s['name'], 'description': s['description'], 'price': s['price'], 'duration_minutes': s['duration_minutes']}}
    await callback.message.edit_text(f"Введите новое название услуги (текущее: {s['name']})")
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith('confirm_delete_service:'))
async def cb_confirm_delete_service(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not is_admin(user_id):
        await callback.answer('Доступ запрещён', show_alert=True)
        return
    try:
        sid = int(callback.data.split(':',1)[1])
    except Exception:
        await callback.answer('Неверный id', show_alert=True)
        return
    await delete_service(sid)
    try:
        await callback.message.edit_text(f'Услуга {sid} удалена')
    except Exception:
        await callback.message.answer(f'Услуга {sid} удалена')
    await callback.answer('Удалено')


@router.callback_query(lambda c: c.data and c.data.startswith('cancel_delete_service:'))
async def cb_cancel_delete_service(callback: CallbackQuery):
    try:
        sid = int(callback.data.split(':',1)[1])
    except Exception:
        await callback.answer('Неверный id', show_alert=True)
        return
    try:
        await callback.message.edit_text(f'Удаление услуги {sid} отменено')
    except Exception:
        await callback.message.answer(f'Удаление услуги {sid} отменено')
    await callback.answer('Отменено')

@router.message(lambda m: m.from_user and m.from_user.id in STAGED_EDITS)
async def handle_staged_edit(message: Message):
    """Handle messages while an admin has an active staged edit."""
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.answer('Доступ запрещён')
        return
    staged = STAGED_EDITS.get(user_id)
    if not staged:
        # shouldn't happen but guard
        return
    t = staged['type']
    step = staged['step']

    text = (message.text or '').strip()

    if t == 'master':
        if step == 'name':
            if text:
                if len(text) > MAX_NAME_LEN:
                    await message.answer(f'Имя слишком длинное (макс {MAX_NAME_LEN} символов), попробуйте ещё раз')
                    return
                staged['data']['name'] = text
            staged['step'] = 'bio'
            await message.answer(f"Введите короткое описание (bio). Пример: 'Опытный мастер по стрижкам' (макс {MAX_BIO_LEN} символов). Оставьте пустым, чтобы сохранить текущее: {staged['data'].get('bio')}")
            return
        if step == 'bio':
            if text:
                if len(text) > MAX_BIO_LEN:
                    await message.answer(f'Bio слишком длинное (макс {MAX_BIO_LEN} символов), попробуйте ещё раз')
                    return
                staged['data']['bio'] = text
            staged['step'] = 'contact'
            await message.answer(f"Введите контакт (например: +7 900 000-00-00 или @username). Оставьте пустым, чтобы сохранить текущее: {staged['data'].get('contact')}")
            return
        if step == 'contact':
            if text:
                if len(text) > MAX_CONTACT_LEN:
                    await message.answer(f'Контакт слишком длинный (макс {MAX_CONTACT_LEN} символов), попробуйте ещё раз')
                    return
                staged['data']['contact'] = text
            # show confirmation
            d = staged['data']
            summary = f"Подтвердите изменения для мастера {staged['id']}:\nИмя: {d.get('name')}\nBio: {d.get('bio')}\nКонтакт: {d.get('contact')}"
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text='Применить', callback_data=f'confirm_apply_edit:master:{staged["id"]}:{user_id}'),
                InlineKeyboardButton(text='Отменить', callback_data=f'cancel_apply_edit:{user_id}')
            ]])
            staged['step'] = 'confirm'
            await message.answer(summary, reply_markup=kb)
            return
    if t == 'master_add':
        # interactive creation flow for a new master
        if step == 'name':
            if not text:
                await message.answer('Введите имя мастера (обязательно). Попробуйте ещё раз')
                return
            if len(text) > MAX_NAME_LEN:
                await message.answer(f'Имя слишком длинное (макс {MAX_NAME_LEN} символов), попробуйте ещё раз')
                return
            staged['data']['name'] = text
            staged['step'] = 'bio'
            await message.answer(f"Введите короткое описание (bio). Пример: 'Опытный мастер по стрижкам' (макс {MAX_BIO_LEN} символов).")
            return
        if step == 'bio':
            if text:
                if len(text) > MAX_BIO_LEN:
                    await message.answer(f'Bio слишком длинное (макс {MAX_BIO_LEN} символов), попробуйте ещё раз')
                    return
                staged['data']['bio'] = text
            staged['step'] = 'contact'
            await message.answer(f"Введите контакт (например: +7 900 000-00-00 или @username).")
            return
        if step == 'contact':
            if text:
                if len(text) > MAX_CONTACT_LEN:
                    await message.answer(f'Контакт слишком длинный (макс {MAX_CONTACT_LEN} символов), попробуйте ещё раз')
                    return
                staged['data']['contact'] = text
            
            # Move to service selection step
            services = await list_services()
            if services:
                staged['step'] = 'services'
                # Show first 5 services
                kb_rows = []
                for s in services[:5]:
                    kb_rows.append([InlineKeyboardButton(text=f'{s["name"]} — {s["price"]}€', callback_data=f'admin:master:add:service:{s["id"]}')])
                if len(services) > 5:
                    kb_rows.append([InlineKeyboardButton(text='➡️ Далее', callback_data='admin:master:add:services:page:1')])
                kb_rows.append([InlineKeyboardButton(text='✅ Готово', callback_data='admin:master:add:services:done')])
                kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
                await message.answer('Выберите услуги для мастера (можно несколько или пропустить):', reply_markup=kb)
            else:
                # No services, skip to confirmation
                staged['step'] = 'confirm'
                d = staged['data']
                summary = f"Подтвердите данные мастера:\nИмя: {d.get('name')}\nBio: {d.get('bio')}\nКонтакт: {d.get('contact')}"
                kb = InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text='✅ Создать', callback_data=f'admin:master:add:confirm:{message.from_user.id}'),
                    InlineKeyboardButton(text='❌ Отменить', callback_data=f'admin:master:add:cancel:{message.from_user.id}')
                ]])
                await message.answer(summary, reply_markup=kb)
            return
    elif t == 'service':
        if step == 'name':
            if text:
                if len(text) > MAX_NAME_LEN:
                    await message.answer(f'Имя слишком длинное (макс {MAX_NAME_LEN} символов), попробуйте ещё раз')
                    return
                staged['data']['name'] = text
            staged['step'] = 'price'
            await message.answer(f"Введите цену (пример: 12.5). Допустимый диапазон: {MIN_PRICE} — {MAX_PRICE}. Оставьте пустым, чтобы сохранить текущее: {staged['data'].get('price')}")
            return
        if step == 'price':
            if text:
                try:
                    v = float(text)
                except Exception:
                    await message.answer('Неверный формат цены. Введите число, например: 12.5')
                    return
                if not (MIN_PRICE <= v <= MAX_PRICE):
                    await message.answer(f'Цена должна быть между {MIN_PRICE} и {MAX_PRICE}. Введите корректное значение, например 12.5')
                    return
                staged['data']['price'] = v
            staged['step'] = 'duration'
            await message.answer(f"Введите длительность в минутах (пример: 30). Допустимый диапазон: {MIN_DURATION} — {MAX_DURATION} минут. Оставьте пустым, чтобы сохранить текущее: {staged['data'].get('duration_minutes')}")
            return
        if step == 'duration':
            if text:
                try:
                    v = int(text)
                except Exception:
                    await message.answer('Неверный формат длительности. Введите целое число, например: 45')
                    return
                if not (MIN_DURATION <= v <= MAX_DURATION):
                    await message.answer(f'Длительность должна быть между {MIN_DURATION} и {MAX_DURATION} минут. Введите корректное значение, например: 30')
                    return
                staged['data']['duration_minutes'] = v
            staged['step'] = 'description'
            await message.answer(f"Введите описание (оставьте пустым чтобы оставить текущее: {staged['data'].get('description')})")
            return
        if step == 'description':
            if text:
                if len(text) > MAX_DESC_LEN:
                    await message.answer(f'Описание слишком длинное (макс {MAX_DESC_LEN} символов), попробуйте ещё раз')
                    return
                staged['data']['description'] = text
            d = staged['data']
            summary = f"Подтвердите изменения для услуги {staged['id']}:\nИмя: {d.get('name')}\nЦена: {d.get('price')}\nДлительность: {d.get('duration_minutes')}\nОписание: {d.get('description')}"
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text='Применить', callback_data=f'confirm_apply_edit:service:{staged["id"]}:{user_id}'),
                InlineKeyboardButton(text='Отменить', callback_data=f'cancel_apply_edit:{user_id}')
            ]])
            staged['step'] = 'confirm'
            await message.answer(summary, reply_markup=kb)
            return
    if t == 'service_add':
        # interactive creation flow for a new service
        if step == 'name':
            if not text:
                await message.answer('Введите название услуги (обязательно). Попробуйте ещё раз')
                return
            if len(text) > MAX_NAME_LEN:
                await message.answer(f'Имя слишком длинное (макс {MAX_NAME_LEN} символов), попробуйте ещё раз')
                return
            staged['data']['name'] = text
            staged['step'] = 'price'
            await message.answer(f"Введите цену (пример: 12.5). Допустимый диапазон: {MIN_PRICE} — {MAX_PRICE}.")
            return
        if step == 'price':
            if not text:
                await message.answer('Введите цену (обязательно). Попробуйте ещё раз')
                return
            try:
                v = float(text)
            except Exception:
                await message.answer('Неверный формат цены. Введите число, например: 12.5')
                return
            if not (MIN_PRICE <= v <= MAX_PRICE):
                await message.answer(f'Цена должна быть между {MIN_PRICE} и {MAX_PRICE}. Введите корректное значение, например 12.5')
                return
            staged['data']['price'] = v
            staged['step'] = 'duration'
            await message.answer(f"Введите длительность в минутах (пример: 30). Допустимый диапазон: {MIN_DURATION} — {MAX_DURATION} минут.")
            return
        if step == 'duration':
            if not text:
                await message.answer('Введите длительность (обязательно). Попробуйте ещё раз')
                return
            try:
                v = int(text)
            except Exception:
                await message.answer('Неверный формат длительности. Введите целое число, например: 45')
                return
            if not (MIN_DURATION <= v <= MAX_DURATION):
                await message.answer(f'Длительность должна быть между {MIN_DURATION} и {MAX_DURATION} минут. Введите корректное значение, например: 30')
                return
            staged['data']['duration_minutes'] = v
            staged['step'] = 'description'
            await message.answer(f"Введите описание для услуги (можно оставить пустым)")
            return
        if step == 'description':
            if text:
                if len(text) > MAX_DESC_LEN:
                    await message.answer(f'Описание слишком длинное (макс {MAX_DESC_LEN} символов), попробуйте ещё раз')
                    return
                staged['data']['description'] = text
            # create service
            d = staged['data']
            try:
                sid = await create_service(d.get('name'), d.get('description') or '', d.get('price'), d.get('duration_minutes'))
                await message.answer(f'Услуга добавлена id={sid}')
            except Exception as e:
                await message.answer('Ошибка при добавлении услуги: ' + str(e))
            STAGED_EDITS.pop(user_id, None)
            return


@router.callback_query(lambda c: c.data and c.data.startswith('confirm_apply_edit:'))
async def cb_confirm_apply_edit(callback: CallbackQuery):
    # format: confirm_apply_edit:<type>:<id>:<author_user_id>
    parts = callback.data.split(':')
    if len(parts) != 4:
        await callback.answer('Неверные данные', show_alert=True)
        return
    _, typ, obj_id_s, author_id_s = parts
    try:
        obj_id = int(obj_id_s)
        author_id = int(author_id_s)
    except Exception:
        await callback.answer('Неверный id', show_alert=True)
        return
    if callback.from_user.id != author_id:
        await callback.answer('Только автор может подтвердить изменения', show_alert=True)
        return
    if not is_admin(callback.from_user.id):
        await callback.answer('Доступ запрещён', show_alert=True)
        return
    staged = STAGED_EDITS.pop(author_id, None)
    if not staged:
        await callback.answer('Нечего применять', show_alert=True)
        return
    try:
        if typ == 'master':
            d = staged['data']
            await update_master(obj_id, name=d.get('name'), bio=d.get('bio'), contact=d.get('contact'))
            await callback.message.edit_text(f'Изменения для мастера {obj_id} применены')
        elif typ == 'service':
            d = staged['data']
            await update_service(obj_id, name=d.get('name'), description=d.get('description'), price=d.get('price'), duration_minutes=d.get('duration_minutes'))
            await callback.message.edit_text(f'Изменения для услуги {obj_id} применены')
        else:
            await callback.answer('Неверный тип', show_alert=True)
            return
    except Exception as e:
        await callback.message.answer('Ошибка при применении: ' + str(e))
    await callback.answer('Готово')


@router.callback_query(lambda c: c.data and c.data.startswith('cancel_apply_edit:'))
async def cb_cancel_apply_edit(callback: CallbackQuery):
    # format: cancel_apply_edit:<author_user_id>
    parts = callback.data.split(':')
    if len(parts) != 2:
        await callback.answer('Неверные данные', show_alert=True)
        return
    try:
        author_id = int(parts[1])
    except Exception:
        await callback.answer('Неверный id', show_alert=True)
        return
    if callback.from_user.id != author_id:
        await callback.answer('Только автор может отменить', show_alert=True)
        return
    STAGED_EDITS.pop(author_id, None)
    try:
        await callback.message.edit_text('Редактирование отменено')
    except Exception:
        await callback.message.answer('Редактирование отменено')
    await callback.answer('Отменено')