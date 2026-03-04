#!/usr/bin/env python3
"""Neil Trading Signal Bot"""

import discord
import re
import json
import sqlite3
import asyncio
import time
import signal
import sys
import os
import aiohttp
import logging
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# Fix Windows encoding
if sys.platform == 'win32':
    if sys.stdout.encoding != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if sys.stderr.encoding != 'utf-8':
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')


# ── Load config.json ──

def load_config():
    if not Path("config.json").exists():
        print("\n❌ config.json not found.")
        print("   Copy config.example.json to config.json and fill in your details.\n")
        sys.exit(1)
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"\n❌ config.json has a formatting error: {e}\n")
        sys.exit(1)


# ── Database (saves every signal) ──

def init_db(path):
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT, ticker TEXT, message TEXT,
            time TEXT, entry REAL, stop_loss REAL,
            tp1 REAL, tp2 REAL, tp3 REAL,
            author TEXT, channel_id INTEGER
        )
    """)
    conn.commit()
    conn.close()

def save_signal(path, sig):
    conn = sqlite3.connect(path)
    conn.execute(
        "INSERT INTO signals (type,ticker,message,time,entry,stop_loss,tp1,tp2,tp3,author,channel_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (sig["type"], sig["ticker"], sig["message"], sig["time"],
         sig.get("entry"), sig.get("stop_loss"),
         sig.get("tp1"), sig.get("tp2"), sig.get("tp3"),
         sig.get("author"), sig.get("channel_id"))
    )
    conn.commit()
    conn.close()


# ── Detect BUY/SELL from message text ──

BUY_PATTERNS = [
    r"going\s+longs?\s+(?:on\s+)?(\$?[A-Z]{2,10})",
    r"longed\s+(?:on\s+)?(\$?[A-Z]{2,10})",
    r"(?:^|\s)long(?:ing)?\s+(\$?[A-Z]{2,10})",
    r"(\$?[A-Z]{2,10})\s+long",
    r"bought\s+(?:some\s+)?(?:spot\s+)?(\$?[A-Z]{2,10})",
    r"buying\s+(\$?[A-Z]{2,10})",
    r"long(?:ed|ing)?\s+(\$?[A-Z]{2,10})\s+here",
    r"(\$?[A-Z]{2,10})\s+long\s+here",
]

SELL_PATTERNS = [
    r"going\s+shorts?\s+(?:on\s+)?(\$?[A-Z]{2,10})",
    r"shorted\s+(?:on\s+)?(\$?[A-Z]{2,10})",
    r"(?:^|\s)short(?:ing)?\s+(\$?[A-Z]{2,10})",
    r"(\$?[A-Z]{2,10})\s+short",
    r"sold\s+(?:some\s+)?(\$?[A-Z]{2,10})",
    r"selling\s+(\$?[A-Z]{2,10})",
    r"short(?:ed|ing)?\s+(\$?[A-Z]{2,10})\s+here",
    r"(\$?[A-Z]{2,10})\s+short\s+here",
]

BUY_REGEX = [re.compile(p, re.IGNORECASE) for p in BUY_PATTERNS]
SELL_REGEX = [re.compile(p, re.IGNORECASE) for p in SELL_PATTERNS]

def detect_signal(text):
    for p in BUY_REGEX:
        m = p.search(text)
        if m:
            return "BUY", m.group(1).replace("$", "").upper().strip()
    for p in SELL_REGEX:
        m = p.search(text)
        if m:
            return "SELL", m.group(1).replace("$", "").upper().strip()
    return None, None


# ── Print a signal to the terminal ──

def show_signal(sig):
    icon = "🟢" if sig["type"] == "BUY" else "🔴"
    print(f"\n{'─'*40}")
    print(f"  {icon} {sig['type']}  {sig['ticker']}   ({sig['time']})")
    print(f"{'─'*40}")
    if sig.get("entry"):
        print(f"  Entry:      ${sig['entry']:,.4f}")
    if sig.get("stop_loss"):
        print(f"  Stop Loss:  ${sig['stop_loss']:,.4f}")
    if sig.get("tp1"):
        print(f"  Target 1:   ${sig['tp1']:,.4f}")
    if sig.get("tp2"):
        print(f"  Target 2:   ${sig['tp2']:,.4f}")
    if sig.get("tp3"):
        print(f"  Target 3:   ${sig['tp3']:,.4f}")
    if not any([sig.get("entry"), sig.get("stop_loss"), sig.get("tp1")]):
        print("  No prices found - check Discord for details.")
    print(f"{'─'*40}\n")


# ── Read prices from chart images (optional, needs GPT-4 key) ──

def try_read_chart(image_path, trade_type, extractor, executor):
    """Returns dict of prices or empty dict"""
    if not extractor:
        return {}
    try:
        loop = asyncio.get_event_loop()
        result = asyncio.ensure_future(asyncio.wait_for(
            loop.run_in_executor(executor, extractor.extract_prices, str(image_path), trade_type),
            timeout=15
        ))
        return result
    except Exception:
        return {}


# ── The bot ──

class Bot(discord.Client):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.db_path = config.get("database_path", "signals.db")
        self.channels = config.get("channel_ids", [])
        self.usernames = [u.lower() for u in config.get("neil_usernames", [])]
        self.alert_tags = [t.lower() for t in config.get("alert_tags", [])]
        self.executor = ThreadPoolExecutor(max_workers=1)

        # Chart reader (optional)
        self.chart_extractor = None
        api_key = config.get("gpt4_api_key", "")
        if api_key and api_key != "YOUR_GPT4_API_KEY_HERE":
            try:
                from chart_extractor import ChartPriceExtractor
                self.chart_extractor = ChartPriceExtractor(gpt4_api_key=api_key)
            except Exception:
                pass

        self.temp_dir = Path("temp_charts")
        self.temp_dir.mkdir(exist_ok=True)
        init_db(self.db_path)

    async def on_ready(self):
        print("\n✅ Bot is ON and watching for signals.")
        print("   Press Ctrl+C to stop.\n")

    async def on_message(self, message):
        try:
            # Only watch our channels
            if message.channel.id not in self.channels:
                return

            # Only listen to Neil or alert tags
            name = message.author.name.lower()
            text = message.content
            is_neil = any(u in name for u in self.usernames)
            is_alert = any(t in text.lower() for t in self.alert_tags)
            if not (is_neil or is_alert):
                return

            # Check for a trade signal
            trade_type, ticker = detect_signal(text)
            if not trade_type:
                return

            sig = {
                "type": trade_type,
                "ticker": ticker,
                "message": text,
                "time": datetime.now().strftime("%H:%M:%S"),
                "author": message.author.name,
                "channel_id": message.channel.id,
            }

            # Try to read prices from chart image
            if message.attachments and self.chart_extractor:
                for att in message.attachments[:1]:
                    if att.content_type and att.content_type.startswith("image/"):
                        img = self.temp_dir / f"chart_{message.id}.png"
                        async with aiohttp.ClientSession() as s:
                            async with s.get(att.url) as r:
                                if r.status == 200:
                                    with open(img, "wb") as f:
                                        f.write(await r.read())
                        try:
                            loop = asyncio.get_event_loop()
                            result = await asyncio.wait_for(
                                loop.run_in_executor(
                                    self.executor,
                                    self.chart_extractor.extract_prices,
                                    str(img), trade_type
                                ),
                                timeout=15
                            )
                            if result.entry_price:
                                sig["entry"] = result.entry_price
                            if result.stop_loss:
                                sig["stop_loss"] = result.stop_loss
                            if result.take_profit_1:
                                sig["tp1"] = result.take_profit_1
                            if result.take_profit_2:
                                sig["tp2"] = result.take_profit_2
                            if result.take_profit_3:
                                sig["tp3"] = result.take_profit_3
                        except Exception:
                            pass
                        try:
                            os.remove(img)
                        except Exception:
                            pass

            # Show it and save it
            show_signal(sig)
            save_signal(self.db_path, sig)

            try:
                await message.add_reaction("👀")
            except Exception:
                pass

        except Exception as e:
            logging.error(f"Error: {e}", exc_info=True)

    async def close(self):
        self.executor.shutdown(wait=False)
        await super().close()


# ── Start the bot ──

def main():
    # Logging goes to file only (keeps terminal clean)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(message)s",
        handlers=[logging.FileHandler("neil_bot.log", encoding="utf-8")],
    )
    for name in ["discord", "discord.http", "discord.gateway"]:
        logging.getLogger(name).setLevel(logging.WARNING)

    # Handle Ctrl+C
    signal.signal(signal.SIGINT, lambda *_: (print("\n👋 Bot stopped."), sys.exit(0)))

    # Load settings
    config = load_config()
    token = config.get("discord_token", "")
    if not token or token == "YOUR_DISCORD_TOKEN_HERE":
        print("\n❌ No Discord token found.")
        print('   Open config.json and paste your token next to "discord_token".\n')
        sys.exit(1)

    # Run with auto-reconnect
    print("\n🚀 Starting bot...")
    retries = 0
    while retries < 10:
        try:
            bot = Bot(config)
            bot.run(token)
            break
        except discord.errors.LoginFailure:
            print("\n❌ Wrong Discord token. Check config.json and try again.")
            break
        except KeyboardInterrupt:
            print("\n👋 Bot stopped.")
            break
        except Exception:
            retries += 1
            wait = min(60, 5 * retries)
            print(f"\n⚠️  Lost connection. Reconnecting in {wait}s...")
            time.sleep(wait)

    if retries >= 10:
        print("\n❌ Too many errors. Check neil_bot.log for details.")
    print("\nBot is off.")


if __name__ == "__main__":
    main()
