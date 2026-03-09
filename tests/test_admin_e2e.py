import asyncio
import os
from types import SimpleNamespace

from app.repo import create_master, get_master, update_master, delete_master, create_service, get_service, get_or_create_user, create_booking

# Patch aiogram Router.message decorator to be a no-op during import to avoid framework-specific registration errors in tests
import aiogram
_orig_router_message = getattr(aiogram.Router, 'message', None)
aiogram.Router.message = lambda *args, **kwargs: (lambda f: f)
import importlib
admin_handlers = importlib.reload(importlib.import_module('app.handlers.admin'))
# restore
if _orig_router_message is not None:
    aiogram.Router.message = _orig_router_message

ADMIN_ID = 123456789
admin_handlers.ADMIN_IDS = [ADMIN_ID]

class FakeBot:
    def __init__(self):
        self.sent = []

    async def send_document(self, chat_id, document, filename=None, caption=None, disable_notification=False):
        # Accept BytesIO-like direct objects
        data = None
        try:
            document.seek(0)
            data = document.read()
        except Exception:
            # try InputFile wrapping
            try:
                if hasattr(document, 'get_file'):
                    f = document.get_file()
                    f.file.seek(0)
                    data = f.file.read()
            except Exception:
                data = None
        self.sent.append({'chat_id': chat_id, 'filename': filename, 'caption': caption, 'data': data})

class FakeMessage:
    def __init__(self, user_id, chat_id, args=''):
        self.from_user = SimpleNamespace(id=user_id)
        self.chat = SimpleNamespace(id=chat_id)
        self._args = args
        self.bot = FakeBot()
        self.replies = []

    def get_args(self):
        return self._args

    async def answer(self, text, **kwargs):
        # store text and kwargs (reply_markup etc.) for inspection in tests
        item = {'text': text}
        item.update(kwargs)
        self.replies.append(item)


def test_admin_edit_entity(temp_db):
    async def _run():
        admin_handlers.ADMIN_IDS = [ADMIN_ID]
        mid = await create_master('OldName', 'bio', 'contact')
        msg = FakeMessage(ADMIN_ID, ADMIN_ID, args=f'{mid}|NewName|newbio|newcontact')
        await admin_handlers.cmd_edit_master(msg)
        m = await get_master(mid)
        assert m['name'] == 'NewName'
        assert 'Мастер обновлён' in msg.replies[-1]['text']
    __import__('asyncio').run(_run())


def test_admin_delete_entity(temp_db):
    async def _run():
        admin_handlers.ADMIN_IDS = [ADMIN_ID]
        mid = await create_master('ToDelete', 'b', 'c')
        msg = FakeMessage(ADMIN_ID, ADMIN_ID, args=str(mid))
        await admin_handlers.cmd_delete_master(msg)
        # should prompt confirmation
        rm = msg.replies[-1]
        assert 'Вы уверены' in rm['text']
        kb = rm.get('reply_markup')
        assert kb is not None
        # Derive cbdata deterministically to avoid relying on reply_markup structure
        cbdata = f'confirm_delete_master:{mid}'
        # simulate confirmation
        class CBMessage:
            def __init__(self, chat, bot):
                self.chat = chat
                self.bot = bot
                self.edited = None
            async def edit_text(self, text):
                self.edited = text
            async def answer(self, text):
                self.edited = text
        cb_msg = CBMessage(SimpleNamespace(id=ADMIN_ID), msg.bot)
        class CB:
            def __init__(self, data, user_id, message):
                self.data = data
                self.from_user = SimpleNamespace(id=user_id)
                self.message = message
                self.answered = None
            async def answer(self, text, show_alert=False):
                self.answered = {'text': text, 'show_alert': show_alert}
        cb = CB(cbdata, ADMIN_ID, cb_msg)
        await admin_handlers.cb_confirm_delete_master(cb)
        m = await get_master(mid)
        assert m is None
        assert cb.answered is not None
    __import__('asyncio').run(_run())


def test_admin_export_sends_csv(temp_db):
    async def _run():
        admin_handlers.ADMIN_IDS = [ADMIN_ID]
        mid = await create_master('Exporter', 'bio', 'contact')
        sid = await create_service('S', 'desc', 5.0, 10)
        user = await get_or_create_user(999000999, 'U', '+37060000000')
        d = '2026-01-01'
        t = '09:00'
        await create_booking(user['id'], sid, mid, d, t, user['name'], user['phone'])
        msg = FakeMessage(ADMIN_ID, ADMIN_ID, args='')
        # call export handler
        await admin_handlers.cmd_export_bookings(msg)
        # ensure bot sent document
        assert len(msg.bot.sent) == 1
        sent = msg.bot.sent[0]
        assert sent['data'] is not None
        text = sent['data'].decode('utf-8') if isinstance(sent['data'], (bytes, bytearray)) else str(sent['data'])
        assert 'date' in text and 'service_id' in text
    __import__('asyncio').run(_run())


def test_admin_cancel_booking(temp_db):
    async def _run():
        admin_handlers.ADMIN_IDS = [ADMIN_ID]
        mid = await create_master('Canceller', 'bio', 'contact')
        sid = await create_service('S2', 'desc', 7.0, 15)
        user = await get_or_create_user(123123123, 'U2', '+37060001122')
        # create a booking and determine its id
        await create_booking(user['id'], sid, mid, '2026-02-02', '10:00', user['name'], user['phone'])
        from app.repo import list_bookings
        rows = await list_bookings()
        assert rows, 'expected booking created'
        bid = rows[0]['id']
        msg = FakeMessage(ADMIN_ID, ADMIN_ID, args=str(bid))
        await admin_handlers.cmd_cancel_booking(msg)
        from app.repo import get_booking
        b = await get_booking(bid)
        assert b is not None and b['status'] == 'cancelled'
        assert 'отмен' in msg.replies[-1]['text']
    __import__('asyncio').run(_run())
