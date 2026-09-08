# ⚡ ZVB Radar & Autonomous Lead Engine

<div align="center">

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Telegram](https://img.shields.io/badge/Telegram_Bot-24/7-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)
![Status](https://img.shields.io/badge/Deployment-GitHub_Actions_24/7-blue?style=for-the-badge&logo=github-actions&logoColor=white)
![Location](https://img.shields.io/badge/Location-Sofia,_Bulgaria-red?style=for-the-badge)

**Autonomous multi-platform lead radar, intelligent qualification filter, and interactive Telegram assistant for electrical engineering and smart building systems in Sofia, Bulgaria.**

[Overview](#-overview) • [Core Features](#-core-features) • [Architecture](#-system-architecture) • [Quick Start](#-quick-start) • [Configuration](#-configuration) • [License](#-license)

</div>

---

## 📌 Overview

**ZVB Radar** is an enterprise-grade automated lead generation and management pipeline built for **Загрос Витоша България ЕООД (ZVB)**. It continuously monitors Bulgarian service marketplaces, detects high-intent electrical installation and smart home inquiries, filters noise using a 7-layer verification engine, and delivers actionable instant alerts to Telegram with 1-click WhatsApp and call triggers.

---

## 🚀 Core Features

### 1. 📡 Multi-Platform Resilient Scraper
- **Continuous Radar Sweeps:** Automated scanning across **MaistorPlus**, **Bazar.bg**, **Alo.bg**, and **Daibau.bg**.
- **Anti-Blocking Architecture:** Resilient HTTP sessions with exponential backoff retries, dynamic browser headers (`Sec-Ch-Ua`, `User-Agent` rotation), and adaptive fallback HTML selectors.
- **Sofia Geo-Targeting:** Automatic extraction of districts, street names, and postal regions within Sofia.

### 2. 🛡️ 7-Layer Enterprise Qualification Filter
- **Deduplication:** Cross-platform fingerprinting ensuring duplicate listings are never alerted twice.
- **Fuzzy Similarity (>80%):** Filters out repackaged or reposted ads from competing contractors.
- **Freshness Gate (<14 Days):** Automatically rejects stale or expired tenders.
- **Value Tier Classification:** Identifies high-budget and enterprise opportunities with VIP badges.

### 3. 🤖 Interactive Telegram Assistant (Zagros AI)
- **Instant Alerts:** Real-time push notifications featuring direct client phone numbers, WhatsApp links, and lead source.
- **📑 1-Click PDF Invoices (`/pdf`):** Generates official branded Bulgarian PDF quotation documents on ZVB letterhead with price breakdowns.
- **💰 Smart Market Calculator (`/calc`):** Live Sofia labor & material cost estimation for wiring, circuit breaker boards, CCTV, and smart switches.
- **📱 Facebook Lead Hunter (`/fb`):** Generates persuasive, professional Bulgarian pitch replies for social media contractor requests.
- **🏗️ B2B Partner Directory (`/builders`, `/designers`):** Instant access to top construction firms (KSB) and interior design studios.
- **🩺 Diagnostic Health Probe (`/health`):** Live latency and availability check across all target platforms.

---

## 🏗️ System Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│                    Target Platforms                         │
│   Bazar.bg  │  Alo.bg  │  MaistorPlus.com  │  Daibau.bg     │
└───────────────┬─────────────────────────────────────────────┘
                │ Resilient Scraper Engine
                ▼
┌─────────────────────────────────────────────────────────────┐
│               7-Layer Qualification Filter                  │
│  • Deduplication  • Freshness  • Sofia Geo-Radius           │
│  • Intent Scorer  • Phone Extractor  • Value Tier           │
└───────────────┬─────────────────────────────────────────────┘
                │ Qualified High-Intent Leads
                ▼
┌─────────────────────────────────────────────────────────────┐
│               ZVB Telegram Bot & Workflow                   │
│  • Push Alerts    • WhatsApp Links   • Interactive Menu     │
│  • PDF Quotes     • Price Calculator • Zagros AI Brain      │
└─────────────────────────────────────────────────────────────┘
```

---

## ⚡ Quick Start

### Prerequisites
- Python 3.10+
- Telegram Bot Token & Chat ID

### Installation
```bash
# 1. Clone the repository
git clone https://github.com/amirthn6533/zvb-radar.git
cd zvb-radar

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure credentials
cp config.example.json config.json
# Edit config.json with your Telegram token and credentials

# 4. Run diagnostic health check
python lead_scraper.py --test

# 5. Start the interactive Telegram assistant
python telegram_bot_service.py
```

---

## 🔐 Configuration

Copy `config.example.json` to `config.json` and provide your settings:

```json
{
  "gemini_api_key": "YOUR_GEMINI_API_KEY",
  "telegram": {
    "enabled": true,
    "bot_token": "YOUR_TELEGRAM_BOT_TOKEN",
    "chat_id": "YOUR_CHAT_ID"
  },
  "maistorplus": {
    "enabled": true,
    "username": "YOUR_EMAIL",
    "password": "YOUR_PASSWORD"
  },
  "search_settings": {
    "prioritize_sofia": true,
    "notify_new_leads_only": true
  }
}
```

---

## 📊 Automated Cloud Deployment

This project includes automated **GitHub Actions** workflows:
- **`zagros-bot.yml`**: Runs the interactive Telegram assistant continuously in cloud sessions.
- **`zvb_radar.yml`**: Scheduled 15-minute cron runner generating digest alerts and database syncs.

---

## 📄 License

This project is open-source and licensed under the [MIT License](LICENSE).

---

<div align="center">
  <sub>Developed by <b>Amir</b> for <b>Загрос Витоша България ЕООД</b> • <a href="https://zvb.bg">zvb.bg</a></sub>
</div>
