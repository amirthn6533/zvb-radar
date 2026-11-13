# -*- coding: utf-8 -*-
"""
ZVB 8-Layer Enterprise Lead Filter & Zero-Duplicate Engine v3.0
Representative: Амир (Amir) | Company: „Загрос Витоша България“ ЕООД (ZVB)

Guarantees:
1. Strict Phone Verification (No valid Bulgarian phone = No Telegram alert)
2. 4-Stage Deduplication (Exact ID + Canonical URL Hash + Phone Number + Fuzzy Title Similarity >= 78%)
3. Strict Time Window & Closed/Expired Status Rejection (Blocks stale ads > 3 days old)
4. Strict Sofia & Surroundings Geo-Fencing
5. Dual-Tier Project Classification (Small/Fast-Cash Projects vs. Large/Turnkey B2B Construction Projects)
6. Atomic Git + SQLite History Synchronization across GitHub Actions runs
"""

import os
import json
import re
import datetime
import difflib
import hashlib
import subprocess

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_FILE = os.path.join(DATA_DIR, "alert_history.json")
LEADS_FILE = os.path.join(DATA_DIR, "leads.json")

# 1. Stale / Closed Status Indicators (Bulgarian)
CLOSED_STATUS_KEYWORDS = [
    "приключен", "приключила", "изтекъл", "изтекла", "избран изпълнител",
    "затворен", "затворена", "неактивен", "неактивна", "архивиран", "спряна",
    "намерен майстор", "не приема оферти", "заето", "кандидатствали: 5/5",
    "достигнат е максималният брой позволени кандидати",
    "максималният брой позволени кандидати",
    "преди 30+ дни", "преди 29 дни", "преди 28 дни", "преди 27 дни",
    "преди 26 дни", "преди 25 дни", "преди 24 дни", "преди 23 дни",
    "преди 22 дни", "преди 21 дни", "преди 20 дни", "преди 19 дни",
    "преди 18 дни", "преди 17 дни", "преди 16 дни", "преди 15 дни",
    "преди 14 дни", "преди 13 дни", "преди 12 дни", "преди 11 дни",
    "преди 10 дни", "преди 9 дни", "преди 8 дни", "преди 7 дни",
    "от 1 до 3 месец", "от 3 до 6 месец"
]

# Non-electrical / Irrelevant job exclusions
NON_ELECTRICAL_EXCLUSIONS = [
    "ремонт на хладилник", "ремонт на пералня", "ремонт на съдомиялна",
    "метален парапет", "металел парапет", "решетка за балкон",
    "претапициране", "шофьор на автобус", "камериер", "сервитьор",
    "готвач", "чистач", "курс ", "курсове ", "дистанционно обучение",
    "елвис пресли", "квалификационни курсове", "търся работа като",
    "желана длъжност", "bmw ", "mercedes", "audi ", "volkswagen", "peugeot",
    "citroen", "renault", "puretech", "crossback", "tdi", "xdrive", "quattro",
    "скоростна кутия", "автомобил", "хидростроителство", "хидротехнически"
]

REQUIRED_RELEVANCE_STEMS = [
    "електро", "ел.", "ел ", "табло", "табла", "кабел", "окабеляване", "инсталац",
    "осветл", "лед", "led", "камер", "видеонаблюд", "домофон", "слаботок",
    "силноток", "строител", "строеж", "сград", "ремонт", "довършител", "подизпълнит",
    "бригад", "майстор", "технически ръководител", "инженер", "солар", "фотоволтаи",
    "контакт", "бойлер", "апартамент", "къща", "къщи", "вила", "офис", "овк", "климати"
]

# 2. Sofia & Immediate Surroundings (Strict Regional Filter)
SOFIA_CORE_REGIONS = [
    "софия", "sofia", "младост", "люлин", "лозенец", "витоша", "бояна", "драгалевци",
    "симеоново", "манастирски ливади", "кръстова вада", "надежда", "център", "овча купел",
    "гео милев", "изток", "дианабад", "белите брези", "стрелбище", "красно село",
    "хиподрума", "банишора", "хаджи димитър", "дружба", "редута", "илинден",
    "красна поляна", "павлово", "банкя", "обеля", "света троица", "разсадника",
    "борово", "гоце делчев", "слатина", "славия", "връбница", "горна баня",
    "княжево", "бистрица", "панчарево", "герман", "нови искър", "софия-град",
    "костинброд", "божурище", "елин пелин", "волуяк", "владая", "казичене", "кривина",
    "полигона", "изгрев", "оборище", "сердика", "триадица", "студентски град", "малинова долина"
]

# Cities that are STRICTLY rejected unless Sofia is also explicitly specified
OTHER_BULGARIAN_CITIES = [
    "бургас", "варна", "пловдив", "русе", "стара загора", "плевен", "търговище",
    "видин", "разград", "свищов", "пазарджик", "кърджали", "велико търново",
    "перник", "благоевград", "шумен", "сливен", "хасково", "враца", "габрово",
    "пещера", "дупница", "сандански", "асеновград", "казанлък", "червен бряг",
    "несебър", "слънчев бряг", "кюстендил", "ботевград", "мездра", "разлог", "банско",
    "велинград", "смолян", "ямбол", "добрич", "силистра", "ловеч", "монтана"
]

# 3. Project Size & Category Markers
LARGE_TURNKEY_B2B_KEYWORDS = [
    "строителна фирма", "строителна компания", "главен изпълнител", "подизпълнител",
    "подизпълнители", "бригада", "жилищна сграда", "жилищни сгради", "жилищен комплекс",
    "затворен комплекс", "ново строителство", "груб строеж", "строеж на къща",
    "строителство на къщи", "до ключ", "инвеститор", "технически ръководител",
    "строителен надзор", "инженеринг", "промишлено строителство", "хале", "складова база",
    "хотел", "административна сграда", "кооперация", "цпрс", "ксб", "овк"
]

VIP_COMMERCIAL_VILLA_KEYWORDS = [
    "сграда", "сгради", "комплекс", "търговски", "офис", "офиси", "къща", "къщи", "вила", "вили",
    "ресторант", "заведение", "склад", "хале", "ново строителство", "груб строеж", "хотел",
    "кооперация", "мезонет", "инвеститор", "жилищен комплекс", "затворен комплекс", "промишлен"
]

VIP_CCTV_SECURITY_NET_KEYWORDS = [
    "видеонаблюдение", "охранителни камери", "камери", "cctv", "сот", "охрана", "контрол на достъп",
    "контрол на достъпа", "двр", "dvr", "nvr", "пое", "poe", "ит мрежа", "компютърна мрежа",
    "лан мрежа", "сървър", "сървърен", "слаботокова", "видеодомофон", "домофонна система",
    "домофон", "пожароизвестяване", "солар", "фотоволтаич", "парково осветление"
]

VIP_FULL_ELECTRICAL_KEYWORDS = [
    "цялостно окабеляване", "нова инсталация", "смяна на инсталация", "подмяна на инсталация",
    "инсталация на цял", "инсталация на цяло", "трифазно табло", "главно табло", "електромерно табло",
    "смяна на табло", "ново табло", "ремонт на табло", "силнотокова", "трифазен", "дефектнотокова",
    "заземяване", "ремонт на цяла инсталация", "пълно окабеляване", "ново ел табло", "ел. инсталация"
]

SMALL_FAST_REPAIR_KEYWORDS = [
    "контакт", "контакти", "ключ", "осветление", "лампа", "лунички", "полилей", "лед",
    "бойлер", "печка", "котлон", "аспиратор", "вентилатор", "предпазител", "бушон",
    "прекъсна", "късо съединение", "авария", "дребни ремонти", "частичен ремонт", "кабел"
]

HIGH_VALUE_INDICATORS = list(set(
    LARGE_TURNKEY_B2B_KEYWORDS
    + VIP_COMMERCIAL_VILLA_KEYWORDS
    + VIP_CCTV_SECURITY_NET_KEYWORDS
    + VIP_FULL_ELECTRICAL_KEYWORDS
))

BLACKLISTED_PHONES = {
    "0879590810", "359879590810", "+359879590810",
    "029699173", "02/9699173", "070012345"
}


def normalize_bg_phone(raw_phone):
    """Returns (local_display, intl_digits) e.g. ('0888 123 456', '359888123456')"""
    if not raw_phone:
        return None, None
    digits = re.sub(r'\D', '', str(raw_phone))
    if digits.startswith('00359'):
        digits = digits[2:]
    elif digits.startswith('0') and len(digits) in (9, 10):
        digits = '359' + digits[1:]
    elif not digits.startswith('359') and len(digits) == 9 and digits[0] in '89':
        digits = '359' + digits

    if digits.startswith('359') and len(digits) in (11, 12):
        local = '0' + digits[3:]
        if len(local) == 10 and local.startswith(('087', '088', '089', '098')):
            local_fmt = f"{local[:4]} {local[4:7]} {local[7:]}"
        elif len(local) == 9 and local.startswith('02'):
            local_fmt = f"02 {local[2:5]} {local[5:7]} {local[7:]}"
        else:
            local_fmt = local
        return local_fmt, digits
    return None, None


def has_valid_bg_phone(lead):
    """
    Strictly verifies that the lead has a real, dialable Bulgarian phone number
    (mobile 087/088/089/098 or Sofia landline 02).
    Rejects empty strings, placeholders ('Директен телефон в MaistorPlus', '08XX XXX XXX'),
    or non-Sofian area codes (like 052 Varna, 056 Burgas, 032 Plovdiv).
    """
    raw_phone = str(lead.get("phone", "") or "").strip()
    if not raw_phone:
        return False, "Missing phone number"

    low = raw_phone.lower()
    if "xx" in low or "maistorplus" in low or "daibau" in low or "в обявата" in low:
        return False, f"Placeholder phone text ('{raw_phone}')"

    digits = re.sub(r"\D", "", raw_phone)
    if not digits or len(digits) < 7:
        return False, f"Invalid phone digits ('{raw_phone}')"

    if digits in BLACKLISTED_PHONES or raw_phone in BLACKLISTED_PHONES:
        return False, "Blacklisted platform support phone"

    # Normalize 359 prefix to 0
    if digits.startswith("359") and len(digits) >= 11:
        digits = "0" + digits[3:]
    elif digits.startswith("00359") and len(digits) >= 13:
        digits = "0" + digits[5:]

    # Reject non-Sofia landline area codes (032 Plovdiv, 052 Varna, 056 Burgas, 062 V. Tarnovo, etc.)
    non_sofia_prefixes = ("032", "034", "042", "052", "056", "058", "062", "064", "068", "073", "082", "084", "086", "092", "094", "096")
    if digits.startswith(non_sofia_prefixes):
        return False, f"Non-Sofia landline area code ({digits[:3]})"

    # Valid Bulgarian mobile (087, 088, 089, 098) -> 10 digits
    if re.match(r"^0(8[789]\d{7}|98\d{7})$", digits):
        return True, digits

    # Valid Sofia landline (02 + 7 digits) -> 9 digits
    if re.match(r"^02\d{7}$", digits):
        return True, digits

    # Valid national 0700 number
    if re.match(r"^0700\d{5}$", digits):
        return True, digits

    return False, f"Unrecognized phone format ('{raw_phone}')"


def load_alert_history():
    history = {}
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    history.update(data)
        except Exception as e:
            print(f"Error loading alert history JSON: {e}")

    try:
        import db_manager
        db_history = db_manager.get_alert_history()
        if db_history and isinstance(db_history, dict):
            history.update(db_history)
    except Exception:
        pass

    return history


def save_alert_history(history):
    try:
        import db_manager
        for k, v in history.items():
            if isinstance(v, dict):
                if not v.get("id"):
                    v["id"] = k
                db_manager.mark_alerted(v)
    except Exception as e:
        print(f"DB save alert history error: {e}")
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Error saving alert history: {e}")
        return False


def sync_git_history():
    """
    Syncs BOTH alert_history.json and leads.json to the git repository
    so GitHub Actions runners never reset leads.json or resend old items.
    """
    try:
        subprocess.run(["git", "config", "user.name", "Zagros Bot"], cwd=DATA_DIR, capture_output=True, check=False)
        subprocess.run(["git", "config", "user.email", "bot@zvb.bg"], cwd=DATA_DIR, capture_output=True, check=False)
        subprocess.run(["git", "add", "alert_history.json", "leads.json"], cwd=DATA_DIR, capture_output=True, check=False)
        res = subprocess.run(
            ["git", "commit", "-m", "chore: sync alert history and leads [skip ci]"],
            cwd=DATA_DIR, capture_output=True, text=True, check=False
        )
        if "nothing to commit" not in (res.stdout or "") and "nothing to commit" not in (res.stderr or ""):
            subprocess.run(["git", "pull", "--rebase", "origin", "main"], cwd=DATA_DIR, capture_output=True, check=False)
            subprocess.run(["git", "push", "origin", "main"], cwd=DATA_DIR, capture_output=True, check=False)
    except Exception:
        pass


def normalize_text_for_comparison(text):
    """Normalizes title and description for fuzzy deduplication."""
    t = str(text or "").lower()
    t = re.sub(r"\[.*?\]", " ", t)
    t = re.sub(r"[^\w\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def calculate_similarity(text1, text2):
    """Calculates SequenceMatcher ratio between two normalized project texts."""
    norm1 = normalize_text_for_comparison(text1)
    norm2 = normalize_text_for_comparison(text2)
    if not norm1 or not norm2:
        return 0.0
    return difflib.SequenceMatcher(None, norm1, norm2).ratio()


def is_duplicate_or_similar(lead, history):
    """
    4-Stage Deduplication:
    Stage 1: Exact ID check (JSON + SQLite)
    Stage 2: Canonical URL hash check
    Stage 3: Normalized Phone + Category/Source check
    Stage 4: Fuzzy text similarity (>= 78% similarity with any previously alerted lead)
    """
    lead_id = str(lead.get("id", "")).strip()
    lead_url = str(lead.get("url", "")).split("?")[0].split("#")[0].strip()
    lead_title = str(lead.get("title", "")).strip()
    url_hash = hashlib.md5(lead_url.encode("utf-8")).hexdigest() if lead_url else ""

    valid_p, norm_phone = has_valid_bg_phone(lead)
    lead_phone_digits = norm_phone if valid_p else ""

    # Check SQLite DB first
    try:
        import db_manager
        if db_manager.is_alerted(lead_id, url_hash):
            return True, f"Duplicate in SQLite DB ({lead_id})"
    except Exception:
        pass

    # Stage 1: Exact ID
    if lead_id and lead_id in history:
        return True, f"Exact ID duplicate ({lead_id})"

    for hist_id, hist_item in history.items():
        if not isinstance(hist_item, dict):
            continue

        # Stage 2: URL hash or exact URL
        hist_url = str(hist_item.get("url", "")).split("?")[0].split("#")[0].strip()
        if (url_hash and hist_item.get("url_hash") == url_hash) or (lead_url and hist_url == lead_url):
            return True, f"URL hash duplicate with {hist_id}"

        # Stage 3: Same phone number already alerted
        hist_phone = re.sub(r"\D", "", str(hist_item.get("phone", "")))
        if hist_phone.startswith("359") and len(hist_phone) >= 11:
            hist_phone = "0" + hist_phone[3:]
        if lead_phone_digits and hist_phone and lead_phone_digits == hist_phone:
            return True, f"Phone duplicate ({lead_phone_digits}) already sent in {hist_id}"

        # Stage 4: Fuzzy Title Similarity (>= 78%)
        hist_title = hist_item.get("title", "")
        if lead_title and hist_title:
            sim = calculate_similarity(lead_title, hist_title)
            if sim >= 0.78:
                return True, f"Fuzzy duplicate ({int(sim * 100)}% similar to {hist_id})"

    return False, "Unique lead"


def is_project_closed_or_expired(lead):
    """Checks if the project has closed/expired status or non-electrical exclusions."""
    title = str(lead.get("title", "")).lower()
    desc = str(lead.get("description", "")).lower()
    status = str(lead.get("status_text", "")).lower()
    combined = f"{title} {desc} {status}"

    for kw in CLOSED_STATUS_KEYWORDS:
        if kw in combined:
            return True, f"Project closed or stale ('{kw}')"

    for ex in NON_ELECTRICAL_EXCLUSIONS:
        if ex in combined:
            return True, f"Non-electrical / excluded topic ('{ex}')"

    if not any(stem in combined for stem in REQUIRED_RELEVANCE_STEMS):
        return True, "Irrelevant topic (missing electrical/construction stem in title/description)"

    return False, "Active"


def is_within_time_window(lead, max_days=3):
    """
    Ensures the lead was discovered or published within the last `max_days` days.
    Blocks old September/October leads that previously stayed in leads.json for a month.
    """
    date_str = lead.get("published_at") or lead.get("found_at") or lead.get("date")
    if not date_str:
        return True, "Recent (current scan)"

    now = datetime.datetime.now()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%d.%m.%Y"):
        try:
            dt = datetime.datetime.strptime(str(date_str).strip(), fmt)
            age_days = (now - dt).total_seconds() / 86400.0
            if age_days > max_days:
                return False, f"Stale lead ({int(age_days)} days old > max {max_days}d)"
            return True, f"Fresh ({age_days:.1f} days old)"
        except ValueError:
            continue

    return True, "Date format accepted"


def is_valid_sofia_region(lead):
    """Strictly verifies the lead is in Sofia or immediate Sofia surroundings."""
    title = str(lead.get("title", "")).lower()
    loc = str(lead.get("location", "")).lower()
    desc = str(lead.get("description", "")).lower()
    full = f"{title} {loc} {desc}"

    # Reject other Bulgarian cities if Sofia is not the actual location
    for city in OTHER_BULGARIAN_CITIES:
        if city in loc and "софия" not in loc:
            return False, f"Location outside Sofia ({city})"
        if city in title and "софия" not in title:
            return False, f"Title outside Sofia ({city})"

    if any(area in full for area in SOFIA_CORE_REGIONS):
        return True, "Within Sofia operational zone"

    return False, "Location not recognized as Sofia region"


def calculate_project_value_tier(lead):
    """
    Classifies the project into clear Small vs. Large tiers for Amir (ZVB):
    - LARGE_TURNKEY_B2B: Large building projects, general contractors, KSB builders, subcontractors
    - VIP_FULL_ELECTRICAL: Full apartment/house rewiring, main switchboards, 3-phase installations
    - VIP_CCTV_SECURITY_NET: CCTV, security cameras, solar lighting, smart home, LAN/low-voltage
    -VIP_COMMERCIAL_VILLA: Villas, offices, commercial spaces, warehouses
    - SMALL_FAST_REPAIR: Small/medium fast-cash electrical repairs, sockets, boilers, lighting
    """
    title = str(lead.get("title", "")).lower()
    desc = str(lead.get("description", "")).lower()
    cat = str(lead.get("category", "")).lower()
    source = str(lead.get("source", "")).lower()
    combined = f"{title} {desc}"

    if cat == "contractor" or source in ["ksb", "business.bg"] or any(w in combined for w in LARGE_TURNKEY_B2B_KEYWORDS):
        return "LARGE_TURNKEY_B2B", "🏗 ПРOЕКТ ГОЛЯМ / СТРОИТЕЛСТВО И ПОДИЗПЪЛНЕНИЕ (پروژه بزرگ / پیمانکاری ساختمانی)"

    if any(w in combined for w in VIP_FULL_ELECTRICAL_KEYWORDS):
        return "VIP_FULL_ELECTRICAL", "⚡🏠 ЦЯЛОСТНА ЕЛ. ИНСТАЛАЦИЯ И ТАБЛА (پروژه کامل برق‌کشی و تابلو برق)"

    if any(w in combined for w in VIP_CCTV_SECURITY_NET_KEYWORDS):
        return "VIP_CCTV_SECURITY_NET", "📹☀️ КАМЕРИ, СОЛАРНИ СИСТЕМИ И СЛАБОТОКОВИ МРЕЖИ (دوربین، سولار و جریان ضعیف)"

    if any(w in combined for w in VIP_COMMERCIAL_VILLA_KEYWORDS):
        return "VIP_COMMERCIAL_VILLA", "💎🏢 ТЪРГОВСКИ / ВИЛЕН ОБЕКТ (پروژه تجاری / ویلایی)"

    if any(w in combined for w in SMALL_FAST_REPAIR_KEYWORDS):
        return "SMALL_FAST_REPAIR", "🔧⚡ МАЛЪК ПРОЕКТ / БЪРЗ РЕМОНТ И МОНТАЖ (پروژه کوچک و نقد / تعمیرات و نصب)"

    return "STANDARD", "⚡ ЕЛЕКТРО ПРОЕКТ СОФИЯ (پروژه برق صوفیه)"


def estimate_project_budget(lead):
    """Estimates project budget in EUR & BGN based on scope."""
    text = f"{lead.get('title', '')} {lead.get('description', '')} {lead.get('budget', '')} {lead.get('price', '')}".lower()
    m = re.search(r'(\d+[\s\d]*)\s*(?:лв|лева|bgn|eur|евро|€)', text)
    if m:
        num_str = re.sub(r'\s+', '', m.group(1))
        if num_str.isdigit() and int(num_str) >= 50:
            unit = "€" if ("eur" in text or "евро" in text or "€" in text) else "лв"
            return f"{num_str} {unit}"

    tier, _ = calculate_project_value_tier(lead)
    if tier == "LARGE_TURNKEY_B2B":
        return "2,500 – 25,000+ € (Договор за обект / подизпълнение)"
    elif tier == "VIP_COMMERCIAL_VILLA":
        return "1,500 – 10,000+ €"
    elif tier == "VIP_FULL_ELECTRICAL":
        return "1,200 – 4,500 €"
    elif tier == "VIP_CCTV_SECURITY_NET":
        return "600 – 3,500 €"
    elif tier == "SMALL_FAST_REPAIR":
        return "80 – 450 € (Бързо плащане)"
    return "250 – 1,500 €"


def evaluate_lead(lead, history=None, require_phone=True):
    """
    Runs all 8 enterprise filters on a candidate project lead.
    Returns (is_approved: bool, reason: str, value_tier: str).
    """
    if history is None:
        history = load_alert_history()

    # 1. Strict Phone Verification (No Phone = No Alert!)
    if require_phone:
        has_phone, phone_info = has_valid_bg_phone(lead)
        if not has_phone:
            return False, f"Rejected: {phone_info}", "NONE"

    # 2. Closed / Expired / Non-Electrical check
    closed, closed_reason = is_project_closed_or_expired(lead)
    if closed:
        return False, closed_reason, "NONE"

    # 3. Time Window (max 3 days for classifieds/tenders)
    fresh, fresh_reason = is_within_time_window(lead, max_days=3)
    if not fresh:
        return False, fresh_reason, "NONE"

    # 4. Regional check (Sofia & Sofia region)
    in_sofia, sofia_reason = is_valid_sofia_region(lead)
    if not in_sofia:
        return False, sofia_reason, "NONE"

    # 5. 4-Stage Deduplication (ID + URL Hash + Phone + Fuzzy Title)
    is_dup, dup_reason = is_duplicate_or_similar(lead, history)
    if is_dup:
        return False, dup_reason, "NONE"

    # 6. Value tier classification
    tier, _ = calculate_project_value_tier(lead)

    return True, "PASSED_ALL_FILTERS", tier


def record_alert_sent(lead, history=None):
    """Records that this lead was alerted to Telegram so it will NEVER be resent."""
    if history is None:
        history = load_alert_history()

    lead_id = str(lead.get("id", "")).strip()
    if not lead_id:
        return
    lead_url = str(lead.get("url", "")).split("?")[0].split("#")[0].strip()
    lead_title = str(lead.get("title", "")).strip()
    url_hash = hashlib.md5(lead_url.encode("utf-8")).hexdigest() if lead_url else ""

    valid_p, norm_phone = has_valid_bg_phone(lead)
    clean_phone = norm_phone if valid_p else str(lead.get("phone", ""))

    history[lead_id] = {
        "id": lead_id,
        "title": lead_title,
        "url": lead_url,
        "url_hash": url_hash,
        "phone": clean_phone,
        "source": lead.get("source", ""),
        "location": lead.get("location", ""),
        "alerted_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    save_alert_history(history)
