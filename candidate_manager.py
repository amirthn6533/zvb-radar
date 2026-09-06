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

def parse_candidates_batch(raw_text):
    """
    Parses single or multiple candidate electricians from text.
    Handles multi-line lists, comma-separated lists, or unstructured blocks.
    Returns list of candidate dicts: [{name, phone, skills, rate, notes}, ...]
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
You are an intelligent HR and contacts extraction assistant for an electrical contracting firm in Sofia, Bulgaria.
The user provided contact information for one or MORE electrician candidates (may be 1 person or a multi-line list of several people):
\"\"\"{raw_text}\"\"\"

Extract EVERY individual person into a JSON array of objects.
Output ONLY valid JSON (no markdown formatting, no backticks, just pure JSON):
[
  {{
    "name": "Full name or nickname",
    "phone": "Bulgarian phone number (e.g., 0886460397 or +359...)",
    "skills": "Key skills or status (e.g., табла, инсталации, تماس نگرفته)",
    "rate": "Expected rate if mentioned, else empty string",
    "notes": "Any other notes"
  }}
]
"""
        req_data = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 600,
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
                if isinstance(data, list) and len(data) > 0:
                    return data
                elif isinstance(data, dict):
                    return [data]
        except Exception as e:
            print(f"Gemini batch candidate parse fallback: {e}")

    # Fallback: Line-by-line / Regex extraction
    candidates_list = []
    lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
    
    # If single line but has multiple Bulgarian numbers
    if len(lines) == 1:
        phones = re.findall(r"(?:08[789]\d{7}|\+?359\d{8,9})", re.sub(r"[\s\-]", "", raw_text))
        if len(phones) > 1:
            # Split by commas or semicolons
            chunks = [c.strip() for c in re.split(r"[,;]+", raw_text) if c.strip()]
            if len(chunks) >= len(phones):
                lines = chunks

    for line in lines:
        phone_match = re.search(r"(\+?359\s?[0-9\s]{7,12}|08[789][0-9\s]{7,10}|02\s?[0-9\s]{6,8})", line)
        phone = phone_match.group(1).strip() if phone_match else ""
        clean_phone = re.sub(r"\s+", "", phone)

        rem_text = line
        if phone:
            rem_text = rem_text.replace(phone, " ")

        parts = [p.strip() for p in re.split(r"[,،;\n|]+", rem_text) if p.strip()]
        name = parts[0] if parts else "برق‌کار کاندید"
        skills = parts[1] if len(parts) > 1 else ""
        notes = ", ".join(parts[2:]) if len(parts) > 2 else ""

        if name or clean_phone:
            candidates_list.append({
                "name": name,
                "phone": clean_phone or phone,
                "skills": skills,
                "rate": "",
                "notes": notes
            })

    return candidates_list if candidates_list else [{
        "name": "کاندید جدید",
        "phone": "",
        "skills": raw_text,
        "rate": "",
        "notes": ""
    }]

def add_candidates_from_text(raw_text):
    """
    Parses and adds one or multiple candidates.
    Returns list of created candidate objects.
    """
    parsed_list = parse_candidates_batch(raw_text)
    candidates = load_candidates()
    created = []

    now_ts = int(datetime.datetime.now().timestamp())
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    for i, p in enumerate(parsed_list):
        cand_id = f"c_{now_ts}_{i}"
        cand_obj = {
            "id": cand_id,
            "name": p.get("name", "بی‌نام"),
            "phone": p.get("phone", ""),
            "skills": p.get("skills", ""),
            "rate": p.get("rate", ""),
            "notes": p.get("notes", ""),
            "added_at": now_str
        }
        candidates[cand_id] = cand_obj
        created.append(cand_obj)

    save_candidates(candidates)
    return created

def add_candidate(raw_text):
    """Backward-compatible helper returning the first or combined added candidate."""
    added = add_candidates_from_text(raw_text)
    return added[0] if added else {}

def delete_candidate_by_query(query):
    """
    Finds and deletes candidate matching ID, name, or phone.
    Returns (success, deleted_name_or_msg).
    """
    candidates = load_candidates()
    clean_q = query.strip().lower()
    clean_q = clean_q.lstrip(":, ")
    
    # Check exact ID first
    if clean_q in candidates:
        name = candidates[clean_q].get("name", clean_q)
        del candidates[clean_q]
        save_candidates(candidates)
        return True, name

    # Normalize search query (strip spaces for phone check)
    q_digits = re.sub(r"[^\d]", "", clean_q)

    matched_id = None
    matched_name = None
    for cid, c in candidates.items():
        c_name = c.get("name", "").lower()
        c_phone = re.sub(r"[^\d]", "", c.get("phone", ""))
        
        # Check name match
        if clean_q in c_name or c_name in clean_q:
            matched_id = cid
            matched_name = c.get("name")
            break
        
        # Check phone match
        if q_digits and len(q_digits) >= 6 and (q_digits in c_phone or c_phone in q_digits):
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
            "کافیست در گروه یا چت خصوصی نام، شماره و توضیحات فرد (حتی لیست چند نفره) را بفرستید:\n"
            "<code>اضافه کن:\n"
            "بهزاد اسیبانپور 0886460397\n"
            "امیر فرمانی 0878608254\n"
            "داوود اسماعیلی 0886293352</code>"
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
        skills = c.get("skills", "")
        rate = c.get("rate", "")
        notes = c.get("notes", "")
        added = c.get("added_at", "")

        intl, viber_link, wa_link = format_clean_phone_links(phone) if phone else ("", "", "")

        text += f"<b>{idx}. {name}</b>\n"
        if phone:
            text += f"📞 شماره تماس: <code>{phone}</code>\n"
            text += f"💬 چت مستقیم: <a href='{viber_link}'>Viber</a> | <a href='{wa_link}'>WhatsApp</a>\n"
        if skills:
            text += f"⚡ وضعیت/مهارت: <i>{skills}</i>\n"
        if rate:
            text += f"💰 دستمزد: <b>{rate}</b>\n"
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
