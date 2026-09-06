import os
import json
import re
import datetime
import subprocess
import urllib.request
import urllib.parse

CANDIDATES_FILE = os.path.join(os.path.dirname(__file__), "candidates.json")

def load_candidates():
    if not os.path.exists(CANDIDATES_FILE):
        return {}
    try:
        with open(CANDIDATES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading candidates: {e}")
        return {}

def save_candidates(data):
    try:
        with open(CANDIDATES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        sync_git()
        return True
    except Exception as e:
        print(f"Error saving candidates: {e}")
        return False

def sync_git():
    """Sync candidates.json to GitHub repository so data persists across runs."""
    try:
        subprocess.run(["git", "config", "user.name", "Zagros Bot"], capture_output=True, check=False)
        subprocess.run(["git", "config", "user.email", "bot@zvb.bg"], capture_output=True, check=False)
        subprocess.run(["git", "add", "candidates.json"], capture_output=True, check=False)
        res = subprocess.run(["git", "commit", "-m", "chore: update candidates database [skip ci]"], capture_output=True, text=True, check=False)
        if "nothing to commit" not in res.stdout and "nothing to commit" not in res.stderr:
            subprocess.run(["git", "push"], capture_output=True, check=False)
    except Exception as e:
        print(f"Git sync error (non-fatal): {e}")

def parse_candidate_with_ai_or_regex(raw_text):
    """
    Parses unstructured text into candidate details: name, phone, skills, rate, notes.
    Uses Gemini AI with fast response, with regex fallback.
    """
    api_key = None
    cfg_path = os.path.join(os.path.dirname(__file__), "config.json")
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                api_key = json.load(f).get("gemini_api_key")
        except Exception:
            pass

    if api_key:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        prompt = f"""
You are a precise data extraction assistant for an electrical company in Sofia, Bulgaria.
The user provided details for a candidate electrician:
"{raw_text}"

Extract the information into valid JSON only (no markdown, no backticks, just pure JSON):
{{
  "name": "Full name or nickname",
  "phone": "Bulgarian phone formatted like 088... or +359...",
  "skills": "Key electrical skills (e.g., табла, окабеляване, монтаж, интелигентни системи)",
  "rate": "Hourly/daily rate or expected salary if mentioned, else empty string",
  "notes": "Vehicle, tools, city area, or personal impressions"
}}
"""
        req_data = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 300,
                "thinkingConfig": {"thinkingBudget": 0}
            }
        }
        try:
            req = urllib.request.Request(url, data=json.dumps(req_data).encode("utf-8"), headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=4) as response:
                result = json.loads(response.read().decode("utf-8"))
                text = result["candidates"][0]["content"]["parts"][0]["text"].strip()
                text = re.sub(r"^```json\s*", "", text)
                text = re.sub(r"^```\s*", "", text)
                text = re.sub(r"```$", "", text).strip()
                data = json.loads(text)
                if data.get("name") or data.get("phone"):
                    return data
        except Exception as e:
            print(f"Gemini candidate parse fallback: {e}")

    # Fallback: Regex extraction
    phone_match = re.search(r"(\+?359\s?[0-9\s]{7,12}|08[789][0-9\s]{7,10}|02\s?[0-9\s]{6,8})", raw_text)
    phone = phone_match.group(1).strip() if phone_match else ""
    clean_phone = re.sub(r"\s+", "", phone)

    # Clean text without phone
    rem_text = raw_text
    if phone:
        rem_text = rem_text.replace(phone, " ")

    parts = [p.strip() for p in re.split(r"[,،;\n|]+", rem_text) if p.strip()]
    name = parts[0] if parts else "برق‌کار کاندید"
    skills = parts[1] if len(parts) > 1 else "برق‌کاری و تأسیسات الکتریکی"
    notes = ", ".join(parts[2:]) if len(parts) > 2 else ""

    return {
        "name": name,
        "phone": clean_phone or phone,
        "skills": skills,
        "rate": "",
        "notes": notes
    }

def add_candidate(raw_text):
    """
    Parses and adds a new candidate to the database.
    """
    parsed = parse_candidate_with_ai_or_regex(raw_text)
    cand_id = f"c_{int(datetime.datetime.now().timestamp())}"
    
    candidates = load_candidates()
    cand_obj = {
        "id": cand_id,
        "name": parsed.get("name", "بی‌نام"),
        "phone": parsed.get("phone", ""),
        "skills": parsed.get("skills", ""),
        "rate": parsed.get("rate", ""),
        "notes": parsed.get("notes", ""),
        "added_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    candidates[cand_id] = cand_obj
    save_candidates(candidates)
    return cand_obj

def delete_candidate_by_query(query):
    """
    Finds and deletes candidate matching ID, name, or phone.
    Returns (success, deleted_name_or_msg).
    """
    candidates = load_candidates()
    clean_q = query.strip().lower()
    
    # Check exact ID first
    if clean_q in candidates:
        name = candidates[clean_q].get("name", clean_q)
        del candidates[clean_q]
        save_candidates(candidates)
        return True, name

    # Search by name or phone
    matched_id = None
    matched_name = None
    for cid, c in candidates.items():
        c_name = c.get("name", "").lower()
        c_phone = re.sub(r"\s+", "", c.get("phone", ""))
        if clean_q in c_name or (clean_q in c_phone and len(clean_q) >= 4):
            matched_id = cid
            matched_name = c.get("name")
            break
            
    if matched_id:
        del candidates[matched_id]
        save_candidates(candidates)
        return True, matched_name

    return False, "کاندیدی با این مشخصات یافت نشد."

def format_clean_phone_links(phone):
    """Generates formatted phone, viber, and whatsapp links."""
    clean = re.sub(r"[^\d+]", "", phone)
    if clean.startswith("08"):
        intl = "+359" + clean[1:]
    elif clean.startswith("359"):
        intl = "+" + clean
    elif clean.startswith("+359"):
        intl = clean
    else:
        intl = clean

    viber_link = f"viber://chat?number={intl}"
    wa_link = f"https://wa.me/{intl.lstrip('+')}"
    return intl, viber_link, wa_link

def get_candidate_list_view():
    """
    Returns (text_message, inline_keyboard_dict) representing the candidate CRM.
    """
    candidates = load_candidates()
    if not candidates:
        text = (
            "👥 <b>بانک کاندیداها و برق‌کارهای ZVB</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "📭 در حال حاضر هیچ کاندیدی در لیست ثبت نشده است.\n\n"
            "💡 <b>روش اضافه کردن برق‌کار جدید:</b>\n"
            "کافیست در گروه یا چت خصوصی بنویسید:\n"
            "<code>زاگرس اضافه کن: ایوان، 0888123456، مهارت تابلو و لوله‌گذاری، روزمزد ۱۲۰ لوا</code>\n"
            "یا\n"
            "<code>/add_cand Георги 0877998811, опит 5г, инсталации</code>"
        )
        buttons = [
            [{"text": "➕ راهنمای افزودن", "callback_data": "cmd_add_cand_help"}],
            [{"text": "🔙 بازگشت به منوی اصلی", "callback_data": "cmd_main_menu"}]
        ]
        return text, {"inline_keyboard": buttons}

    text = (
        f"👥 <b>بانک کاندیداها و برق‌کارهای ZVB ({len(candidates)} نفر)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    buttons = []
    for idx, (cid, c) in enumerate(candidates.items(), 1):
        name = c.get("name", "بی‌نام")
        phone = c.get("phone", "بدون شماره")
        skills = c.get("skills", "-")
        rate = c.get("rate", "")
        notes = c.get("notes", "")
        added = c.get("added_at", "")

        intl, viber_link, wa_link = format_clean_phone_links(phone) if phone else ("", "", "")

        text += f"<b>{idx}. {name}</b>\n"
        if phone:
            text += f"📞 شماره تماس: <code>{phone}</code>\n"
            text += f"💬 چت مستقیم: <a href='{viber_link}'>Viber</a> | <a href='{wa_link}'>WhatsApp</a>\n"
        if skills and skills != "-":
            text += f"⚡ مهارت‌ها: <i>{skills}</i>\n"
        if rate:
            text += f"💰 دستمزد پیشنهادی: <b>{rate}</b>\n"
        if notes:
            text += f"📝 یادداشت: <i>{notes}</i>\n"
        text += f"📅 ثبت: {added}\n"
        text += "────────────────────\n"

        # Add inline delete button for each candidate
        del_label = f"❌ حذف {name[:18]}"
        buttons.append([{"text": del_label, "callback_data": f"delcand_{cid}"}])

    buttons.append([{"text": "🔄 بروزرسانی لیست", "callback_data": "cmd_candidates"}])
    buttons.append([{"text": "🔙 منوی اصلی", "callback_data": "cmd_main_menu"}])

    return text, {"inline_keyboard": buttons}
