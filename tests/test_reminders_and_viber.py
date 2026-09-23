import os
import sys
import datetime
import pytest

# Add parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import db_manager
import lead_scraper
import telegram_bot_service

def test_normalize_bg_phone():
    # Standard 08 mobile
    local, intl = lead_scraper.normalize_bg_phone("0888123456")
    assert local == "0888123456"
    assert intl == "359888123456"

    # +359 mobile
    local, intl = lead_scraper.normalize_bg_phone("+359 87 711 2233")
    assert local == "0877112233"
    assert intl == "359877112233"

    # 00359 mobile
    local, intl = lead_scraper.normalize_bg_phone("00359899445566")
    assert local == "0899445566"
    assert intl == "359899445566"

    # Empty or invalid
    assert lead_scraper.normalize_bg_phone("") == (None, None)
    assert lead_scraper.normalize_bg_phone(None) == (None, None)
    assert lead_scraper.normalize_bg_phone("12345") == (None, None)

def test_custom_reminders_crud():
    db_manager.init_db()
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    
    # 1. Add reminder
    rem_id = db_manager.add_custom_reminder(
        chat_id="123456",
        title="تماس با کارفرمای پروژه ملادوست",
        phone="0888123456",
        remind_at=f"{today_str} 09:00"
    )
    assert rem_id.startswith("rem_")

    # 2. Get today reminders
    today_list = db_manager.get_today_reminders(today_str)
    assert any(r["id"] == rem_id for r in today_list)

    # 3. Mark status
    ok = db_manager.mark_custom_reminder_status(rem_id, "DONE")
    assert ok is True

    # 4. Check not in pending today
    today_list_after = db_manager.get_today_reminders(today_str)
    assert not any(r["id"] == rem_id for r in today_list_after)

    # 5. Delete
    deleted = db_manager.delete_custom_reminder(rem_id)
    assert deleted is True

def test_parse_reminder_text():
    # Persian natural language
    ok, ack = telegram_bot_service.parse_reminder_text("یادآوری: فردا ساعت ۱۰ تماس با ایوان 0888123456", "123")
    assert ok is True
    assert "یادآوری با موفقیت" in ack
    assert "0888123456" in ack

    # Bulgarian
    ok_bg, ack_bg = telegram_bot_service.parse_reminder_text("/remind утре 11:30 обаждане на 0877998811", "123")
    assert ok_bg is True
    assert "0877998811" in ack_bg

def test_handle_reminders_cmd():
    msg, kbd = telegram_bot_service.handle_reminders_cmd()
    assert "یادآوری" in msg
    assert "inline_keyboard" in kbd
