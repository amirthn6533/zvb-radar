import json
import os
import sys
sys.stdout.reconfigure(encoding='utf-8')

import db_manager

def migrate():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_manager.init_db()
    
    # 1. Migrate leads.json
    leads_path = os.path.join(base_dir, "leads.json")
    leads_count = 0
    if os.path.exists(leads_path):
        try:
            with open(leads_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for k, v in data.items():
                if not v.get("id"):
                    v["id"] = k
                db_manager.save_lead(v)
                leads_count += 1
            print(f"✅ Migrated {leads_count} leads from leads.json")
        except Exception as e:
            print(f"❌ Error migrating leads: {e}")

    # 2. Migrate candidates.json
    cand_path = os.path.join(base_dir, "candidates.json")
    cand_count = 0
    if os.path.exists(cand_path):
        try:
            with open(cand_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for k, v in data.items():
                if not v.get("id"):
                    v["id"] = k
                db_manager.save_candidate(v)
                cand_count += 1
            print(f"✅ Migrated {cand_count} candidates from candidates.json")
        except Exception as e:
            print(f"❌ Error migrating candidates: {e}")

    # 3. Migrate alert_history.json
    alert_path = os.path.join(base_dir, "alert_history.json")
    alert_count = 0
    if os.path.exists(alert_path):
        try:
            with open(alert_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for k, v in data.items():
                if not v.get("id"):
                    v["id"] = k
                db_manager.mark_alerted(v)
                alert_count += 1
            print(f"✅ Migrated {alert_count} alerts from alert_history.json")
        except Exception as e:
            print(f"❌ Error migrating alert history: {e}")

    stats = db_manager.get_crm_stats()
    print("📊 Current Database Summary:", stats)

if __name__ == '__main__':
    migrate()
