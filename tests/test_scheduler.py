import pytest
from datetime import date, timedelta
from app.repo import create_master, create_service
from app.scheduler import set_schedule, generate_slots, add_exception


def test_generate_slots_and_exception(temp_db):
    async def _run():
        mid = await create_master('Sched Master')
        sid = await create_service('Short', 'desc', 10.0, 30)
        wd = date.today().weekday()
        await set_schedule(mid, wd, '09:00', '11:00', 30)
        # Find next date with same weekday, at least tomorrow
        d = date.today() + timedelta(days=7)  # Next week same day
        d = d.isoformat()
        slots = await generate_slots(mid, d, 30)
        assert '09:00' in slots
        assert '09:30' in slots
        await add_exception(mid, d, available=0)
        slots2 = await generate_slots(mid, d, 30)
        assert slots2 == []
    __import__('asyncio').run(_run())
