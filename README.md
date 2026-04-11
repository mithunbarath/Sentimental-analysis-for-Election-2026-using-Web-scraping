# Kongu Political Intelligence Engine

A comprehensive, multi-platform social media scraping and sentiment analysis pipeline specifically designed for political intelligence gathering in the Tamil Nadu / Kongu region.

## Overview

The Kongu Political Intelligence Engine automates the extraction, enrichment, and storage of political sentiments across major social media platforms. By analyzing posts and comments from Instagram, Facebook, X (Twitter), and YouTube, the engine continuously feeds real-time intelligence into analytical dashboards.

## Core Features

- **Multi-Platform Support**: Scrape public posts and deeply nested comments from Instagram, Facebook, Twitter, and YouTube.
- **Hybrid Scraper Cascade**: Bypasses limitations using API-based solutions (Apify, Firecrawl, BrightData) as primary, falling back to native Playwright/Scrapling stealth multi-account rotation seamlessly.
- **Geographic & Keyword Filtering**: Tailored to focus dynamically on specific districts (e.g., Coimbatore, Tiruppur, Salem) or Broad TN regional political keywords.
- **NLP Enrichment**: Integrated NLP module tags records with sentiment scores and extracts politically relevant entities.
- **Robust Deduplication**: Advanced record deduplication with exact ID matching and fuzzy text logic, supported by local JSON tracking or Redis.
- **Multiple Data Synchronizations**: Automatically exports cleaned data to local CSV/JSONL, Google Sheets, Firebase (Firestore), and MongoDB for seamless dashboard integrations.
- **Continuous Mode**: Features an `--infinite` scraping execution mode for 24/7 intelligence generation.
- **Target Profiles**: Provides deep targeted extraction from specific profile URLs to break down individual political narratives.

## Prerequisites

- **Python 3.8+** (Built and verified on Windows environment with pro-actor event loops)
- Supported browser binaries (Installed via Playwright)
- Database credentials depending on the needed integrations (Firebase Admin JSON, MongoDB URI, or Google Service accounts).

## Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd claude-brightdata-scraper
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   playwright install
   ```

3. **Environment Setup:**
   Create a `.env` file in the root directory for API and database credentials. See `config.yaml` for the structured configuration variables required.
   
## Configuration

Review and adjust the `config.yaml` file natively. Parameters include:
- `enable_which_platforms`: Specify which social platforms to run natively.
- `keywords`: Include Broad or Kongu-specific search queries.
- `nlp`: Enable sentiment processing.
- `infinite_mode`: Define delays and limits between scraping cascades.
- `google_sheets` / `firebase` / `mongodb`: Set up respective database integrations.

## Usage Guide

You can run the scraper manually or fully automated via the extensive command-line interface. 

### 1. Initial Authentication (Login Mode)
Login walls can be bypassed by logging into active browser sessions the scraper will subsequently reuse.
```powershell
# Authenticate on platforms individually
python main.py --login instagram
python main.py --login facebook
```

### 2. General Scraping
Run a scrape cycle based on keywords and enabled platforms defined in your `config.yaml`.
```powershell
python main.py --platforms all --verbose 
```

### 3. Targeted Infinite Feed Setup
Run continuously across all configured platforms, using the cascade fallbacks to avoid blocks.
```powershell
python main.py --platforms all --infinite --delay 10 --cascade --verbose
```

### 4. Direct Profile Target
Ideal for deeply extracting the sentiment surrounding a specific politician or party's public page natively via Instagram.
```powershell
python main.py --profile "https://www.instagram.com/account_name/" --profile-limit 50
```

### 5. Cross-Platform Multi-Targeting
Execute an orchestrated extraction across cross-platform profiles (Instagram, Twitter, YouTube) tied explicitly to a politician's name. The scraper handles all links provided and saves everything natively merged to an individual CSV.
```powershell
python main.py --politician "MK Stalin" --profiles "https://www.instagram.com/mkstalin" "https://twitter.com/mkstalin" "https://www.youtube.com/@mkstalin"
```

### 6. District-Specific Targeting
Filter and focus explicitly on regional data to isolate relevant public sentiment.
```powershell
python main.py --platforms facebook instagram --district "Coimbatore" --store-all
```

## Output Structure

The processed data routes to the sources you dictate in `config.yaml`, structurally categorized as `SocialMediaRecord`s. 

Local files get deployed in the `output/` directory:
- `*_data.csv` (General and Region Specific)
- `*_data.jsonl`
- Targeted profile outputs correspond dynamically to the profile slug name (e.g., `target_profile.csv`).

## Troubleshooting & Verification

- **Browser TargetClosedError**: Active zombie sessions are the primary cause. Force clear chrome tasks:
  *Windows:* `taskkill /F /IM chrome.exe /T`
- **Data Deduplication Overreach**: If limits are met unexpectedly fast, clear your `.deduplication_state.json` file.
