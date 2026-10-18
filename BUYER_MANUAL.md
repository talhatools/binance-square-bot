# 📘 Binance Square Automated Posting Bot - Complete Commercial User & Buyer Manual
*Product Version: 2.0 Enterprise | Commercial License Documentation*

Welcome to the **Automated Binance Square Posting Bot**! This complete guide provides step-by-step instructions for beginners and advanced users on how to install, configure, operate, customize, and monetize this automated bot.

---

## 📑 Table of Contents
1. [Product Overview & Value Proposition](#1-product-overview--value-proposition)
2. [How It Works (Under The Hood)](#2-how-it-works-under-the-hood)
3. [Quick Setup for Windows (1-Click Method)](#3-quick-setup-for-windows-1-click-method)
4. [Complete PowerShell Command Reference](#4-complete-powershell-command-reference)
5. [API Keys Setup Guide (Step-by-Step)](#5-api-keys-setup-guide-step-by-step)
   - [How to get Binance Square OpenAPI Key](#how-to-get-binance-square-openapi-key)
   - [How to get Anthropic Claude API Key (Optional)](#how-to-get-anthropic-claude-api-key-optional)
   - [How to get Telegram Bot Alerts (Optional)](#how-to-get-telegram-bot-alerts-optional)
6. [Branding & Customization (Watermark, Time, Volume)](#6-branding--customization-watermark-time-volume)
7. [24/7 Cloud VPS Deployment (Ubuntu Linux)](#7-247-cloud-vps-deployment-ubuntu-linux)
8. [Error Codes & Troubleshooting Guide](#8-error-codes--troubleshooting-guide)
9. [اردو اور رومن اردو میں مکمل گائیڈ (Roman Urdu Complete Guide)](#9-اردو-اور-رومن-اردو-میں-مکمل-گائیڈ-roman-urdu-complete-guide)

---

## 1. Product Overview & Value Proposition

Binance Square is the fastest-growing crypto social platform with over 30 million active traders. Growing an audience on Binance Square manually takes hours of daily chart drawing and writing.

**What This Bot Does Automatically:**
- 🔍 **Scans 60+ High-Volume Crypto Coins** every 30 minutes from live Binance market data.
- 📐 **Computes Rule-Based Technical Setups**: RSI momentum, MA20/MA50 moving average crossovers, support/resistance breakout & rejection.
- 📊 **Renders Dark-Theme Candlestick Charts** with custom indicators, entry zones, targets, stop-losses, and your personal watermark/brand name.
- ✍️ **Drafts Mobile-Optimized Copy**: Coin cashtags (e.g. `$BTC`, `$SOL`), rationale, risk-to-reward ratio, and disclaimers.
- 🚀 **Publishes Directly to Binance Square** via the official OpenAPI with attached high-resolution images.
- 🛡️ **6-Hour Anti-Repetition Cooldown**: Ensures your followers never see the same coin spammed.
- 📈 **Tracks Signal Hit Rate**: Automatically verifies subsequent price candles to calculate your real win-rate % and profit/loss!

---

## 2. How It Works (Under The Hood)

Every cycle (default: every 30 minutes), the bot automatically executes:

1. **Market Scanner**: Connects to Binance public API (no trading key required) and filters liquid USDT pairs with $>=\$10M$ 24h volume.
2. **Deduplication Check**: Queries local SQLite database (`data/square_bot.db`) to ensure the coin hasn't been posted in the last 6 hours.
3. **Multi-Timeframe Engine**: Pulls 1-Hour and 4-Hour candlestick data. Identifies `LONG`, `SHORT`, or `NO_TRADE`. If the market is consolidating with poor risk-reward, it skips the cycle instead of forcing a bad post.
4. **Candlestick Image Generation**: Creates a high-definition PNG chart with yellow MA20, cyan MA50, green Support, red Resistance, dotted Target/Stop-Loss, and your brand watermark.
5. **AI Drafting**: Generates punchy, action-oriented trade setups under 600 characters ending with high-converting trade Call-to-Actions (CTAs) to drive trade executions.
6. **Binance Square OpenAPI Publication**: Requests an S3 upload ticket, uploads the image, polls processing, and publishes content.
7. **Signal Accuracy Tracking**: A secondary background worker checks open trades every 15 minutes to record `TARGET_HIT` or `STOP_HIT` with realized PnL %.

---

## 3. Quick Setup for Windows (1-Click Method)

For complete beginners, you do NOT need to type any code to run the bot:

### Step 1: Open the Bot Folder
Open `binance automation` on your Desktop.

### Step 2: Add Your Binance Square Key in `.env`
1. Open the `.env` file using **Notepad**.
2. Paste your Binance Square API key:
   ```env
   BINANCE_SQUARE_OPENAPI_KEY=your_key_here
   DRY_RUN=false
   ```
3. Save the file (**Ctrl + S**).

### Step 3: Run With 1 Click!
- **To start 24/7 Auto-Posting**: Double-click **`start_bot.bat`**.
- **To post just 1 signal immediately**: Double-click **`run.bat`**.
- **To view Win-Rate & Stats**: Double-click **`check_stats.bat`**.

---

## 4. Complete PowerShell Command Reference

If you prefer using the terminal, open PowerShell in the bot folder and use these commands:

| Command | What It Does | When To Use |
| :--- | :--- | :--- |
| `.\python main.py` | Starts continuous 24/7 background scheduler. | Use to let the bot run constantly while your PC is on. |
| `.\python main.py --run-once` | Executes 1 single scanning & posting cycle immediately, then stops. | Use to test or trigger manual posts on demand. |
| `.\python main.py --dry-run` | Runs in simulation mode (generates charts and text without posting). | Use when testing indicators without publishing to your account. |
| `.\python main.py --run-once --dry-run` | Tests 1 single cycle in simulation mode. | Best for testing new settings. |
| `.\python main.py --stats` | Displays historical win-rate %, total trades, target hits, and PnL %. | Use to inspect trading signal accuracy. |
| `.\python main.py --history` | Displays a table of the 15 most recent trades with prices, TP, SL, and status. | Use to view what the bot posted recently. |
| `.\python main.py --summary` | Prints today's total posts and coins handled. | Daily checkup. |
| `.\python main.py --track-signals` | Triggers immediate check of open signals against current market prices. | Updates pending trade outcomes. |
| `.\python scripts/health_check.py` | Runs diagnostic self-test of Binance API, SQLite, and Chart generator. | Use if you ever suspect internet or API issues. |
| `Get-Content .\logs\square_bot.log -Wait -Tail 30` | Streams live bot log output in real-time. | Use to watch what the bot is doing right now. |

> **Pro Tip**: You can also use `python` directly instead of `.\python` if Python is in your PATH.

---

## 5. API Keys Setup Guide (Step-by-Step)

### How to get Binance Square OpenAPI Key
1. Log into your account on [Binance.com](https://www.binance.com).
2. Go to **Square** -> Click on your profile icon -> **Creator Center**.
3. In the Creator Center sidebar, navigate to **OpenAPI / API Management**.
4. Click **Create API Key** and give it a label (e.g. `SquarePoster`).
5. **CRITICAL SECURITY NOTE**: Ensure the key only has **"Posting"** permission. Do **NOT** enable Trading, Futures, or Withdrawal permissions.
6. Copy the generated Key and paste it into `.env`:
   ```env
   BINANCE_SQUARE_OPENAPI_KEY=paste_key_here
   ```

### How to get Anthropic Claude API Key (Optional)
*Note: If you do not provide a Claude key, the bot uses its built-in smart technical template generator for free!*
1. Go to [console.anthropic.com](https://console.anthropic.com) and create an account.
2. Navigate to **API Keys** -> Click **Create Key**.
3. Copy the key and add it to `.env`:
   ```env
   ANTHROPIC_API_KEY=sk-ant-api03-...
   ```

### How to get Telegram Bot Alerts (Optional)
To receive instant alerts on your phone whenever the bot posts or hits a target:
1. Open Telegram and search for `@BotFather`.
2. Send `/newbot`, choose a name and username, and copy the **HTTP API Token**.
3. Search for `@userinfobot` on Telegram and send `/start` to get your **Chat ID**.
4. In `.env`, add:
   ```env
   TELEGRAM_BOT_TOKEN=123456789:ABCdef...
   TELEGRAM_CHAT_ID=your_chat_id
   ```

---

## 6. Branding & Customization (Watermark, Time, Volume)

All configuration is controlled from the `.env` file without touching any code:

```env
# 1. Custom Branding / Watermark on Charts
# Change this to your channel name, Twitter handle, or brand
WATERMARK_TEXT=Talha Sniper

# 2. Posting Frequency (in minutes)
# Default is 30 minutes (max 48 posts/day). Can be 15, 30, 45, 60, etc.
POST_INTERVAL_MINUTES=30

# 3. Minimum 24h Volume Filter (in USDT)
# Default is $10,000,000 to only trade liquid, safe crypto assets
MIN_24H_QUOTE_VOLUME=10000000

# 4. Deduplication Cooldown (in hours)
# A coin will not be posted again within this duration (Default: 6 hours)
COOLDOWN_HOURS=6

# 5. Live Mode vs Simulation Mode
# Set to false to publish to your real Binance account. Set to true for testing.
DRY_RUN=false
```

---

## 7. 24/7 Cloud VPS Deployment (Ubuntu Linux)

If you want the bot to run 24/7 even when your laptop is turned off, deploy it on an Ubuntu VPS ($4/month on DigitalOcean, Hetzner, Contabo, or AWS):

1. **Connect to your VPS via SSH**:
   ```bash
   ssh root@your_server_ip
   ```
2. **Upload or clone your bot folder**:
   ```bash
   cd /home/ubuntu
   git clone <your-repo> binance-automation
   cd binance-automation
   ```
3. **Run the 1-command installer**:
   ```bash
   bash scripts/setup_vps.sh
   ```
4. **Edit your credentials**:
   ```bash
   nano .env
   ```
5. **Start the background service**:
   ```bash
   sudo systemctl start binance-square-bot
   ```
6. **Check live status**:
   ```bash
   sudo systemctl status binance-square-bot
   tail -f logs/square_bot.log
   ```

The bot will now automatically start on server reboot and run 24/7 indefinitely!

---

## 8. Error Codes & Troubleshooting Guide

| Error Code / Issue | Cause | Solution |
| :--- | :--- | :--- |
| **`220003`** | API Key Not Found | Your Square API key in `.env` is incorrect or missing. Re-check `.env`. |
| **`220004`** | API Key Expired | Your Binance Square API key expired. Generate a fresh key in Creator Center. |
| **`220009`** | Daily Post Limit (100) Reached | Binance Square allows max 100 posts/day. The bot automatically halts gracefully until midnight UTC. |
| **`504 Gateway Timeout`** | Binance server heavy load | The bot automatically handles 504 without crashing; the post usually publishes within seconds. |
| **`Python was not found`** | PATH not loaded in old terminal | Close and re-open PowerShell, or simply double-click `start_bot.bat` or `run.bat`. |
| **No post generated** | Market in consolidation | The bot has a strict quality filter. If no coin has a clean $R:R \ge 1.4$ setup, it skips the cycle instead of forcing a bad post. |

---

---

## 9. اردو اور رومن اردو میں مکمل گائیڈ (Roman Urdu Complete Guide)

Agar aap ya aapka customer Roman Urdu mein samajhna chahta hai, to yeh section unke liye hai:

### 🌟 Yeh Bot Kya Karta Hai?
Yeh bot har 30 minute baad Binance market scan karta hai, sabse behtareen crypto coin dhoondhta hai, uska professional **dark-theme chart** banata hai (jisme aapka naam ya watermark laga hota hai), **Entry, Target aur Stop-Loss** calculate karta hai, aur automatic aapke **Binance Square** account par post kar deta hai!

---

### 🚀 Sirf 3 Steps Mein Bot Start Karein:

#### Step 1: Apni Keys `.env` File Mein Daalein
Folder ke andar `.env` file ko Notepad mein open karein aur yeh likhein:
```env
BINANCE_SQUARE_OPENAPI_KEY=yahan_apni_key_daalein
DRY_RUN=false
```
File ko Save (**Ctrl + S**) karein.

#### Step 2: Bot Ko Run Karein (1-Click)
- **24/7 Auto-Post Chalane Ke Liye:** **`start_bot.bat`** par **Double-Click** karein!
- **Sirf 1 Post Foran Karne Ke Liye:** **`run.bat`** par **Double-Click** karein!
- **Stats & History Dekhne Ke Liye:** **`check_stats.bat`** par **Double-Click** karein!

---

### 🛠️ PowerShell Commands List (Terminal Users Ke Liye):

Folder mein PowerShell open kar ke yeh commands chala sakte hain:

1. **Bot Ko 24/7 Chalanay Ke Liye:**
   ```powershell
   .\python main.py
   ```
2. **Sirf Ek Post Foran Publish Karne Ke Liye:**
   ```powershell
   .\python main.py --run-once
   ```
3. **Pichli Posts Ki Table / History Dekhne Ke Liye:**
   ```powershell
   .\python main.py --history
   ```
4. **Accuracy / Win-Rate Check Karne Ke Liye:**
   ```powershell
   .\python main.py --stats
   ```
5. **System Health Check / Diagnostics Chalane Ke Liye:**
   ```powershell
   .\python scripts/health_check.py
   ```

---

### ⚙️ Apni Marzi Ki Settings Kese Badlein? (`.env` File Se)
- **Apna Name / Watermark Badalne Ke Liye:**
  `.env` mein `WATERMARK_TEXT=Apna_Brand_Name` likhein.
- **Posting Ka Time Badalne Ke Liye:**
  `.env` mein `POST_INTERVAL_MINUTES=30` (Aap 15, 30, ya 60 kar sakte hain).
- **Test Mode ON/OFF Karne Ke Liye:**
  `DRY_RUN=true` (Sirf test karega, account par post nahi karega).  
  `DRY_RUN=false` (Real account par live post karega).

---

### 🛑 Bot Ko Band Kese Karna Hai?
Terminal window ko simply **Close (X)** kar dein ya keyboard par **`Ctrl + C`** daba dein.

---
*Commercial License Documentation - Ready for Resale and Distribution.*
