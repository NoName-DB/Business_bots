import asyncio
import importlib
import aiogram
from types import SimpleNamespace

# Patch decorator during import (same pattern as booking_date_flow)
_orig = getattr(aiogram.Router, 'message', None)
aiogram.Router.message = lambda *a, **k: (lambda f: f)
# ensure Text filter exists for decorator usage in handlers
import aiogram.filters as _f
_f.Text = lambda *a, **k: (lambda f: f)
# avoid TelegramEvent.register enforcement
try:
    import aiogram.dispatcher.event.telegram as _te
    _te.TelegramEvent.register = lambda *a, **k: None
except Exception:
    pass
booking_handlers = importlib.reload(importlib.import_module('app.handlers.booking'))
if _orig is not None:
    aiogram.Router.message = _orig


class FakeMessage:
    def __init__(self, user_id, chat_id, text=None):
        self.from_user = SimpleNamespace(id=user_id)
        self.chat = SimpleNamespace(id=chat_id)
        self.text = text
        self.replies = []
    async def answer(self, text, **kwargs):
        self.replies.append({'text': text, **kwargs})


# Helper to extract args like get_args_from_message does
from app.utils import get_args_from_message as get_args


def test_user_cancel_own_booking(temp_db):
    async def _run():
        from app.repo import create_service, create_master, get_or_create_user, create_booking, list_bookings, get_booking
        # create a service, master, user and booking
        user = await get_or_create_user(5555, 'Uowner', '+10000000001')
        sid = await create_service('Svc1', 'd', 12.0, 30)
        mid = await create_master('M1', 'bio', 'contact')
        await create_booking(user['id'], sid, mid, '2026-04-01', '14:00', user['name'], user['phone'])
        rows = await list_bookings()
        assert rows, 'expected at least one booking'
        bid = rows[0]['id']
        msg = FakeMessage(user['id'], user['id'], text=f'/cancel_booking {bid}')
        # call handler
        await booking_handlers.cmd_user_cancel_booking(msg)
        b = await get_booking(bid)
        assert b is not None and b['status'] == 'cancelled'
        assert any('отмен' in r['text'] for r in msg.replies)
    asyncio.run(_run())


def test_user_cannot_cancel_others_booking(temp_db):
    async def _run():
        from app.repo import create_service, create_master, get_or_create_user, create_booking, list_bookings, get_booking
        user1 = await get_or_create_user(6666, 'U1', '+10000000002')
        user2 = await get_or_create_user(7777, 'U2', '+10000000003')
        sid = await create_service('Svc2', 'd', 20.0, 45)
        mid = await create_master('M2', 'bio', 'cont')
        await create_booking(user1['id'], sid, mid, '2026-05-01', '15:00', user1['name'], user1['phone'])
        rows = await list_bookings()
        bid = rows[0]['id']
        msg = FakeMessage(user2['id'], user2['id'], text=f'/cancel_booking {bid}')
        await booking_handlers.cmd_user_cancel_booking(msg)
        b = await get_booking(bid)
        assert b is not None and b['status'] != 'cancelled'
        assert any('не найдено' in r['text'] or 'прав' in r['text'] for r in msg.replies)
    asyncio.run(_run())