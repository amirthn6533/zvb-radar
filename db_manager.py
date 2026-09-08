import sqlite3
import os
import json
import datetime
import sys
sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "zvb_radar.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    c = conn.cursor()
    
    # 1. Leads table
    c.execute('''
        CREATE TABLE IF NOT EXISTS leads (
            id TEXT PRIMARY KEY,
            title TEXT,
            url TEXT,
            source TEXT,
            keyword TEXT,
            category TEXT,
            category_label TEXT,
            location TEXT,
            phone TEXT,
            price TEXT,
            value_tier TEXT DEFAULT 'NORMAL',
            status TEXT DEFAULT 'NEW',
            reminder_date TEXT,
            notes TEXT,
            found_at TEXT,
            raw_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('CREATE INDEX IF NOT EXISTS idx_leads_status ON leads (status)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_leads_reminder ON leads (reminder_date)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_leads_source ON leads (source)')

    # 2. Candidates table
    c.execute('''
        CREATE TABLE IF NOT EXISTS candidates (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            phone TEXT,
            skills TEXT,
            rate TEXT,
            notes TEXT,
            status TEXT DEFAULT 'AVAILABLE',
            added_at TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('CREATE INDEX IF NOT EXISTS idx_candidates_status ON candidates (status)')

    # 3. Alert history table
    c.execute('''
        CREATE TABLE IF NOT EXISTS alert_history (
            id TEXT PRIMARY KEY,
            title TEXT,
            url TEXT,
            url_hash TEXT,
            source TEXT,
            location TEXT,
            alerted_at TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('CREATE INDEX IF NOT EXISTS idx_alerts_hash ON alert_history (url_hash)')
    
    conn.commit()
    
    # Auto-bootstrap from JSON if SQLite is freshly created
    c.execute("SELECT COUNT(*) FROM leads")
    if c.fetchone()[0] == 0:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        leads_path = os.path.join(base_dir, "leads.json")
        if os.path.exists(leads_path):
            try:
                with open(leads_path, "r", encoding="utf-8") as f:
                    for k, v in json.load(f).items():
                        if not v.get("id"): v["id"] = k
                        c.execute("INSERT OR IGNORE INTO leads (id, title, url, source, phone, price, location, value_tier, status, found_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                  (v.get("id"), v.get("title",""), v.get("url",""), v.get("source",""), v.get("phone",""), v.get("price",""), v.get("location",""), v.get("value_tier","NORMAL"), v.get("status","NEW"), v.get("found_at","")))
            except Exception:
                pass

        cand_path = os.path.join(base_dir, "candidates.json")
        if os.path.exists(cand_path):
            try:
                with open(cand_path, "r", encoding="utf-8") as f:
                    for k, v in json.load(f).items():
                        if not v.get("id"): v["id"] = k
                        c.execute("INSERT OR IGNORE INTO candidates (id, name, phone, skills, rate, notes, status, added_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                                  (v.get("id"), v.get("name",""), v.get("phone",""), v.get("skills",""), v.get("rate",""), v.get("notes",""), v.get("status","AVAILABLE"), v.get("added_at","")))
            except Exception:
                pass
        conn.commit()

    conn.close()

# --- Leads API ---
def save_lead(lead):
    if not lead or not lead.get("id"):
        return
    conn = get_connection()
    c = conn.cursor()
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    raw_str = json.dumps(lead, ensure_ascii=False)
    
    c.execute('''
        INSERT INTO leads (
            id, title, url, source, keyword, category, category_label,
            location, phone, price, value_tier, status, reminder_date, notes, found_at, raw_data, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            title=excluded.title,
            url=excluded.url,
            phone=COALESCE(NULLIF(excluded.phone, ''), leads.phone),
            price=COALESCE(NULLIF(excluded.price, ''), leads.price),
            raw_data=excluded.raw_data,
            updated_at=?
    ''', (
        lead.get("id"),
        lead.get("title", ""),
        lead.get("url", ""),
        lead.get("source", ""),
        lead.get("keyword", ""),
        lead.get("category", ""),
        lead.get("category_label", ""),
        lead.get("location", ""),
        lead.get("phone", ""),
        lead.get("price", ""),
        lead.get("value_tier", "NORMAL"),
        lead.get("status", "NEW"),
        lead.get("reminder_date", None),
        lead.get("notes", ""),
        lead.get("found_at", now_str),
        raw_str,
        now_str,
        now_str
    ))
    conn.commit()
    conn.close()

def save_leads_batch(leads_iterable):
    if not leads_iterable:
        return
    if isinstance(leads_iterable, dict):
        items = leads_iterable.values()
    else:
        items = leads_iterable
    for lead in items:
        save_lead(lead)

def get_lead(lead_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM leads WHERE id = ?", (lead_id,))
    row = c.fetchone()
    conn.close()
    if row:
        d = dict(row)
        if d.get("raw_data"):
            try:
                base = json.loads(d["raw_data"])
                base.update(d)
                return base
            except Exception:
                pass
        return d
    return None

def get_all_leads():
    """Returns dict of {lead_id: lead_dict} for backward compatibility."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM leads ORDER BY updated_at DESC")
    rows = c.fetchall()
    conn.close()
    result = {}
    for r in rows:
        d = dict(r)
        if d.get("raw_data"):
            try:
                parsed = json.loads(d["raw_data"])
                parsed.update(d)
                result[d["id"]] = parsed
                continue
            except Exception:
                pass
        result[d["id"]] = d
    return result

def update_lead_status(lead_id, status, reminder_date=None, notes=None):
    conn = get_connection()
    c = conn.cursor()
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    updates = ["status = ?", "updated_at = ?"]
    params = [status, now_str]
    
    if reminder_date is not None:
        updates.append("reminder_date = ?")
        params.append(reminder_date)
    if notes is not None:
        updates.append("notes = ?")
        params.append(notes)
    
    params.append(lead_id)
    c.execute(f"UPDATE leads SET {', '.join(updates)} WHERE id = ?", params)
    affected = c.rowcount
    conn.commit()
    conn.close()
    return affected > 0

def get_due_reminders(target_date=None):
    """Returns leads with reminder_date <= target_date (default today) and not won/lost."""
    if not target_date:
        target_date = datetime.date.today().strftime("%Y-%m-%d")
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        SELECT * FROM leads 
        WHERE reminder_date IS NOT NULL 
          AND reminder_date <= ? 
          AND status NOT IN ('WON', 'LOST', 'ARCHIVED')
        ORDER BY reminder_date ASC
    ''', (target_date,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

def get_crm_stats():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT status, COUNT(*) as count FROM leads GROUP BY status")
    counts = {r["status"]: r["count"] for r in c.fetchall()}
    
    c.execute("SELECT COUNT(*) FROM leads")
    total_leads = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM candidates WHERE status = 'AVAILABLE'")
    active_cand = c.fetchone()[0]
    
    conn.close()
    return {
        "total": total_leads,
        "new": counts.get("NEW", 0),
        "contacted": counts.get("CONTACTED", 0),
        "offer_sent": counts.get("OFFER_SENT", 0),
        "won": counts.get("WON", 0),
        "lost": counts.get("LOST", 0),
        "active_candidates": active_cand
    }

# --- Candidates API ---
def save_candidate(cand):
    if not cand or not cand.get("id"):
        return
    conn = get_connection()
    c = conn.cursor()
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute('''
        INSERT INTO candidates (id, name, phone, skills, rate, notes, status, added_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name=excluded.name,
            phone=excluded.phone,
            skills=excluded.skills,
            rate=excluded.rate,
            notes=excluded.notes,
            status=excluded.status
    ''', (
        cand.get("id"),
        cand.get("name", ""),
        cand.get("phone", ""),
        cand.get("skills", ""),
        cand.get("rate", ""),
        cand.get("notes", ""),
        cand.get("status", "AVAILABLE"),
        cand.get("added_at", now_str)
    ))
    conn.commit()
    conn.close()

def delete_candidate(cand_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM candidates WHERE id = ?", (cand_id,))
    affected = c.rowcount
    conn.commit()
    conn.close()
    return affected > 0

def get_all_candidates():
    """Returns dict of {cand_id: cand_dict} for backward compatibility."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM candidates ORDER BY created_at DESC")
    rows = c.fetchall()
    conn.close()
    return {r["id"]: dict(r) for r in rows}

# --- Alert History API ---
def is_alerted(lead_id, url_hash=None):
    conn = get_connection()
    c = conn.cursor()
    if url_hash:
        c.execute("SELECT 1 FROM alert_history WHERE id = ? OR url_hash = ?", (lead_id, url_hash))
    else:
        c.execute("SELECT 1 FROM alert_history WHERE id = ?", (lead_id,))
    row = c.fetchone()
    conn.close()
    return row is not None

def mark_alerted(lead):
    if not lead or not lead.get("id"):
        return
    conn = get_connection()
    c = conn.cursor()
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute('''
        INSERT OR IGNORE INTO alert_history (id, title, url, url_hash, source, location, alerted_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        lead.get("id"),
        lead.get("title", ""),
        lead.get("url", ""),
        lead.get("url_hash", ""),
        lead.get("source", ""),
        lead.get("location", ""),
        lead.get("alerted_at", now_str)
    ))
    conn.commit()
    conn.close()

def get_alert_history():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM alert_history")
    rows = c.fetchall()
    conn.close()
    return {r["id"]: dict(r) for r in rows}

if __name__ == '__main__':
    init_db()
    print("Database initialized successfully at", DB_PATH)

