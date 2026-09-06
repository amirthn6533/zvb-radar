import os
import json
import re
import datetime
import difflib
import hashlib
import subprocess

HISTORY_FILE = os.path.join(os.path.dirname(__file__), "alert_history.json")

# 1. Stale / Closed Status Indicators (Bulgarian)
CLOSED_STATUS_KEYWORDS = [
    "приключен", "приключила", "изтекъл", "изтекла", "избран изпълнител",
    "затворен", "затворена", "неактивен", "неактивна", "архивиран", "спряна",
    "намерен майстор", "не приема оферти", "заето", "кандидатствали: 5/5"
]

# 2. Sofia & Immediate Surroundings (Strict Regional Filter)
SOFIA_CORE_REGIONS = [
    "софия", "sofia", "младоست", "люлин", "лозенец", "витоша", "бояна", "драгалевци",
    "симеоново", "манастирски ливади", "кръстова вада", "надежда", "център", "овча купел",
    "гео милев", "изток", "дианабад", "белите брези", "стрелбище", "красно село",
    "хиподрума", "банишора", "хаджи димитър", "дружба", "редута", "илинден",
    "красна поляна", "павлово", "банкя", "обеля", "света троица", "разсадника",
    "борово", "гоце делчев", "слатина", "славия", "връбница", "горна баня",
    "княжево", "бистрица", "панчарево", "герман", "нови искър", "софия-град"
]

# Cities that are STRICTLY rejected unless specifically targeting other countries/regions
OTHER_BULGARIAN_CITIES = [
    "бургас", "варна", "пловдив", "русе", "стара загора", "плевен", "търговище", 
    "видин", "разград", "свищов", "пазарджик", "кърджали", "велико търново",
    "перник", "благоевград", "шумен", "сливен", "хасково", "враца", "габрово",
    "пещера", "дупница", "сандански", "асеновград", "казаنлък", "червен бряг",
    "несебър", "слънчев бряг", "кюстендил", "ботевград", "мездра", "разлог", "банско"
]

# 3. High-Value Project Markers (Prioritizes 500+ BGN jobs)
HIGH_VALUE_INDICATORS = [
    "цялостно", "цялостен", "нов строеж", "нова сграда", "апартамент", "къща",
    "смяна на табло", "ново табло", "апартаментно табло", "трифазен", "окабеляване",
    "видеонаблюдение", "камери", "сот", "умен дом", "shelly", "knx", "офис",
    "заведение", "ресторант", "склад", "хале", "инсталация на цял"
]

def load_alert_history():
    if not os.path.exists(HISTORY_FILE):
        return {}
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading alert history: {e}")
        return {}

def save_alert_history(history):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Error saving alert history: {e}")
        return False

def sync_git_history():
    """Sync alert_history.json to git repo so duplicates are never resent across GitHub Actions runs."""
    try:
        subprocess.run(["git", "config", "user.name", "Zagros Bot"], capture_output=True, check=False)
        subprocess.run(["git", "config", "user.email", "bot@zvb.bg"], capture_output=True, check=False)
        subprocess.run(["git", "add", "alert_history.json"], capture_output=True, check=False)
        res = subprocess.run(["git", "commit", "-m", "chore: sync alert history [skip ci]"], capture_output=True, text=True, check=False)
        if "nothing to commit" not in res.stdout and "nothing to commit" not in res.stderr:
            subprocess.run(["git", "push"], capture_output=True, check=False)
    except Exception as e:
        pass

def normalize_text_for_comparison(text):
    """Normalizes title and description for fuzzy deduplication."""
    t = text.lower()
    t = re.sub(r"\[.*?\]", " ", t)  # strip [MaistorPlus], [Daibau]
    t = re.sub(r"[^\w\s]", " ", t)  # strip punctuation
    t = re.sub(r"\s+", " ", t).strip()
    return t

def calculate_similarity(text1, text2):
    """Calculates SequenceMatcher ratio between two normalized project texts."""
    norm1 = normalize_text_for_comparison(text1)
    norm2 = normalize_text_for_comparison(text2)
    return difflib.SequenceMatcher(None, norm1, norm2).ratio()

def is_duplicate_or_similar(lead, history):
    """
    Layer 1: Exact ID check
    Layer 2: Canonical URL hash check
    Layer 3: Fuzzy text similarity (> 80% similarity with already alerted job)
    """
    lead_id = lead.get("id", "")
    lead_url = lead.get("url", "").split("?")[0]
    lead_title = lead.get("title", "")
    url_hash = hashlib.md5(lead_url.encode("utf-8")).hexdigest()

    # 1. Exact ID
    if lead_id in history:
        return True, f"Exact ID already alerted ({lead_id})"

    # 2. Canonical URL Hash
    for hid, item in history.items():
        if item.get("url_hash") == url_hash:
            return True, f"URL hash match with {hid}"

    # 3. Fuzzy similarity check against recent alerts (last 30 days)
    for hid, item in history.items():
        hist_title = item.get("title", "")
        sim = calculate_similarity(lead_title, hist_title)
        if sim >= 0.80:
            return True, f"High text similarity ({sim:.0%}) with already alerted job '{hist_title[:30]}...'"

    return False, "New unique project"

def is_project_closed_or_expired(lead):
    """
    Layer 4: Checks if project tender is closed, awarded, or archived.
    """
    combined = f"{lead.get('title', '')} {lead.get('description', '')} {lead.get('status', '')}".lower()
    for kw in CLOSED_STATUS_KEYWORDS:
        if kw in combined:
            return True, f"Project status is closed/expired: '{kw}'"
    return False, "Active"

def is_within_time_window(lead, max_days=14):
    """
    Layer 5: Strict freshness window (Default: max 14 days old).
    """
    found_at = lead.get("found_at", "")
    if not found_at:
        return True, "No timestamp (assume fresh)"
    try:
        lead_time = datetime.datetime.strptime(found_at, "%Y-%m-%d %H:%M")
        diff_days = (datetime.datetime.now() - lead_time).total_seconds() / 86400
        if diff_days > max_days:
            return False, f"Expired time window ({diff_days:.1f} days old > {max_days} days limit)"
        return True, f"Fresh ({diff_days:.1f} days old)"
    except Exception:
        return True, "Date parse error (pass)"

def is_valid_sofia_region(lead):
    """
    Layer 6: Regional check - strictly Sofia & environs.
    """
    title = lead.get("title", "").lower()
    loc = lead.get("location", "").lower()
    full = f"{title} {loc}".lower()

    # Reject other cities
    for city in OTHER_BULGARIAN_CITIES:
        if city in full and "софия" not in full:
            return False, f"Location outside Sofia ({city})"

    # Check for Sofia presence
    if any(area in full for area in SOFIA_CORE_REGIONS):
        return True, "Within Sofia operational zone"

    return False, "Location not recognized as Sofia region"

def calculate_project_value_tier(lead):
    """
    Layer 7: Project value scoring (High, Medium, Normal).
    """
    title = lead.get("title", "").lower()
    budget = lead.get("budget", "").lower()
    combined = f"{title} {budget}"

    is_high = any(w in combined for w in HIGH_VALUE_INDICATORS)
    if is_high or any(b in budget for b in ["1000", "1500", "2000", "3000", "5000", "над 1000"]):
        return "HIGH_VALUE", "💎 Голям/високобюджетен обект (500+ лв)"
    return "STANDARD", "⚡ Стандартна електро заявка"

def evaluate_lead(lead, history=None):
    """
    Runs all 7 filters on a candidate project lead.
    Returns (is_approved: bool, reason: str, value_tier: str).
    """
    if history is None:
        history = load_alert_history()

    # 1. Closed / Expired check
    closed, closed_reason = is_project_closed_or_expired(lead)
    if closed:
        return False, closed_reason, "NONE"

    # 2. Time Window (max 14 days)
    fresh, fresh_reason = is_within_time_window(lead, max_days=14)
    if not fresh:
        return False, fresh_reason, "NONE"

    # 3. Regional check (Sofia)
    in_sofia, sofia_reason = is_valid_sofia_region(lead)
    if not in_sofia:
        return False, sofia_reason, "NONE"

    # 4. Strict Deduplication & Text Similarity (> 80%)
    is_dup, dup_reason = is_duplicate_or_similar(lead, history)
    if is_dup:
        return False, dup_reason, "NONE"

    # 5. Value tier scoring
    tier, tier_label = calculate_project_value_tier(lead)

    return True, "PASSED_ALL_7_FILTERS", tier

def record_alert_sent(lead, history=None):
    """Records that this lead was alerted to Telegram so it will NEVER be resent."""
    if history is None:
        history = load_alert_history()

    lead_id = lead.get("id", "")
    lead_url = lead.get("url", "").split("?")[0]
    lead_title = lead.get("title", "")
    url_hash = hashlib.md5(lead_url.encode("utf-8")).hexdigest()

    history[lead_id] = {
        "id": lead_id,
        "title": lead_title,
        "url": lead_url,
        "url_hash": url_hash,
        "source": lead.get("source", ""),
        "location": lead.get("location", ""),
        "alerted_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    save_alert_history(history)
