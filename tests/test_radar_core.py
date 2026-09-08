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
