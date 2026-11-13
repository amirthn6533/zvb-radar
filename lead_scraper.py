# -*- coding: utf-8 -*-
"""
ZVB Ultimate Lead & Project Radar v3.0 — Sofia, Bulgaria
Representative: Амир (Amir) | Company: „Загрос Витоша България“ ЕООД (ZVB)

Multi-Engine Discovery System:
1. Engine A (Small & Medium Fast-Cash Projects): Alo.bg, Bazar.bg, MaistorPlus (Direct Sofia client & renovation requests with verified phone numbers)
2. Engine B (Large & Turnkey Construction Projects): Official Chamber of Builders (КСБ - register.ksb.bg) active 2025/2026 Sofia builders with Building Permits & Manager contacts
3. Engine C (Sofia Construction, Renovation, Villa & MEP Contractors): Business.bg Sofia verified contractors with direct mobile numbers
4. Engine D (Active Sofia Sites Hiring Subcontractors/Brigades): Zaplata.bg & Alo.bg construction ads cross-referenced with KSB/Business.bg phone resolver
5. Strict 8-Layer Filter: Zero duplicates, mandatory valid Bulgarian phone number, Sofia geo-fencing, and personalized scripts in Amir's name.
"""

import os
import sys
import re
import time
import json
import csv
import hashlib
import datetime
import urllib.parse
import random
import requests
from bs4 import BeautifulSoup
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

import lead_filter_engine

sys.stdout.reconfigure(encoding='utf-8')

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
]

HEADERS = {
    'User-Agent': USER_AGENTS[0],
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'bg-BG,bg;q=0.9,en;q=0.8',
    'Upgrade-Insecure-Requests': '1'
}

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")
LEADS_JSON_PATH = os.path.join(DATA_DIR, "leads.json")
LEADS_CSV_PATH = os.path.join(DATA_DIR, "leads.csv")
DASHBOARD_HTML_PATH = os.path.join(DATA_DIR, "leads_dashboard.html")

DEFAULT_KEYWORDS = [
    "търся електротехник софия",
    "търсят се майстори подизпълнители софия",
    "строителна фирма търси електротехник софия",
    "ремонт на ел инсталация софия",
    "монтаж на камери видеонаблюдение софия",
    "смяна на ел табло софия"
]


def get_resilient_session(retries=3, backoff_factor=0.5):
    session = requests.Session()
    retry_strategy = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=[429, 500, 502, 503, 504],
        raise_on_status=False
    )
    adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=20)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def get_browser_headers(referer=None):
    ua = random.choice(USER_AGENTS)
    h = {
        'User-Agent': ua,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'bg-BG,bg;q=0.9,en-US;q=0.8,en;q=0.7',
        'Cache-Control': 'no-cache',
        'Upgrade-Insecure-Requests': '1'
    }
    if referer:
        h['Referer'] = referer
    return h


def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Could not read config.json: {e}")
    return {
        "telegram": {"enabled": False, "bot_token": "", "chat_id": ""},
        "keywords": DEFAULT_KEYWORDS
    }


def extract_phone_numbers(text):
    """
    Extracts valid Bulgarian mobile (087, 088, 089, 098) and Sofia landline (02) numbers.
    Filters out non-Sofia area codes and invalid numbers.
    """
    if not text:
        return []
    matches = []
    # 1. Mobile numbers: +359 888 123 456 or 0888 123 456 or 0888-12-34-56
    mob_pattern = r'(?:\+359|00359|0)[\s\-\.]*(8[789]\d|98\d)[\s\-\.]*(\d{2,3})[\s\-\.]*(\d{2,3})[\s\-\.]*(\d{1,2})?'
    for m in re.finditer(mob_pattern, text):
        raw = m.group(0)
        digits = re.sub(r'\D', '', raw)
        if digits.startswith('359') and len(digits) == 12:
            digits = '0' + digits[3:]
        elif digits.startswith('00359') and len(digits) == 14:
            digits = '0' + digits[5:]
        if len(digits) == 10 and digits.startswith(('087', '088', '089', '098')):
            formatted = f"{digits[:4]} {digits[4:7]} {digits[7:]}"
            if formatted not in matches and digits not in lead_filter_engine.BLACKLISTED_PHONES:
                matches.append(formatted)

    # 2. Sofia landline: 02 / 967 00 08 or 02 889 1038
    sofia_pattern = r'\b02[\s\-\/\.]{1,3}(\d{3})[\s\-\.]*(\d{2})[\s\-\.]*(\d{2})\b'
    for m in re.finditer(sofia_pattern, text):
        formatted = f"02 {m.group(1)} {m.group(2)} {m.group(3)}"
        digits = re.sub(r'\D', '', formatted)
        if len(digits) == 9 and digits not in lead_filter_engine.BLACKLISTED_PHONES:
            if formatted not in matches:
                matches.append(formatted)

    return matches


def normalize_bg_phone(raw_phone):
    """Returns (local_display, intl_digits) e.g. ('0888123456', '359888123456')"""
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
        return local, digits
    return None, None


def classify_lead(title, keyword, description=""):
    t = (str(title) + " " + str(keyword) + " " + str(description)).lower()

    if any(w in t for w in ["строителна", "груб строеж", "инвеститор", "подизпълнител", "бригада", "технически ръководител", "жилищна сграда", "до ключ", "цпрс", "ксб"]):
        return "contractor", "🏗 Голям обект / Строител и Главен изпълнител (پروژه بزرگ ساختمانی)"
    if any(w in t for w in ["търся", "търси", "спешно", "нуждая се", "заявка", "оферта за"]):
        return "urgent_client", "🎯 Директен клиент / Спешна заявка (کارفرمای مستقیم)"
    if any(w in t for w in ["ремонт", "довършителни", "апартамент", "къща", "офис", "освежаване", "преустройство"]):
        return "renovation", "🏠 Ремонт и преустройство на сграда/жилище (پروژه بازسازی و نوسازی)"
    return "direct_electrical", "⚡ Електроинсталации, Табла, Камери и Солари (تأسیسات برق و دوربین)"


def build_amir_pitch_for_lead(lead):
    """
    Generates a ready-to-copy Bulgarian pitch personalized in the name of Amir (Амир)
    representing „Загрос Витоша България“ ЕООД (ZVB), tailored to Small vs Large projects.
    """
    tier, _ = lead_filter_engine.calculate_project_value_tier(lead)
    mgr = lead.get("manager", "").strip()
    greeting = f"Здравейте, {mgr}!" if mgr else "Здравейте!"

    if tier == "LARGE_TURNKEY_B2B" or lead.get("category") == "contractor":
        return (
            f"{greeting} Казвам се Амир от фирма „Загрос Витоша България“ ЕООД (ZVB София). "
            "Изпълняваме комплексни електромонтажни дейности като надежден подизпълнител за жилищни сгради, къщи и търговски обекти в София: "
            "силнотокови и слаботокови инсталации, главни и апартаментни ел. табла, видеонаблюдение, соларно и парково осветление. "
            "Разполагаме със собствена бригада и спазваме стриктно сроковете по Акт 14/15/16. "
            "Може ли да ни изпратите количествена сметка за оферта по Ваш текущ обект? Поздрави, Амир."
        )
    elif tier == "VIP_CCTV_SECURITY_NET":
        return (
            f"{greeting} Казвам се Амир от фирма „Загрос Витоша България“ ЕООД (гр. София). "
            "Видях Вашето запитване и можем да реагираме веднага с професионален монтаж на видеонаблюдение (4K IP/PTZ камери), "
            "слаботоково окабеляване, контрол на достъпа и автономно соларно осветление с гаранция. "
            "Предлагаме безплатен оглед в София. Поздрави, Амир."
        )
    else:
        return (
            f"{greeting} Казвам се Амир от фирма „Загрос Витоша България“ ЕООД (гр. София). "
            "Видях Вашата обява за електроуслуги и можем да поемем обекта веднага – цялостно окабеляване, "
            "монтаж/смяна на ел. табло с дефектнотокови защити, захранване на уреди и осветление. "
            "Предлагаме безплатен оглед на място в София и чиста работа с гаранция. Поздрави, Амир. Тел: +359 87 7944353 | https://zvb.bg"
        )


build_amir_pitch = build_amir_pitch_for_lead


def resolve_company_phone_ksb_and_dirs(company_name, session=None):
    """
    Given a Bulgarian company name (from Alo.bg, Zaplata.bg, Bazar.bg, etc.),
    automatically queries the Official Chamber of Builders (register.ksb.bg/spravki.php)
    and Business.bg to resolve its official Sofia phone number, manager name, and address!
    """
    if not company_name or len(company_name.strip()) < 3:
        return None
    clean_name = re.sub(r'\b(ЕООД|ООД|АД|ЕТ|ЕАД|ДЗЗД|КОНСОРЦИУМ)\b', '', company_name, flags=re.I)
    clean_name = re.sub(r'["„“\'«»]', '', clean_name).strip()
    if len(clean_name) < 3:
        return None

    sess = session or get_resilient_session(retries=2, backoff_factor=0.3)

    # 1. Try Official Chamber of Builders (register.ksb.bg/spravki.php)
    try:
        r = sess.post(
            "https://register.ksb.bg/spravki.php",
            data={"findEIK": "", "findNAME": clean_name[:25], "filter1": "Търси вписани в регистъра"},
            headers=get_browser_headers("https://register.ksb.bg/"),
            timeout=8
        )
        r.encoding = 'utf-8'
        if r.status_code == 200 and 'pub_view.php' in r.text:
            soup = BeautifulSoup(r.text, 'html.parser')
            for a in soup.find_all('a', href=True):
                if 'pub_view.php' in a['href']:
                    info = parse_ksb_member_page(a['href'], sess)
                    if info and info.get("phone"):
                        ok_p, _ = lead_filter_engine.has_valid_bg_phone({"phone": info["phone"]})
                        if ok_p and "софия" in (info.get("city", "") + " " + info.get("address", "")).lower():
                            return info
    except Exception:
        pass

    return None


def parse_ksb_member_page(href, session=None):
    """Parses a builder's official KSB dossier (pub_view.php?id_members=...) for phone, manager, and active projects."""
    sess = session or get_resilient_session(retries=2, backoff_factor=0.3)
    url = href if href.startswith("http") else f"https://register.ksb.bg/{href.lstrip('/')}"
    try:
        rd = sess.get(url, headers=get_browser_headers("https://register.ksb.bg/"), timeout=9)
        rd.encoding = 'utf-8'
        if rd.status_code != 200:
            return None
        soup = BeautifulSoup(rd.text, 'html.parser')

        info = {
            "name": "",
            "eik": "",
            "manager": "",
            "city": "София",
            "address": "",
            "phone": "",
            "email": "",
            "website": "",
            "projects": [],
            "url": url
        }

        full_txt = soup.get_text(" | ", strip=True)
        m_eik = re.search(r'ЕИК по БУЛСТАТ:\s*(\d{9,13})', full_txt)
        if m_eik:
            info["eik"] = m_eik.group(1)

        m_name = re.search(r'наименование:\s*\|?\s*([^\|]+?)\s*\|\s*правно-организационна форма:\s*\|?\s*([^\|]+)', full_txt)
        if m_name:
            info["name"] = f"{m_name.group(1).strip()} {m_name.group(2).strip()}".strip()

        for tr in soup.find_all('tr'):
            tds = [td.get_text(" ", strip=True) for td in tr.find_all('td')]
            row_txt = tr.get_text(" | ", strip=True)

            if 'град(село):' in row_txt and not info["address"]:
                m_city = re.search(r'град\(село\):\s*\|?\s*([^\|]+)', row_txt)
                if m_city:
                    info["city"] = m_city.group(1).strip()

            if 'улица,' in row_txt and not info["address"]:
                m_str = re.search(r'улица,[^:]*:\s*\|?\s*([^\|]+)', row_txt)
                if m_str:
                    info["address"] = m_str.group(1).strip()

            if 'тел.код:' in row_txt and 'Телефон:' in row_txt:
                m_c = re.search(r'тел\.код:\s*\|?\s*([0-9\+]{0,5})', row_txt)
                m_t = re.search(r'Телефон:\s*\|?\s*([0-9\s\-\/\.\,;]+)', row_txt)
                c_val = m_c.group(1).strip() if m_c else ''
                t_val = m_t.group(1).strip() if m_t else ''
                if t_val:
                    # Extract first phone if multiple separated by comma/semicolon/slash
                    first_t = re.split(r'[;,]', t_val)[0].strip()
                    cand_raw = f"{c_val} {first_t}".strip()
                    extracted = extract_phone_numbers(cand_raw)
                    if extracted:
                        info["phone"] = extracted[0]
                    else:
                        digits = re.sub(r'\D', '', cand_raw)
                        if len(digits) == 7 and digits[0] in '23489' and 'софия' in info["city"].lower():
                            info["phone"] = f"02 {digits[:3]} {digits[3:5]} {digits[5:]}"
                        elif len(digits) == 10 and digits.startswith(('087', '088', '089', '098')):
                            info["phone"] = f"{digits[:4]} {digits[4:7]} {digits[7:]}"

            if 'E-mail:' in row_txt and not info["email"]:
                m_em = re.search(r'E-mail:\s*\|?\s*([^\s\|]+@[^\s\|]+)', row_txt)
                if m_em:
                    info["email"] = m_em.group(1).strip()

            if len(tds) >= 6 and tds[0] == '1' and not info["manager"]:
                role = tds[5].strip()
                if any(k in role.lower() for k in ['управител', 'изпълнителен', 'директор', 'председател']):
                    info["manager"] = f"{tds[1].strip()} {tds[3].strip()} ({role})"

            if len(tds) >= 10 and tds[0] in ('2023', '2024', '2025', '2026'):
                proj_title = tds[2].strip()
                investor = tds[4].strip()
                if proj_title and len(proj_title) > 10:
                    info["projects"].append(f"{proj_title[:95]} (Възложител: {investor[:45]})")

        return info
    except Exception:
        return None


def scrape_ksb_sofia_builders(existing_leads, alert_history, max_new=3):
    """
    Engine B (Large Turnkey Construction Projects):
    Queries the Official Chamber of Builders (register.ksb.bg) for Sofia general contractors
    with active 2025/2026 protocols (Group 1.1 - 1.4 High-Rise, Residential & Villas).
    Extracts verified phone numbers, manager names, and active building permits!
    """
    results = []
    sess = get_resilient_session(retries=2, backoff_factor=0.5)

    # Rotate across Sofia building groups: 11 (Major), 12 (Large), 13 (Medium Residential), 14 (Villas & Low-rise)
    for grp in ["11", "13", "14"]:
        if len(results) >= max_new:
            break
        try:
            r = sess.post(
                "https://register.ksb.bg/listFirms.php",
                data={
                    "Podphp": "22",
                    "GroupTypephp": grp,
                    "Pod": "22",
                    "GroupType": grp,
                    "filter": "Покажи строителите"
                },
                headers=get_browser_headers("https://register.ksb.bg/"),
                timeout=12
            )
            r.encoding = 'utf-8'
            if r.status_code != 200:
                continue

            soup = BeautifulSoup(r.text, 'html.parser')
            for tr in soup.find_all('tr'):
                if len(results) >= max_new:
                    break
                row_txt = tr.get_text(" | ", strip=True)
                # Focus on active builders with recent 2025/2026 protocols
                if not any(y in row_txt for y in ('2026', '2025')):
                    continue
                a = tr.find('a', href=True)
                if not a or 'pub_view.php' not in a['href']:
                    continue

                m_id = re.search(r'id_members=(\d+)', a['href'])
                if not m_id:
                    continue
                lead_id = f"ksb_{m_id.group(1)}"

                if lead_id in existing_leads or lead_id in alert_history:
                    continue

                info = parse_ksb_member_page(a['href'], sess)
                if not info or not info.get("phone"):
                    continue

                # Verify valid Sofia/BG mobile or Sofia landline
                ok_phone, _ = lead_filter_engine.has_valid_bg_phone({"phone": info["phone"]})
                if not ok_phone:
                    continue

                if "софия" not in (info.get("city", "") + " " + info.get("address", "")).lower():
                    continue

                comp_name = info.get("name") or row_txt.split("|")[2].strip()
                mgr_str = info.get("manager", "")
                proj_str = info["projects"][0] if info.get("projects") else "Жилищно и обществено строителство до ключ в гр. София (Група I ЦПРС)"
                addr_str = f"София, {info['address']}" if info.get("address") else "гр. София"

                desc_parts = [f"Официално вписан главен изпълнител в ЦПРС (КСБ) с активен протокол 2025/2026."]
                if mgr_str:
                    desc_parts.append(f"Управител: {mgr_str}.")
                if info.get("email"):
                    desc_parts.append(f"Имейл: {info['email']}.")
                desc_parts.append(f"Обекти: {proj_str}")

                lead_obj = {
                    "id": lead_id,
                    "title": f"[Голям Строител София] {comp_name} — {proj_str[:65]}",
                    "description": " ".join(desc_parts),
                    "manager": mgr_str,
                    "email": info.get("email", ""),
                    "url": info["url"],
                    "source": "KSB",
                    "keyword": "Главен изпълнител / Строителство до ключ София",
                    "category": "contractor",
                    "category_label": "🏗 Голям обект / Главен изпълнител (ЦПРС София)",
                    "location": addr_str,
                    "phone": info["phone"],
                    "found_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                }

                is_dup, _ = lead_filter_engine.is_duplicate_or_similar(lead_obj, alert_history)
                if not is_dup:
                    results.append(lead_obj)
                    time.sleep(0.3)
        except Exception as e:
            print(f"  [KSB Engine] Error on group {grp}: {e}")

    return results


def scrape_business_bg_sofia(existing_leads, alert_history, max_new=4):
    """
    Engine C (Sofia Turnkey Builders, House Builders, Renovation Contractors & MEP Engineering):
    Scrapes verified Sofia companies with direct mobile numbers from Business.bg.
    Covers both Medium Renovation Contractors and Large Residential/Villa Builders.
    """
    results = []
    sess = get_resilient_session(retries=2, backoff_factor=0.4)

    sofia_categories = [
        ("/o-208/zhilishtno-stroitelstvo/c-214/sofia.html", "contractor", "🏗 Жилищно строителство София (پروژه بزرگ ساختمانی)"),
        ("/o-219/stroitelstvo-na-kyshti/c-214/sofia.html", "contractor", "🏡 Строителство на къщи до ключ София (ساخت ویلا صفر تا صد)"),
        ("/o-222/stroitelni-remonti/c-214/sofia.html", "renovation", "🏠 Довършителни ремонти на апартаменти и офиси София (پروژه بازسازی)"),
        ("/o-747/stroitelni-firmi/c-214/sofia.html", "contractor", "🏗 Строителна компания София (شرکت ساختمانی صوفیه)"),
        ("/o-224/inzhenering/c-214/sofia.html", "contractor", "⚙️ Инженеринг и СМР София (پیمانکار مهندسی و تاسیسات)"),
        ("/o-301/klimatici/c-214/sofia.html", "contractor", "❄️ ОВК и Климатични системи София (نیازمند برق‌رسانی و تابلو)"),
        ("/o-508/arhitektura/c-214/sofia.html", "contractor", "📐 Архитектурно и проектно студио София (طراح و معمار پروژه)")
    ]

    for path, cat_code, cat_label in sofia_categories:
        if len(results) >= max_new:
            break
        url = f"https://www.business.bg{path}"
        try:
            r = sess.get(url, headers=get_browser_headers("https://www.business.bg/"), timeout=10)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, 'html.parser')
            cards = soup.select('div.firm_content')

            for card in cards:
                if len(results) >= max_new:
                    break
                h2 = card.select_one('h2.firm_title')
                tel_el = card.select_one('.tel_b')
                desc_el = card.select_one('.firm_text')
                mail_el = card.select_one('.mail_b a[href^="mailto:"]')
                link_el = card.select_one('a[href]')

                if not h2 or not tel_el:
                    continue

                firm_name = h2.get_text(" ", strip=True)
                raw_tel = tel_el.get_text(" ", strip=True)
                desc_txt = desc_el.get_text(" ", strip=True) if desc_el else ""

                # Skip non-electrical/unrelated services like waste disposal or asphalt only
                low_comb = f"{firm_name} {desc_txt}".lower()
                if any(bad in low_comb for bad in ["отпадъци", "асфалтиране", "шлайфан бетон", "геодезия", "микропилоти"]):
                    continue

                phones = extract_phone_numbers(raw_tel)
                if not phones:
                    continue
                best_phone = phones[0]

                href = link_el['href'] if link_el else url
                full_url = urllib.parse.urljoin("https://www.business.bg", href)
                slug_hash = hashlib.md5(firm_name.encode('utf-8')).hexdigest()[:10]
                lead_id = f"bizbg_{slug_hash}"

                if lead_id in existing_leads or lead_id in alert_history:
                    continue

                email_val = mail_el['href'].replace('mailto:', '').strip() if mail_el else ""

                lead_obj = {
                    "id": lead_id,
                    "title": f"{firm_name} — {desc_txt[:65]}..." if desc_txt else firm_name,
                    "description": desc_txt,
                    "email": email_val,
                    "url": full_url,
                    "source": "Business.bg",
                    "keyword": cat_label,
                    "category": cat_code,
                    "category_label": cat_label,
                    "location": "гр. София",
                    "phone": best_phone,
                    "found_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                }

                ok_eval, _, _ = lead_filter_engine.evaluate_lead(lead_obj, alert_history, require_phone=True)
                if ok_eval:
                    results.append(lead_obj)
        except Exception as e:
            print(f"  [Business.bg Engine] Error on {path}: {e}")

    return results


def scrape_alo(keyword):
    """
    Engine A1: Scrapes Alo.bg for fresh Sofia electrical, renovation & subcontractor demand.
    Automatically skips stale ads ('преди 30+ дни'), job-seekers ('търсят работа'), and courses.
    Extracts direct phone numbers from ad text OR resolves company phone via KSB/Business.bg!
    """
    results = []
    session = get_resilient_session(retries=2, backoff_factor=0.4)
    headers = get_browser_headers(referer="https://www.alo.bg/")

    try:
        url = "https://www.alo.bg/searchq/"
        resp = session.get(url, params={"q": keyword}, headers=headers, timeout=11)
        if resp.status_code != 200:
            return results

        soup = BeautifulSoup(resp.text, 'html.parser')
        items = soup.select('.listvip-item, .list-item')

        for item in items:
            card_text = item.get_text(" ", strip=True)
            low_card = card_text.lower()

            # Reject stale ads (> 6 days old) right on the search card
            if any(stale in low_card for stale in [
                "преди 30+ дни", "преди 2", "преди 1", "преди 9 дни", "преди 8 дни", "преди 7 дни",
                "търсят работа", "желана длъжност", "обучение, курсове", "имоти - продажби", "под наем"
            ]):
                continue

            link_tag = item.select_one('a[href]')
            href = link_tag['href'] if link_tag else ''
            if not href:
                continue

            clean_href = href.split('#')[0]
            full_url = urllib.parse.urljoin("https://www.alo.bg", clean_href)
            id_match = re.search(r'(\d{6,10})', clean_href)
            ad_id = f"alo_{id_match.group(1)}" if id_match else f"alo_{hash(full_url)}"

            title_el = item.select_one('h3, h2, .listvip-item-title, .list-item-title')
            title = title_el.get_text(" ", strip=True) if title_el else (link_tag.get_text(" ", strip=True) if link_tag else "")
            if not title or len(title) < 5:
                continue

            if "софия" not in low_card and "софия" not in title.lower():
                continue

            # Extract phones from card snippet
            phones = extract_phone_numbers(card_text)
            phone_val = phones[0] if phones else ""
            manager_val = ""

            # If no phone in card snippet, check if a company name is listed on the card and resolve via KSB!
            if not phone_val:
                m_firm = re.search(r'Длъжност\s*:\s*[^Ф]+?\s+([А-Яа-яA-Za-z0-9\s\"„“\-]{3,35}?)\s+(?:Фирма|Агенция|ЕООД|ООД)', card_text)
                if not m_firm:
                    m_firm = re.search(r'^([А-Яа-яA-Za-z0-9\s\"„“\-]{3,35}?(?:ЕООД|ООД|АД))\s+преди', card_text)
                if m_firm:
                    comp_candidate = m_firm.group(1).strip()
                    resolved = resolve_company_phone_ksb_and_dirs(comp_candidate, session)
                    if resolved and resolved.get("phone"):
                        phone_val = resolved["phone"]
                        manager_val = resolved.get("manager", "")
                        title = f"[{comp_candidate}] {title}"

            cat, cat_label = classify_lead(title, keyword, card_text)

            results.append({
                "id": ad_id,
                "title": title,
                "description": card_text[:300],
                "manager": manager_val,
                "url": full_url,
                "source": "Alo.bg",
                "keyword": keyword,
                "category": cat,
                "category_label": cat_label,
                "location": "гр. София",
                "phone": phone_val,
                "found_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            })
    except Exception as e:
        print(f"  [Alo.bg] Error searching '{keyword}': {e}")
    return results


def scrape_bazar(keyword, fetch_phone=True):
    """
    Engine A2: Scrapes Bazar.bg Sofia listings and extracts direct phone numbers from descriptions.
    """
    results = []
    encoded_q = urllib.parse.quote(keyword)
    url = f"https://bazar.bg/obiavi/sofia?q={encoded_q}"
    session = get_resilient_session(retries=2, backoff_factor=0.4)
    headers = get_browser_headers(referer="https://bazar.bg/")

    try:
        resp = session.get(url, headers=headers, timeout=11)
        if resp.status_code != 200:
            return results

        soup = BeautifulSoup(resp.text, 'html.parser')
        seen_links = set()

        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            if '/obiava-' not in href or href in seen_links:
                continue
            seen_links.add(href)

            title = a_tag.get('title') or a_tag.get_text(" ", strip=True)
            if not title or len(title) < 6:
                continue

            low_t = title.lower()
            if any(ex in low_t for ex in [
                "курс", "обучение", "продавам", "дава под наем", "под наем",
                "пазарджик", "ловеч", "плевен", "варна", "бургас",
                "bmw", "mercedes", "audi", "puretech", "crossback", "tdi", "cdi", "4.0i", "автомобил"
            ]):
                continue
            if not any(stem in low_t for stem in lead_filter_engine.REQUIRED_RELEVANCE_STEMS):
                continue

            ad_id_match = re.search(r'obiava-(\d+)', href)
            ad_id = f"bazar_{ad_id_match.group(1)}" if ad_id_match else f"bazar_{hash(href)}"
            full_url = urllib.parse.urljoin("https://bazar.bg", href)

            phones = extract_phone_numbers(title)
            phone_val = phones[0] if phones else ""
            cat, cat_label = classify_lead(title, keyword)

            results.append({
                "id": ad_id,
                "title": title,
                "url": full_url,
                "source": "Bazar.bg",
                "keyword": keyword,
                "category": cat,
                "category_label": cat_label,
                "location": "гр. София",
                "phone": phone_val,
                "found_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            })
    except Exception as e:
        print(f"  [Bazar.bg] Error searching '{keyword}': {e}")
    return results


def scrape_zaplata_sofia_construction(existing_leads, alert_history, max_new=3):
    """
    Engine D: Scans live Sofia construction & electrical listings on Zaplata.bg
    (where construction companies are actively hiring site managers, electrical engineers, or brigades today),
    extracts the company name, and resolves its official phone number & manager via KSB!
    """
    results = []
    sess = get_resilient_session(retries=2, backoff_factor=0.4)
    urls = [
        "https://www.zaplata.bg/arhitektura-stroitelstvo-i-gradoustroystvo/sofia/",
        "https://www.zaplata.bg/search/?q=%D0%B5%D0%BB%D0%B5%D0%BA%D1%82%D1%80%D0%BE%D1%82%D0%B5%D1%85%D0%BD%D0%B8%D0%BA&city=1"
    ]

    seen_urls = set()
    for u in urls:
        if len(results) >= max_new:
            break
        try:
            r = sess.get(u, headers=get_browser_headers("https://www.zaplata.bg/"), timeout=10)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, 'html.parser')
            for a in soup.find_all('a', href=True):
                if len(results) >= max_new:
                    break
                href = a['href']
                if '/sofia/' not in href or not any(c.isdigit() for c in href) or href in seen_urls:
                    continue
                seen_urls.add(href)

                m_id = re.search(r'/sofia/(\d+)/', href)
                if not m_id:
                    continue
                lead_id = f"zap_{m_id.group(1)}"
                if lead_id in existing_leads or lead_id in alert_history:
                    continue

                job_title = a.get_text(" ", strip=True)
                low_jt = job_title.lower()
                if any(bad in low_jt for bad in ["шофьор", "камериер", "охранител", "продавач", "готвач", "чистач", "ситопечат"]):
                    continue

                # Fetch detail page to extract company name & any direct phone
                rd = sess.get(href, headers=get_browser_headers(u), timeout=9)
                if rd.status_code != 200:
                    continue
                sd = BeautifulSoup(rd.text, 'html.parser')
                for s_tag in sd(['script', 'style', 'nav', 'footer']):
                    s_tag.decompose()
                d_txt = sd.get_text(" ", strip=True)

                phones = extract_phone_numbers(d_txt)
                phone_val = phones[0] if phones else ""
                manager_val = ""
                comp_name = ""

                # Extract company name cleanly
                m_comp = re.search(r'((?:[А-ЯA-Z0-9\"„“\-]+\s+){1,4}(?:ЕООД|ООД|АД|ЕАД))', d_txt)
                if m_comp:
                    comp_name = m_comp.group(1).strip()
                    comp_name = re.sub(r'^(?:\d+\s+|Общ работник\s+|Монтажници\s+|Електротехник\s+)+', '', comp_name, flags=re.IGNORECASE).strip()
                    if not phone_val:
                        resolved = resolve_company_phone_ksb_and_dirs(comp_name, sess)
                        if resolved and resolved.get("phone"):
                            phone_val = resolved["phone"]
                            manager_val = resolved.get("manager", "")

                if not phone_val:
                    continue

                clean_title = f"[{comp_name or 'Строителна Компания София'}] Активен обект: {job_title[:65]}"
                lead_obj = {
                    "id": lead_id,
                    "title": clean_title,
                    "description": d_txt[:350],
                    "manager": manager_val,
                    "url": href,
                    "source": "Zaplata.bg / KSB",
                    "keyword": "Активно строителство и електро в София",
                    "category": "contractor",
                    "category_label": "🏗 Активен строителен обект в София (پروژه فعال ساختمانی)",
                    "location": "гр. София",
                    "phone": phone_val,
                    "found_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                }

                ok_eval, _, _ = lead_filter_engine.evaluate_lead(lead_obj, alert_history, require_phone=True)
                if ok_eval:
                    results.append(lead_obj)
        except Exception as e:
            print(f"  [Zaplata/KSB Engine] Error: {e}")

    return results


def scrape_maistorplus(username, password):
    """
    Scrapes MaistorPlus logged-in jobs in Sofia, inspects detail pages to filter out closed/full jobs,
    and extracts any direct client phone numbers.
    """
    results = []
    seen_ids = set()
    session = get_resilient_session(retries=2, backoff_factor=0.5)
    headers = get_browser_headers(referer="https://maistorplus.com/")

    mp_electrical_keywords = ['контакт', 'ел.', 'ел ', 'електро', 'осветлен', 'табло', 'бойлер', 'кабел', 'ключ', 'лед', 'камер', 'видеонаблюдение', 'умен дом', 'инсталаци']

    logged_in = False
    try:
        r1 = session.get('https://maistorplus.com/login', headers=headers, timeout=10)
        soup = BeautifulSoup(r1.text, 'html.parser')
        token_input = soup.find('input', {'name': '_csrf_token'})
        if token_input:
            csrf = token_input.get('value')
            login_resp = session.post('https://maistorplus.com/login_check', data={
                '_csrf_token': csrf,
                '_username': username,
                '_password': password,
                '_remember_me': 'on'
            }, headers=headers, timeout=10)
            if login_resp.status_code == 200 or '/craftsman' in login_resp.url:
                logged_in = True
    except Exception as e:
        print(f"  [MaistorPlus] Login notice: {e}")

    endpoints = ['https://maistorplus.com/craftsman/jobs/no-exchanged-phones'] if logged_in else ['https://maistorplus.com/remonti/elektro-uslugi']

    for ep in endpoints:
        try:
            r_jobs = session.get(ep, headers=get_browser_headers(referer="https://maistorplus.com/"), timeout=10)
            if r_jobs.status_code != 200:
                continue
            soup_jobs = BeautifulSoup(r_jobs.text, 'html.parser')

            for a_tag in soup_jobs.find_all('a', href=True):
                href = a_tag['href']
                if '/job/' not in href:
                    continue
                clean_href = href.split('?')[0]
                m = re.search(r'/job/(\d+)', clean_href)
                if not m:
                    continue
                job_id = f"mp_{m.group(1)}"
                if job_id in seen_ids:
                    continue
                seen_ids.add(job_id)

                row = a_tag.find_parent('tr') or a_tag.parent
                row_txt = row.get_text(" ", strip=True) if row else a_tag.get_text(" ", strip=True)
                if 'софия' not in row_txt.lower():
                    continue
                if not any(w in row_txt.lower() for w in mp_electrical_keywords):
                    continue

                full_url = urllib.parse.urljoin('https://maistorplus.com', clean_href)

                # Fetch detail page to verify job is open & check for phone in description
                rj = session.get(full_url, headers=headers, timeout=9)
                if rj.status_code != 200:
                    continue
                sj = BeautifulSoup(rj.text, 'html.parser')
                for t_rem in sj(['script', 'style', 'nav', 'header', 'footer']):
                    t_rem.decompose()
                d_txt = sj.get_text(" ", strip=True)

                if "достигнат е максималният брой" in d_txt.lower() or "приключен" in d_txt.lower():
                    continue

                phones = extract_phone_numbers(d_txt)
                phone_val = phones[0] if phones else ""
                if not phone_val:
                    # Strict phone rule: skip if no direct phone number is available
                    continue

                title_clean = a_tag.get_text(" ", strip=True)[:80]
                results.append({
                    "id": job_id,
                    "title": f"[MaistorPlus] {title_clean}",
                    "description": d_txt[:350],
                    "url": full_url,
                    "source": "MaistorPlus",
                    "keyword": "Заявка за електро проект",
                    "category": "urgent_client",
                    "category_label": "🎯 Директна клиентска заявка (MaistorPlus)",
                    "location": "гр. София",
                    "phone": phone_val,
                    "found_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                })
        except Exception as e:
            print(f"  [MaistorPlus] Error on {ep}: {e}")

    return results


def scrape_daibau(max_pages=1):
    """
    Legacy compatibility wrapper: Daibau hides client phone numbers on public pages,
    so we only return items if a direct phone number is explicitly written in the text.
    """
    return []


def enrich_phones_for_leads(leads_list, max_to_fetch=20):
    """Fetches full page descriptions for classified ads to uncover direct phone numbers."""
    count = 0
    session = get_resilient_session(retries=2, backoff_factor=0.4)
    for item in leads_list:
        if item.get("phone"):
            continue
        if item.get("source") in ["MaistorPlus", "Daibau", "KSB", "Business.bg"]:
            continue
        if count >= max_to_fetch:
            break
        try:
            headers = get_browser_headers(referer=item.get("url"))
            r = session.get(item["url"], headers=headers, timeout=8)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser')
                text = soup.get_text(" ", strip=True)
                phones = extract_phone_numbers(text)
                if phones:
                    item["phone"] = phones[0]
                    print(f"   ↳ 📞 Намерен директен номер за '{item['title'][:35]}...': {item['phone']}")
            count += 1
            time.sleep(random.uniform(0.2, 0.5))
        except Exception:
            pass


def send_telegram_alert(lead, bot_token, chat_id):
    """
    Sends a richly formatted, phone-verified Telegram project card personalized for Amir (ZVB).
    Strictly blocks sending if the lead does not have a valid Bulgarian phone number!
    """
    if not bot_token or not chat_id:
        return False

    has_p, norm_p = lead_filter_engine.has_valid_bg_phone(lead)
    if not has_p:
        print(f"   [Skip Alert] Lead '{lead.get('title', '')[:40]}' has no valid phone number.")
        return False

    local_phone, intl_phone = normalize_bg_phone(lead.get("phone", ""))
    display_phone = lead.get("phone", local_phone or norm_p)

    tier_code, tier_badge = lead_filter_engine.calculate_project_value_tier(lead)
    est_budget = lead_filter_engine.estimate_project_budget(lead)
    amir_pitch = build_amir_pitch_for_lead(lead)

    mgr_line = f"👤 <b>Управител / Контакт:</b> {lead.get('manager')}\n" if lead.get("manager") else ""
    email_line = f"✉️ <b>Имейл:</b> <code>{lead.get('email')}</code>\n" if lead.get("email") else ""
    desc_snippet = lead.get("description", "").strip()
    desc_line = f"📝 <b>Описание:</b> <i>{desc_snippet[:220]}...</i>\n" if desc_snippet else ""

    text = (
        f"🚨 <b>НОВ ПРОЕКТ С ДИРЕКТЕН ТЕЛЕФОН В СОФИЯ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏷 <b>Клас:</b> {tier_badge}\n"
        f"📌 <b>Проект / Фирма:</b> {lead.get('title')}\n"
        f"{mgr_line}"
        f"📍 <b>Локация:</b> {lead.get('location')} | 🌐 <b>Източник:</b> {lead.get('source')}\n"
        f"💰 <b>Очакван обем:</b> <b>{est_budget}</b>\n"
        f"📞 <b>Директен телефон (Кликни за копиране):</b> <code>{display_phone}</code>\n"
        f"{email_line}"
        f"{desc_line}\n"
        f"💬 <b>Готово съобщение от името на Амир (Кликни за копиране):</b>\n"
        f"<code>{amir_pitch}</code>"
    )

    inline_kb = []
    if intl_phone:
        inline_kb.append([
            {"text": "💬 WhatsApp (с готов текст)", "url": f"https://wa.me/{intl_phone}?text={urllib.parse.quote(amir_pitch)}"},
            {"text": "🟣 Viber", "url": f"https://msng.link/o/?{intl_phone}=vi"}
        ])
    inline_kb.append([
        {"text": "🔗 Отвори източника", "url": lead.get("url", "https://zvb.bg")},
        {"text": "⏰ Напомни след 2ч", "callback_data": f"crm_rem2h_{lead.get('id')}"[:60]}
    ])
    inline_kb.append([
        {"text": "✅ Обадих се", "callback_data": f"crm_called_{lead.get('id')}"[:60]},
        {"text": "❌ Пропусни", "callback_data": f"crm_skip_{lead.get('id')}"[:60]}
    ])

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
        "reply_markup": {"inline_keyboard": inline_kb}
    }
    try:
        r = requests.post(url, json=payload, timeout=12)
        return r.status_code == 200
    except Exception as e:
        print(f"Telegram alert error: {e}")
        return False


def load_existing_leads():
    """
    Loads existing leads and automatically purges any old phantom leads without a valid phone number
    or older than 7 days so stale September/October items can never pollute the bot again!
    """
    raw_leads = {}
    if os.path.exists(LEADS_JSON_PATH):
        try:
            with open(LEADS_JSON_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    raw_leads.update(data)
        except Exception:
            pass

    clean_leads = {}
    for k, v in raw_leads.items():
        if not isinstance(v, dict):
            continue
        has_p, _ = lead_filter_engine.has_valid_bg_phone(v)
        fresh, _ = lead_filter_engine.is_within_time_window(v, max_days=7)
        closed, _ = lead_filter_engine.is_project_closed_or_expired(v)
        if has_p and fresh and not closed:
            clean_leads[k] = v

    if len(clean_leads) != len(raw_leads):
        save_leads(clean_leads)

    return clean_leads


def save_leads(leads_dict):
    with open(LEADS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(leads_dict, f, ensure_ascii=False, indent=2)

    try:
        import db_manager
        for k, v in leads_dict.items():
            if isinstance(v, dict):
                if not v.get("id"):
                    v["id"] = k
                db_manager.save_lead(v)
    except Exception:
        pass

    fieldnames = ["id", "category_label", "title", "phone", "location", "source", "keyword", "found_at", "url"]
    try:
        with open(LEADS_CSV_PATH, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for item in leads_dict.values():
                if isinstance(item, dict):
                    writer.writerow(item)
    except Exception:
        pass


def generate_dashboard(leads):
    """Generates the local HTML dashboard for desktop inspection."""
    leads_with_phone = [l for l in leads if lead_filter_engine.has_valid_bg_phone(l)[0]]
    count_all = len(leads_with_phone)
    html_out = f"""<!DOCTYPE html>
<html lang="bg">
<head>
<meta charset="UTF-8">
<title>ZVB Lead Radar v3.0 — Амир (Загрос Витоша България ЕООД)</title>
<style>
body {{ font-family: 'Segoe UI', sans-serif; background: #f8fafc; color: #0f172a; margin: 24px; }}
.card {{ background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 18px; margin-bottom: 14px; box-shadow: 0 2px 6px rgba(0,0,0,0.04); }}
.phone {{ font-size: 16px; font-weight: bold; color: #059669; background: #ecfdf5; padding: 4px 10px; border-radius: 6px; }}
.pitch {{ background: #f1f5f9; padding: 10px; border-radius: 8px; font-family: monospace; font-size: 13px; margin-top: 10px; }}
</style>
</head>
<body>
<h1>⚡ ZVB Lead & Project Radar v3.0 — Проекти с Директен Телефон ({count_all})</h1>
"""
    for l in leads_with_phone[:50]:
        pitch = build_amir_pitch_for_lead(l)
        html_out += f"""
<div class="card">
  <h3>{l.get('title')}</h3>
  <p>📍 <b>{l.get('location')}</b> | Източник: <b>{l.get('source')}</b> | 📞 <span class="phone">{l.get('phone')}</span></p>
  <p>{l.get('description', '')}</p>
  <div class="pitch">{pitch}</div>
</div>
"""
    html_out += "</body></html>"
    try:
        with open(DASHBOARD_HTML_PATH, "w", encoding="utf-8") as f:
            f.write(html_out)
    except Exception:
        pass


def run_scan():
    """
    Executes the full 5-Engine Sofia Project Scan:
    - Engine 1: Alo.bg Sofia Direct Client & Subcontractor Requests
    - Engine 2: Bazar.bg Sofia Electrical & Renovation Requests
    - Engine 3: MaistorPlus Open Sofia Tenders (with phone verification)
    - Engine 4: Business.bg Sofia Verified Builders, House Contractors, Renovation & MEP Firms
    - Engine 5: Official Chamber of Builders (КСБ - register.ksb.bg) Active 2025/2026 Sofia General Contractors & Zaplata.bg Active Sites
    """
    config = load_config()
    telegram_cfg = config.get("telegram", {})
    telegram_enabled = telegram_cfg.get("enabled", False)
    bot_token = telegram_cfg.get("bot_token", "")
    chat_id = telegram_cfg.get("chat_id", "")
    keywords = config.get("keywords", DEFAULT_KEYWORDS)

    print("=" * 68)
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 🚀 ZVB Ultimate Radar v3.0 (Small & Large Projects + Phone Guaranteed)")
    print("=" * 68)

    existing_leads = load_existing_leads()
    alert_history = lead_filter_engine.load_alert_history()
    candidates = []

    # 1. Alo.bg & Bazar.bg Direct Client & Subcontractor Queries in Sofia
    search_queries = list(set(keywords + [
        "търся електротехник софия",
        "подизпълнител софия строителство",
        "ремонт на ел инсталация софия",
        "смяна на ел табло софия"
    ]))
    print("\n🔍 [Engine 1 & 2] Scanning Alo.bg & Bazar.bg for direct Sofia projects...")
    for kw in search_queries[:6]:
        alo_items = scrape_alo(kw)
        bazar_items = scrape_bazar(kw)
        candidates.extend(alo_items)
        candidates.extend(bazar_items)

    # Enrich phones on newly found classifieds before filtering
    enrich_phones_for_leads(candidates, max_to_fetch=15)

    # 2. MaistorPlus Open Sofia Projects
    mp_cfg = config.get("maistorplus", {})
    if mp_cfg.get("enabled") and mp_cfg.get("username") and mp_cfg.get("password"):
        print("\n🔍 [Engine 3] Scanning MaistorPlus Sofia open tenders...")
        mp_items = scrape_maistorplus(mp_cfg["username"], mp_cfg["password"])
        candidates.extend(mp_items)

    # 3. Business.bg Verified Sofia Builders, Renovation & MEP Contractors (Small & Large Projects)
    print("\n🔍 [Engine 4] Scanning Business.bg Sofia (Turnkey Builders, Renovations, MEP)...")
    biz_items = scrape_business_bg_sofia(existing_leads, alert_history, max_new=3)
    print(f"   ↳ Found {len(biz_items)} new verified Sofia contractors with direct phones")
    candidates.extend(biz_items)

    # 4. Official Chamber of Builders (КСБ) Active 2025/2026 Sofia General Contractors & Zaplata Active Sites
    print("\n🔍 [Engine 5] Scanning Official Chamber of Builders (КСБ) & Zaplata Sofia active sites...")
    ksb_items = scrape_ksb_sofia_builders(existing_leads, alert_history, max_new=3)
    zap_items = scrape_zaplata_sofia_construction(existing_leads, alert_history, max_new=2)
    print(f"   ↳ Found {len(ksb_items)} KSB general contractors + {len(zap_items)} active construction sites with phones")
    candidates.extend(ksb_items)
    candidates.extend(zap_items)

    # Run all candidates through the 8-Layer Enterprise Filter (Strict Phone + Zero Duplicate)
    strict_new_leads = []
    for item in candidates:
        ok, reason, tier = lead_filter_engine.evaluate_lead(item, alert_history, require_phone=True)
        if ok:
            item["value_tier"] = tier
            existing_leads[item["id"]] = item
            strict_new_leads.append(item)
            # Add temporary entry to alert_history in-memory so duplicates within the same scan batch are caught
            alert_history[item["id"]] = {
                "id": item["id"],
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "phone": item.get("phone", ""),
                "alerted_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

    save_leads(existing_leads)

    # Dispatch Telegram alerts for newly verified leads (capped at 6 per scan cycle to avoid flooding)
    if telegram_enabled and bot_token and chat_id and strict_new_leads:
        print(f"\n📲 Sending {len(strict_new_leads[:6])} phone-verified new leads to Telegram...")
        for nl in strict_new_leads[:6]:
            sent_ok = send_telegram_alert(nl, bot_token, chat_id)
            if sent_ok:
                lead_filter_engine.record_alert_sent(nl, alert_history)
            time.sleep(0.8)
        lead_filter_engine.sync_git_history()

    sorted_leads = sorted(
        existing_leads.values(),
        key=lambda x: x.get("found_at", ""),
        reverse=True
    )
    generate_dashboard(sorted_leads)
    print(f"\n✅ Scan complete! Active phone-verified leads in database: {len(existing_leads)} (Newly alerted: {len(strict_new_leads[:6])})")
    return sorted_leads


def test_scraper_health():
    """Diagnostic health check across all 5 Sofia discovery engines."""
    report = {}
    engines = [
        ("KSB (Камара на строителите)", lambda: scrape_ksb_sofia_builders({}, {}, max_new=1)),
        ("Business.bg (Строители & Ремонти София)", lambda: scrape_business_bg_sofia({}, {}, max_new=2)),
        ("Alo.bg (София обяви)", lambda: scrape_alo("ремонт софия")),
        ("Bazar.bg (София обяви)", lambda: scrape_bazar("електротехник"))
    ]
    for name, fn in engines:
        t0 = time.time()
        try:
            items = fn()
            dt = round(time.time() - t0, 2)
            report[name] = {"status": "ONLINE ✅", "items": len(items), "latency_sec": dt}
        except Exception as e:
            dt = round(time.time() - t0, 2)
            report[name] = {"status": f"ERROR ❌ ({str(e)[:40]})", "items": 0, "latency_sec": dt}
    return report


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ZVB Ultimate Lead Radar v3.0")
    parser.add_argument("--interval", type=int, default=0, help="Auto-scan interval in minutes")
    parser.add_argument("--health", action="store_true", help="Run health check")
    args = parser.parse_args()

    if args.health:
        res = test_scraper_health()
        print(json.dumps(res, indent=2, ensure_ascii=False))
    elif args.interval > 0:
        while True:
            try:
                run_scan()
            except Exception as e:
                print(f"Error during scan: {e}")
            time.sleep(args.interval * 60)
    else:
        run_scan()
