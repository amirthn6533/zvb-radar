import os
import pytest
import sqlite3
import hashlib
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db_manager

def test_db_init_and_tables(tmp_path):
    test_db = str(tmp_path / "test_zvb.db")
    db_manager.DB_PATH = test_db
    db_manager.init_db()
    
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    assert "leads" in tables
    assert "candidates" in tables
    assert "alert_history" in tables

def test_lead_lifecycle_and_status_update(tmp_path):
    test_db = str(tmp_path / "test_zvb.db")
    db_manager.DB_PATH = test_db
    db_manager.init_db()
    
    lead_data = {
        "id": "lead_12345",
        "title": "Smart Electrical Panel Installation",
        "url": "https://example.com/lead/12345",
        "source": "Bazar.bg",
        "keyword": "electrical",
        "category": "services",
        "category_label": "Electrical",
        "location": "Sofia, Lozenets",
        "phone": "+359888123456",
        "price": "1500 BGN",
        "value_tier": "HIGH_VALUE",
        "notes": "Urgent client project"
    }
    
    db_manager.save_lead(lead_data)
    
    lead = db_manager.get_lead("lead_12345")
    assert lead is not None
    assert lead["status"] == "NEW"
    assert lead["location"] == "Sofia, Lozenets"
    
    ok = db_manager.update_lead_status("lead_12345", "CONTACTED", notes="Client answered call, sending offer")
    assert ok is True
    lead = db_manager.get_lead("lead_12345")
    assert lead["status"] == "CONTACTED"
    
    ok = db_manager.update_lead_status("lead_12345", "WON", notes="Contract signed!")
    assert ok is True
    lead = db_manager.get_lead("lead_12345")
    assert lead["status"] == "WON"

def test_alert_deduplication(tmp_path):
    test_db = str(tmp_path / "test_zvb.db")
    db_manager.DB_PATH = test_db
    db_manager.init_db()
    
    url = "https://olx.bg/d/ad/elektrotehnik-sofia-123.html"
    url_hash = hashlib.sha256(url.encode('utf-8')).hexdigest()[:16]
    
    assert db_manager.is_alerted("ad_123", url_hash) is False
    
    db_manager.mark_alerted({
        "id": "ad_123",
        "title": "Elektrotehnik",
        "url": url,
        "url_hash": url_hash,
        "source": "OLX.bg"
    })
    
    assert db_manager.is_alerted("ad_123", url_hash) is True


def test_strict_bg_phone_validation():
    import lead_filter_engine
    # Reject empty phone
    ok, clean = lead_filter_engine.has_valid_bg_phone({"phone": "", "title": "Смяна на табло в София"})
    assert ok is False

    # Reject placeholder
    ok, clean = lead_filter_engine.has_valid_bg_phone({"phone": "Директен телефон в MaistorPlus", "title": "Ремонт"})
    assert ok is False

    # Reject non-Sofia landline (Varna 052)
    ok, clean = lead_filter_engine.has_valid_bg_phone({"phone": "052 612 345", "title": "Ремонт"})
    assert ok is False

    # Accept valid Bulgarian mobile
    ok, clean = lead_filter_engine.has_valid_bg_phone({"phone": "+359 888 123 456", "title": "Смяна на ел. табло София"})
    assert ok is True
    assert clean == "0888123456"

    # Accept valid Sofia landline (02)
    ok, clean = lead_filter_engine.has_valid_bg_phone({"phone": "02 987 65 43", "title": "Строителна фирма София"})
    assert ok is True
    assert clean == "029876543"


def test_four_stage_deduplication_and_tiers(tmp_path):
    import lead_filter_engine
    test_db = str(tmp_path / "test_dedup.db")
    db_manager.DB_PATH = test_db
    db_manager.init_db()

    history = {}
    lead1 = {
        "id": "alo_999111",
        "title": "Търся електротехник за цялостна ел. инсталация в кв. Лозенец, София",
        "url": "https://www.alo.bg/999111?utm_source=test",
        "source": "Alo.bg",
        "location": "гр. София, Лозенец",
        "phone": "0889 112 233",
        "found_at": "2026-11-13 12:00"
    }
    valid, reason, tier = lead_filter_engine.evaluate_lead(lead1, history, require_phone=True)
    assert valid is True
    assert tier in ("VIP_FULL_ELECTRICAL", "SMALL_FAST_REPAIR", "LARGE_TURNKEY_B2B")

    lead_filter_engine.record_alert_sent(lead1, history)

    # Duplicate by different ID/URL but same phone number
    lead_same_phone = {
        "id": "bazar_888222",
        "title": "Спешно търся майстор за осветление в Младост София",
        "url": "https://bazar.bg/obiava-888222",
        "source": "Bazar.bg",
        "location": "гр. София",
        "phone": "+359889112233",
        "found_at": "2026-11-13 12:05"
    }
    valid2, reason2, _ = lead_filter_engine.evaluate_lead(lead_same_phone, history, require_phone=True)
    assert valid2 is False
    assert "phone" in reason2.lower() or "duplicate" in reason2.lower()


def test_amir_pitch_generation():
    import lead_scraper
    b2b_lead = {
        "id": "ksb_123",
        "title": "[Строител до ключ / КСБ София] АРТЕКС ИНЖЕНЕРИНГ АД",
        "company_name": "АРТЕКС ИНЖЕНЕРИНГ АД",
        "category": "contractor",
        "value_tier": "LARGE_TURNKEY_B2B",
        "phone": "0888 111 222",
        "location": "гр. София"
    }
    pitch = lead_scraper.build_amir_pitch(b2b_lead)
    assert "Амир" in pitch
    assert "Загрос Витоша България" in pitch

