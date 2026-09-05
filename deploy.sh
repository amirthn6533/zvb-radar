#!/bin/bash
# ZVB Radar 1-Click Cloud Deployment Script for Ubuntu / Debian

echo "=========================================================="
echo "      ZVB Radar 24/7 Cloud Deployment Setup"
echo "=========================================================="

# 1. Update packages and install python
apt-get update -y
apt-get install -y python3 python3-pip tzdata git

# 2. Set timezone to Sofia, Bulgaria
timedatectl set-timezone Europe/Sofia

# 3. Install python dependencies
pip3 install -r requirements.txt

# 4. Setup Systemd Service
cp zvb-radar.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable zvb-radar
systemctl restart zvb-radar

echo ""
echo "=========================================================="
echo "✅ ZVB Radar 24/7 با موفقیت روی سرور نصب و فعال شد!"
echo "بررسی وضعیت با دستور: systemctl status zvb-radar"
echo "مشاهده لاگ‌ها با دستور: journalctl -u zvb-radar -f"
echo "=========================================================="
