from aiogram import Router
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.filters import StateFilter, Command
from app.repo import get_master, get_or_create_user, create_booking, list_masters, SlotTaken, DoubleBooking, get_service, average_rating_for_master, get_booking, set_booking_status
from app.utils import valid_phone, format_rating, get_args_from_message as get_args

# Для автозавершения
from app.auto_complete import schedule_auto_complete, cancel_auto_complete
from app.reminders import schedule_reminders, cancel_reminders

router = Router()

class BookingStates(StatesGroup):
    SERVICE = State()
    MASTER = State()
    DATE = State()
    TIME = State()
    NAME = State()
    PHONE = State()
    CONFIRM = State()

def create_time_keyboard(slots, page, per_page=9):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    start = page * per_page
    end = start + per_page
    current_slots = slots[start:end]
    rows = []
    for i in range(0, len(current_slots), 3):
        row = [InlineKeyboardButton(text=t, callback_data=f'book:time:select:{t}') for t in current_slots[i:i+3]]
        rows.append(row)
    # Navigation
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text='⬅️ Previous', callback_data=f'book:time:page:{page-1}'))
    if end < len(slots):
        nav_row.append(InlineKeyboardButton(text='Next ➡️', callback_data=f'book:time:page:{page+1}'))
    if nav_row:
        rows.append(nav_row)
    return InlineKeyboardMarkup(inline_keyboard=rows)

async def _set_state(ctx: FSMContext, state_obj: State):
    """Set FSM state in a way compatible with real FSMContext and the test FakeState.

    Prefer using ctx.set_state when available (real aiogram), then fall back to
    other approaches used in tests (state_obj.set() or storing '_state' in data).
    Adds debug prints to help identify which mechanism is used at runtime.
    """
    # Try context-aware API first (aiogram FSMContext.set_state)
    try:
        await ctx.set_state(state_obj)
        try:
            print('set_state: ctx.set_state(state_obj) succeeded')
        except Exception:
            pass
        return
    except Exception as e:
        try:
            print('set_state: ctx.set_state(state_obj) failed:', repr(e))
        except Exception:
            pass
    try:
        await ctx.set_state(state_obj.state)
        try:
            print('set_state: ctx.set_state(state_obj.state) succeeded')
        except Exception:
            pass
        return
    except Exception as e:
        try:
            print('set_state: ctx.set_state(state_obj.state) failed:', repr(e))
        except Exception:
            pass
    # Try State.set() (some aiogram versions may support this)
    try:
        await state_obj.set()
        try:
            print('set_state: state_obj.set() succeeded')
        except Exception:
            pass
        return
    except Exception as e:
        try:
            print('set_state: state_obj.set() failed:', repr(e))
        except Exception:
            pass
    # Last resort: store state marker in context data (used by FakeState in tests)
    try:
        await ctx.update_data(_state=state_obj.state)
        try:
            print('set_state: ctx.update_data(_state=...) succeeded')
        except Exception:
            pass
    except Exception as e:
        try:
            print('set_state: ctx.update_data(_state=...) failed:', repr(e))
        except Exception:
            pass


async def _get_state(ctx: FSMContext):
    try:
        s = await ctx.get_state()
        try:
            print('get_state: ctx.get_state() ->', s)
        except Exception:
            pass
        return s
    except Exception as e:
        try:
            print('get_state: ctx.get_state() failed:', repr(e))
        except Exception:
            pass
        data = await ctx.get_data()
        s = data.get('_state')
        try:
            print('get_state: fallback ctx.get_data() ->', s)
        except Exception:
            pass
        return s

@router.callback_query(lambda q: q.data and q.data.startswith('book:service:'))
async def cb_select_service(query: CallbackQuery, state: FSMContext):
    service_id = int(query.data.split(':')[-1])
    await state.update_data(service_id=service_id)
    # record the initiator user id so we can detect mismatched interactions
    
    try:
        await state.update_data(booking_user_id=query.from_user.id)
    except Exception:
        pass
    try:
        await state.update_data(booking_user_id=query.from_user.id)
        cur = await state.get_state()
        data_now = await state.get_data()
        print('cb_select_service: after update ->', cur, data_now)
    except Exception:
        pass
    # list masters
    masters = await list_masters()
    if not masters:
        await query.message.answer('😔 К сожалению, сейчас нет доступных мастеров. Попробуйте позже или обратитесь в поддержку.')
        return
    text = 'Выберите мастера или без выбора:'
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    buttons = []
    for m in masters:
        avg, cnt = await average_rating_for_master(m['id'])
        rating = format_rating(avg, cnt)
        label = m['name']
        if rating:
            label = f"{m['name']} {rating}"
        buttons.append([InlineKeyboardButton(text=label, callback_data=f'book:master:{m["id"]}')])
    buttons.append([InlineKeyboardButton(text='Без выбора', callback_data='book:master:0')])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await query.message.answer(text, reply_markup=kb)
    await query.answer("")

@router.callback_query(lambda q: q.data and q.data.startswith('book:master:'))
async def cb_select_master(query: CallbackQuery, state: FSMContext):
    master_id = int(query.data.split(':')[-1])
    await state.update_data(master_id=master_id)
    # ensure booking_user_id reflects the user who chose the master
    try:
        await state.update_data(booking_user_id=query.from_user.id)
    except Exception:
        pass
    try:
        print('cb_select_master called', master_id, 'by user', query.from_user.id)
    except Exception:
        pass
    # show master's working days/time (MVP: derive from master_schedule or defaults)
    try:
        from app.scheduler import get_master_work_info
        days, start_time, end_time, _ = await get_master_work_info(master_id)
        # convert days list to readable string, compress consecutive ranges
        rus = ['Пн','Вт','Ср','Чт','Пт','Сб','Вс']
        def format_days(ds):
            if not ds:
                return ''
            ds = sorted(ds)
            ranges = []
            start = prev = ds[0]
            for d in ds[1:]:
                if d == prev + 1:
                    prev = d
                    continue
                if start == prev:
                    ranges.append(rus[start])
                else:
                    ranges.append(f"{rus[start]}–{rus[prev]}")
                start = prev = d
            if start == prev:
                ranges.append(rus[start])
            else:
                ranges.append(f"{rus[start]}–{rus[prev]}")
            return ','.join(ranges)
        days_str = format_days(days)
        await query.message.answer(f'Мастер работает: {days_str}, {start_time}–{end_time}')
    except Exception:
        pass
    await query.message.answer('📅 Введите дату визита в формате ГГГГ-ММ-ДД. Пример: 2026-01-15')
    await _set_state(state, BookingStates.DATE)
    # dump state after setting for diagnostic
    try:
        cur = await state.get_state()
        data_now = await state.get_data()
        print('cb_select_master: after set_state ->', cur, data_now)
    except Exception:
        pass
    await query.answer("")


# Manual request flow: states
class ManualRequestStates(StatesGroup):
    PREFER = State()
    NAME = State()
    PHONE = State()
    CONFIRM = State()


@router.callback_query(lambda q: q.data and q.data.startswith('manual:request:start'))
async def cb_manual_start(query: CallbackQuery, state: FSMContext):
    # can be 'manual:request:start' or 'manual:request:start:master:<id>'
    parts = query.data.split(':')
    master_id = None
    if len(parts) == 4 and parts[2] == 'master':
        try:
            master_id = int(parts[3])
        except Exception:
            master_id = None
    await state.update_data(manual_master_id=master_id)
    await state.update_data(manual_service_id=(await state.get_data()).get('service_id'))
    await query.message.answer('🕒 Опишите предпочитаемое время или дополнительные пожелания (например: утро, после 16:00). Оставьте пустым, если нет предпочтений.')
    await _set_state(state, ManualRequestStates.PREFER)
    await query.answer("")


@router.callback_query(lambda q: q.data and q.data.startswith('manual:request:cancel'))
async def cb_manual_cancel(query: CallbackQuery, state: FSMContext):
    await state.clear()
    await query.message.answer('Ручная заявка отменена.')
    await query.answer("")


@router.message(StateFilter(ManualRequestStates.PREFER))
async def mr_prefer(message: Message, state: FSMContext):
    pref = (message.text or '').strip()
    await state.update_data(manual_prefer=pref)
    await message.answer('Введите ваше имя для заявки:')
    await _set_state(state, ManualRequestStates.NAME)


@router.message(StateFilter(ManualRequestStates.NAME))
async def mr_name(message: Message, state: FSMContext):
    name = (message.text or '').strip()
    if not name:
        await message.answer('Имя не может быть пустым. Введите ваше имя:')
        return
    await state.update_data(manual_name=name)
    await message.answer('Введите телефон (например, +37061234567):')
    await _set_state(state, ManualRequestStates.PHONE)


@router.message(StateFilter(ManualRequestStates.PHONE))
async def mr_phone(message: Message, state: FSMContext):
    phone = (message.text or '').strip()
    from app.utils import valid_phone
    if not valid_phone(phone):
        await message.answer('Неверный формат телефона. Попробуйте +37061234567')
        return
    await state.update_data(manual_phone=phone)
    data = await state.get_data()
    text = f"Ручная заявка:\nСервис ID: {data.get('manual_service_id')}\nМастер ID: {data.get('manual_master_id') or 'не указан'}\nПредпочтения: {data.get('manual_prefer') or ''}\nИмя: {data.get('manual_name')}\nТелефон: {data.get('manual_phone')}"
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Отправить', callback_data='manual:request:confirm'), InlineKeyboardButton(text='Отмена', callback_data='manual:request:cancel')]])
    await message.answer(text, reply_markup=kb)
    await _set_state(state, ManualRequestStates.CONFIRM)


@router.callback_query(lambda q: q.data and q.data.startswith('manual:request:confirm'))
async def cb_manual_confirm(query: CallbackQuery, state: FSMContext):
    cur = await _get_state(state)
    if cur != ManualRequestStates.CONFIRM.state:
        await query.answer("")
        return
    data = await state.get_data()
    # ensure user
    user = await get_or_create_user(query.from_user.id, name=data.get('manual_name'), phone=data.get('manual_phone'))
    # construct text
    text = f"manual_request service={data.get('manual_service_id')} master={data.get('manual_master_id')} pref={data.get('manual_prefer')} name={data.get('manual_name')} phone={data.get('manual_phone')}"
    from app.repo import create_manual_request, get_service, get_master
    rid = await create_manual_request(user['id'], text)
    try:
        from app.notify import notify_admins
        service = await get_service(data.get('manual_service_id')) if data.get('manual_service_id') else None
        master = await get_master(data.get('manual_master_id')) if data.get('manual_master_id') else None
        service_name = service['name'] if service else "неизвестная"
        master_name = master['name'] if master else "без выбора"
        msg = f"📌 Ручная заявка\nКлиент: {data.get('manual_name')}\nТелефон: {data.get('manual_phone')}\nУслуга: {service_name}\nМастер: {master_name}\nПожелание: {data.get('manual_prefer', 'нет')}"
        await notify_admins(msg)
    except Exception:
        pass
    await query.message.answer('✅ Ручная заявка отправлена админам. Мы свяжемся с вами в ближайшее время! 📞')
    await state.clear()
    await query.answer("")

@router.callback_query(lambda q: q.data and q.data.startswith('book:master_choose:'))
async def cb_master_choose(query: CallbackQuery, state: FSMContext):
    mid = int(query.data.split(':')[-1])
    data = await state.get_data()
    date_s = data.get('date')
    svc_id = data.get('service_id')
    try:
        print('cb_master_choose called', mid, date_s, svc_id)
    except Exception:
        pass
    from app.scheduler import generate_slots
    from app.repo import get_service, get_master
    svc = await get_service(svc_id)
    if not svc:
        await query.message.answer('❌ Ошибка: услуга не найдена. Попробуйте начать заново.')
        await query.answer("")
        return
    # Defensive: if date wasn't saved in state, prompt the user to re-enter
    if not date_s:
        await query.message.answer('Похоже, дата не была сохранена. Пожалуйста, введите дату в формате YYYY-MM-DD.')
        await _set_state(state, BookingStates.DATE)
        await query.answer("")
        return
    slots = await generate_slots(mid, date_s, svc['duration_minutes'])
    if not slots:
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text='Отправить ручную заявку админу', callback_data=f'manual:request:start:master:{mid}'),
            InlineKeyboardButton(text='Отмена', callback_data='manual:request:cancel')
        ]])
        await query.message.answer('😔 На этот день нет доступных слотов для этого мастера. Хотите отправить ручную заявку?', reply_markup=kb)
        await query.answer("")
        return
    kb = create_time_keyboard(slots, 0)
    await state.update_data(slots=slots, current_page=0)
    await query.message.answer(f'Доступные слоты для мастера { (await get_master(mid)) ["name"] } на {date_s}:', reply_markup=kb)
    await _set_state(state, BookingStates.TIME)
    await query.answer("")

@router.message(StateFilter(BookingStates.DATE))
async def process_date(message: Message, state: FSMContext):
    # explicit debug entry
    try:
        print("process_date entered", message.text)
    except Exception:
        pass

    # entry debug: confirm handler received a message and check current state
    try:
        print('process_date entry', getattr(message.from_user, 'id', None), getattr(message, 'text', None))
    except Exception:
        pass
    date_s = message.text.strip()
    # minimal validation
    try:
        import datetime
        datetime.date.fromisoformat(date_s)
    except Exception:
        try:
            print('process_date returning: invalid date format', date_s)
        except Exception:
            pass
        await message.answer('Неверный формат даты. Попробуйте YYYY-MM-DD')
        return

    # Check that the message author is the same user who initiated booking flow
    data = await state.get_data()
    try:
        print('state data:', data)
    except Exception:
        pass

    initiator = data.get('booking_user_id')
    if initiator and initiator != message.from_user.id:
        try:
            print('process_date returning: user mismatch, initiator:', initiator, 'message user:', message.from_user.id)
        except Exception:
            pass
        await message.answer('Похоже, вы используете другой аккаунт, чем тот, что начинал бронирование. Пожалуйста, нажмите "Записаться" ещё раз в своём аккаунте.')
        return

    # check service id presence
    svc_id = data.get('service_id')
    if not svc_id:
        try:
            print('process_date returning: missing service_id in state')
        except Exception:
            pass
        await message.answer('Ошибка: service_id потерян в состоянии. Начните запись заново через /start')
        return

    await state.update_data(date=date_s)

    # debug: confirm handler was called with parsed date
    try:
        print("process_date called", date_s)
    except Exception:
        pass

    data = await state.get_data()
    master_id = data.get('master_id')
    svc_id = data.get('service_id')
    from app.repo import list_masters, get_service
    from app.scheduler import generate_slots

    svc = await get_service(svc_id)
    if not svc:
        try:
            print('process_date returning: service not found', svc_id)
        except Exception:
            pass
        await message.answer('Ошибка: услуга не найдена')
        return

    if master_id == 0 or master_id is None:
        # show masters who have slots on that date
        masters = await list_masters()
        masters_with = []
        for m in masters:
            try:
                slots = await generate_slots(m['id'], date_s, svc['duration_minutes'])
            except Exception as e:
                try:
                    print('generate_slots error:', e)
                except Exception:
                    pass
                # skip this master on error
                continue
            if slots:
                masters_with.append((m, slots))
        if not masters_with:
            try:
                print('process_date returning: no masters_with slots')
            except Exception:
                pass
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text='Отправить ручную заявку админу', callback_data='manual:request:start'),
                InlineKeyboardButton(text='Отмена', callback_data='manual:request:cancel')
            ]])
            await message.answer('К сожалению, на этот день нет свободных слотов. Хотите отправить ручную заявку админу?', reply_markup=kb)
            return
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        rows = []
        for m, slots in masters_with:
            avg, cnt = await average_rating_for_master(m['id'])
            rating = format_rating(avg, cnt)
            label = f"{m['name']} ({len(slots)}), выбрать"
            if rating:
                label = f"{m['name']} {rating} ({len(slots)}), выбрать"
            # fixed callback_data quoting to avoid nested single-quote syntax error
            rows.append([InlineKeyboardButton(text=label, callback_data=f"book:master_choose:{m['id']}")])
        # Also show masters with zero slots as option for manual request
        all_masters = await list_masters()
        for m in all_masters:
            if not any(m2['id'] == m['id'] for m2, _ in masters_with):
                avg, cnt = await average_rating_for_master(m['id'])
                rating = format_rating(avg, cnt)
                label = f"{m['name']} (❌ занято) — запросить"
                if rating:
                    label = f"{m['name']} {rating} (❌ занято) — запросить"
                rows.append([InlineKeyboardButton(text=label, callback_data=f"manual:request:start:master:{m['id']}")])
        kb = InlineKeyboardMarkup(inline_keyboard=rows)
        await message.answer('Выберите мастера с доступным временем или отправьте запрос для занятых мастеров:', reply_markup=kb)
        try:
            print('process_date returning: showed masters list')
        except Exception:
            pass
        return

    # specific master flow
    # Validate that master works on the chosen weekday and inform the user if not
    try:
        if master_id and master_id != 0:
            import datetime as _dt
            weekday = _dt.date.fromisoformat(date_s).weekday()
            try:
                from app.scheduler import get_master_work_info
                days, start_time, end_time, _ = await get_master_work_info(master_id)
                if days is None:
                    days = []
                if weekday not in days:
                    # format days for message
                    rus = ['Пн','Вт','Ср','Чт','Пт','Сб','Вс']
                    def format_days(ds):
                        if not ds:
                            return ''
                        ds = sorted(ds)
                        ranges = []
                        start = prev = ds[0]
                        for d in ds[1:]:
                            if d == prev + 1:
                                prev = d
                                continue
                            if start == prev:
                                ranges.append(rus[start])
                            else:
                                ranges.append(f"{rus[start]}–{rus[prev]}")
                            start = prev = d
                        if start == prev:
                            ranges.append(rus[start])
                        else:
                            ranges.append(f"{rus[start]}–{rus[prev]}")
                        return ','.join(ranges)
                    days_str = format_days(days)
                    await message.answer(f'Этот мастер не работает в этот день недели. Доступные дни: {days_str}.')
                    return
            except Exception:
                pass
    except Exception:
        pass
    try:
        slots = await generate_slots(master_id, date_s, svc['duration_minutes'])
    except Exception as e:
        try:
            print('generate_slots error:', e)
        except Exception:
            pass
        await message.answer('Ошибка генерации слотов')
        try:
            print('process_date returning: generate_slots failed for specific master')
        except Exception:
            pass
        return
    if not slots:
        try:
            print('process_date returning: no slots for specific master', master_id)
        except Exception:
            pass
        await message.answer('К сожалению, у выбранного мастера нет слотов на этот день. Попробуйте другую дату или мастера.')
        return
    kb = create_time_keyboard(slots, 0)
    await state.update_data(slots=slots, current_page=0)
    await message.answer('Выберите время:', reply_markup=kb)
    await _set_state(state, BookingStates.TIME)

@router.callback_query(lambda q: q.data and (q.data.startswith('book:time:select:') or q.data.startswith('book:time:page:')))
async def cb_select_time(query: CallbackQuery, state: FSMContext):
    parts = query.data.split(':')
    if parts[2] == 'select':
        # book:time:select:11:00
        time_s = ':'.join(parts[3:])
        await state.update_data(time=time_s)
        await query.message.answer('👤 Введите ваше имя:')
        await _set_state(state, BookingStates.NAME)
        await query.answer("")
    elif parts[2] == 'page':
        # book:time:page:1
        page = int(parts[3])
        data = await state.get_data()
        slots = data.get('slots', [])
        kb = create_time_keyboard(slots, page)
        await state.update_data(current_page=page)
        await query.message.edit_reply_markup(reply_markup=kb)
        await query.answer("")

@router.message(StateFilter(BookingStates.TIME))
async def process_time(message: Message, state: FSMContext):
    time_s = message.text.strip()
    try:
        import datetime
        datetime.time.fromisoformat(time_s)
    except Exception:
        await message.answer('Неверный формат времени. Попробуйте HH:MM')
        return
    await state.update_data(time=time_s)
    await message.answer('Введите ваше имя:')
    await _set_state(state, BookingStates.NAME)

@router.message(StateFilter(BookingStates.NAME))
async def process_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer('Введите телефон (например, +37061234567):')
    await _set_state(state, BookingStates.PHONE)

@router.message(StateFilter(BookingStates.PHONE))
async def process_phone(message: Message, state: FSMContext):
    phone = message.text.strip()
    if not valid_phone(phone):
        await message.answer('Неверный формат телефона. Попробуйте +37061234567')
        return
    await state.update_data(phone=phone)
    data = await state.get_data()
    
    # Get service and master names
    service = await get_service(data['service_id'])
    service_name = service['name'] if service else 'Услуга'
    
    master_id = data['master_id'] if data['master_id'] != 0 else None
    master_name = 'без выбора'
    if master_id:
        master = await get_master(master_id)
        master_name = master['name'] if master else 'Мастер'
    
    # Build confirmation message with names, not IDs
    text = (
        f"Подтвердите запись:\n"
        f"Услуга: {service_name}\n"
        f"Мастер: {master_name}\n"
        f"Дата: {data['date']}\n"
        f"Время: {data['time']}\n"
        f"Имя: {data['name']}\n"
        f"Телефон: {data['phone']}"
    )
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text='✅ Подтвердить', callback_data='book:confirm'),
        InlineKeyboardButton(text='❌ Отмена', callback_data='book:cancel')
    ]])
    await message.answer(text, reply_markup=kb)
    await _set_state(state, BookingStates.CONFIRM)

@router.callback_query(lambda q: q.data == 'book:confirm')
async def cb_confirm(query: CallbackQuery, state: FSMContext):
    cur = await _get_state(state)
    if cur != BookingStates.CONFIRM.state:
        await query.answer("")
        return
    data = await state.get_data()
    user = await get_or_create_user(query.from_user.id, name=data.get('name'), phone=data.get('phone'))
    try:
        await create_booking(user['id'], data['service_id'], data['master_id'] if data['master_id'] != 0 else None, data['date'], data['time'], data['name'], data['phone'])
        # Получаем длительность услуги и id бронирования (поиск по данным)
        service = await get_service(data['service_id'])
        duration = service['duration_minutes'] if service and 'duration_minutes' in service else 30
        # Получаем id только что созданной записи (по уникальным данным)
        from app.repo import list_bookings
        bookings = await list_bookings()
        booking_id = None
        for b in bookings:
            if b['user_id'] == user['id'] and b['service_id'] == data['service_id'] and b['date'] == data['date'] and b['time'] == data['time']:
                booking_id = b['id']
                break
        if booking_id:
            schedule_auto_complete(booking_id, data['date'], data['time'], duration)
            try:
                schedule_reminders(booking_id, data['date'], data['time'])
            except Exception:
                pass
    except SlotTaken:
        await query.message.answer('😔 Извините, это время уже занято. Попробуйте выбрать другое.')
        await state.clear()
        await query.answer("")
        return
    except DoubleBooking:
        await query.message.answer('⚠️ У вас уже есть активная запись. Нельзя записаться второй раз.')
        await state.clear()
        await query.answer("")
        return
    # notify admins
    try:
        from app.notify import notify_admins
        from app.repo import format_booking_for_display
        # Create a minimal booking dict for formatting
        user = await get_or_create_user(query.from_user.id, name=data.get('name'), phone=data.get('phone'))
        booking_dict = {
            'user_id': user['id'],
            'service_id': data.get('service_id'),
            'master_id': data.get('master_id'),
            'date': data['date'],
            'time': data['time']
        }
        formatted = await format_booking_for_display(booking_dict)
        await notify_admins(formatted)
    except Exception:
        pass
    await query.message.answer('🎉 Запись подтверждена! Админ уведомлён. Ждём вас!')
    await state.clear()
    await query.answer()

@router.callback_query(lambda q: q.data == 'book:cancel')
async def cb_cancel(query: CallbackQuery, state: FSMContext):
    cur = await _get_state(state)
    if cur != BookingStates.CONFIRM.state:
        await query.answer("")
        return
    await query.message.answer('❌ Запись отменена.')
    await state.clear()
    await query.answer()


@router.message(Command('cancel_booking'))
async def cmd_user_cancel_booking(message: Message):
    """Allow user to cancel their own booking by id."""
    args = get_args(message)
    if not args:
        await message.answer('Использование: /cancel_booking booking_id')
        return
    try:
        bid = int(args.strip())
    except Exception:
        await message.answer('Неверный booking_id. Укажите число, например: 123')
        return
    b = await get_booking(bid)
    if not b or b['user_id'] != message.from_user.id:
        await message.answer('❌ Бронирование не найдено или вы не имеете прав для его отмены.')
        return
    await set_booking_status(bid, 'cancelled')
    # cancel any scheduled tasks
    try:
        cancel_auto_complete(bid)
    except Exception:
        pass
    try:
        cancel_reminders(bid)
    except Exception:
        pass
    await message.answer('✅ Ваша запись отменена.')
