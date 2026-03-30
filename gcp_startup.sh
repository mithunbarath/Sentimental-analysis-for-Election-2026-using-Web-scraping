#!/bin/bash
# GCP VM Startup Script for Palladam Politics Scraper
# This script runs automatically every time the VM boots up.

# 1. Log all output to a dedicated file so you can debug via SSH if needed
exec > /var/log/scraper_startup.log 2>&1
echo "Starting Palladam Politics Scraper..."
date

# 2. Set the working directory to where you cloned the repo
# IMPORTANT: Change 'navee' or 'your-user' to your actual Linux username on the VM
PROJECT_DIR="/home/your-user/claude-brightdata-scraper"
cd $PROJECT_DIR || { echo "Directory not found!"; exit 1; }

# 3. Pull latest code (optional, but good for continuous updates)
# git pull origin main

# 4. Activate Python Virtual Environment (if you use one)
# source venv/bin/activate
# Or if using system Python, ensure dependencies are installed globally
# pip3 install -r requirements.txt

# 5. Run the scraper ONCE (no --infinite flag)
# We set a hard timeout (e.g., 60 minutes) to ensure it doesn't hang forever
echo "Running scraper..."
timeout 60m python3 main.py --cascade --scrapy --tn-wide --store-all --platforms all

# 6. Check exit status and sync
EXIT_CODE=$?
echo "Scraper finished with exit code: $EXIT_CODE"
sync

# 7. IMMEDIATELY SHUT DOWN THE VM TO SAVE MONEY
echo "Shutting down VM to cut costs..."
shutdown -h now
