#!/usr/bin/env python3
"""
Stable version of Neil Trading Signal Bot with robust connection handling
Includes auto-reconnection and better error recovery
"""

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
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from pathlib import Path
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor

# Force UTF-8 encoding for Windows
if sys.platform == 'win32':
    import codecs
    if sys.stdout.encoding != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if sys.stderr.encoding != 'utf-8':
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# ============================================================================
# CONFIGURATION
# ============================================================================

class Config:
    """Bot configuration"""

    def __init__(self, config_file: str = "config.json"):
        self.config_file = config_file
        self.load_config()

    def load_config(self):
        """Load configuration from JSON file"""
        if not Path(self.config_file).exists():
            print(f"ERROR: {self.config_file} not found!")
            print("Please create a config.json file with your settings")
            sys.exit(1)

        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except json.JSONDecodeError as e:
            print(f"ERROR: Invalid JSON in {self.config_file}: {e}")
            sys.exit(1)

        self.DISCORD_TOKEN = config.get("discord_token", "")
        self.GPT4_API_KEY = config.get("gpt4_api_key", "")
        self.CHANNEL_IDS = config.get("channel_ids", [])
        self.NEIL_USERNAMES = config.get("neil_usernames", ["Nurse Neil 💉 | Unity"])
        self.ALERT_TAGS = config.get("alert_tags", ["@Neilarora Alerts"])
        self.DATABASE_PATH = config.get("database_path", "signals.db")
        self.LOG_LEVEL = config.get("log_level", "INFO")
        self.MIN_CONFIDENCE = config.get("min_confidence", 0.7)

# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class TradingSignal:
    """Trading signal data structure"""
    signal_type: str  # LONG or SHORT
    ticker: str
    raw_message: str
    timestamp: datetime
    confidence: float
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit_1: Optional[float] = None
    take_profit_2: Optional[float] = None
    take_profit_3: Optional[float] = None
    leverage: Optional[str] = None
    notes: Optional[str] = None
    message_id: Optional[int] = None
    author: Optional[str] = None
    channel_id: Optional[int] = None

# ============================================================================
# DATABASE MANAGER
# ============================================================================

class DatabaseManager:
    """Handles all database operations"""

    def __init__(self, db_path: str = "signals.db"):
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        """Initialize database schema"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    signal_type TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    raw_message TEXT NOT NULL,
                    timestamp DATETIME NOT NULL,
                    confidence REAL NOT NULL,
                    entry_price REAL,
                    stop_loss REAL,
                    take_profit_1 REAL,
                    take_profit_2 REAL,
                    take_profit_3 REAL,
                    leverage TEXT,
                    notes TEXT,
                    message_id INTEGER,
                    author TEXT,
                    channel_id INTEGER
                )
            """)

            conn.commit()
            conn.close()
            logging.info(f"Database initialized at {self.db_path}")
        except sqlite3.Error as e:
            logging.error(f"Database initialization failed: {e}")
            raise

    def save_signal(self, signal: TradingSignal) -> int:
        """Save trading signal to database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO signals (
                    signal_type, ticker, raw_message, timestamp, confidence,
                    entry_price, stop_loss, take_profit_1, take_profit_2, take_profit_3,
                    leverage, notes, message_id, author, channel_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                signal.signal_type, signal.ticker, signal.raw_message,
                signal.timestamp.isoformat(), signal.confidence,
                signal.entry_price, signal.stop_loss,
                signal.take_profit_1, signal.take_profit_2, signal.take_profit_3,
                signal.leverage, signal.notes,
                signal.message_id, signal.author, signal.channel_id
            ))

            signal_id = cursor.lastrowid
            conn.commit()
            conn.close()

            logging.info(f"Signal saved: {signal.ticker} {signal.signal_type}")
            return signal_id
        except sqlite3.Error as e:
            logging.error(f"Failed to save signal: {e}")
            return -1

# ============================================================================
# SIGNAL DETECTOR
# ============================================================================

class SignalDetector:
    """Advanced signal detection with multiple patterns"""

    LONG_PATTERNS = [
        r"going\s+longs?\s+(?:on\s+)?(\$?[A-Z]{2,10})",
        r"longed\s+(?:on\s+)?(\$?[A-Z]{2,10})",
        r"(?:^|\s)long(?:ing)?\s+(\$?[A-Z]{2,10})",
        r"(\$?[A-Z]{2,10})\s+long",
        r"bought\s+(?:some\s+)?(?:spot\s+)?(\$?[A-Z]{2,10})",
        r"buying\s+(\$?[A-Z]{2,10})",
        r"long(?:ed|ing)?\s+(\$?[A-Z]{2,10})\s+here",
        r"(\$?[A-Z]{2,10})\s+long\s+here",
    ]

    SHORT_PATTERNS = [
        r"going\s+shorts?\s+(?:on\s+)?(\$?[A-Z]{2,10})",
        r"shorted\s+(?:on\s+)?(\$?[A-Z]{2,10})",
        r"(?:^|\s)short(?:ing)?\s+(\$?[A-Z]{2,10})",
        r"(\$?[A-Z]{2,10})\s+short",
        r"sold\s+(?:some\s+)?(\$?[A-Z]{2,10})",
        r"selling\s+(\$?[A-Z]{2,10})",
        r"short(?:ed|ing)?\s+(\$?[A-Z]{2,10})\s+here",
        r"(\$?[A-Z]{2,10})\s+short\s+here",
    ]

    def __init__(self):
        self.long_regex = [re.compile(p, re.IGNORECASE) for p in self.LONG_PATTERNS]
        self.short_regex = [re.compile(p, re.IGNORECASE) for p in self.SHORT_PATTERNS]

    def detect_signal(self, message_content: str) -> Optional[TradingSignal]:
        """Detect trading signal from message content"""

        # Check for LONG signals
        for pattern in self.long_regex:
            match = pattern.search(message_content)
            if match:
                ticker = match.group(1).replace('$', '').upper().strip()
                entry_type = "CMP" if re.search(r"\bat\s+cmp\b", message_content, re.IGNORECASE) else "MARKET"

                return TradingSignal(
                    signal_type="LONG",
                    ticker=ticker,
                    raw_message=message_content,
                    timestamp=datetime.now(),
                    confidence=0.9,
                    notes=entry_type
                )

        # Check for SHORT signals
        for pattern in self.short_regex:
            match = pattern.search(message_content)
            if match:
                ticker = match.group(1).replace('$', '').upper().strip()
                entry_type = "CMP" if re.search(r"\bat\s+cmp\b", message_content, re.IGNORECASE) else "MARKET"

                return TradingSignal(
                    signal_type="SHORT",
                    ticker=ticker,
                    raw_message=message_content,
                    timestamp=datetime.now(),
                    confidence=0.9,
                    notes=entry_type
                )

        return None

# ============================================================================
# STABLE BOT CLIENT
# ============================================================================

class StableNeilBot(discord.Client):
    """Stable Discord bot with robust connection handling"""

    def __init__(self, config: Config, *args, **kwargs):
        # Set intents
        intents = discord.Intents.default()
        intents.message_content = True
        intents.messages = True
        intents.guilds = True

        super().__init__(intents=intents, *args, **kwargs)

        self.config = config
        self.db = DatabaseManager(config.DATABASE_PATH)
        self.detector = SignalDetector()
        self.message_count = 0
        self.signal_count = 0
        self.last_heartbeat = time.time()
        self.executor = ThreadPoolExecutor(max_workers=1)

        # Chart extractor - optional
        self.chart_extractor = None
        try:
            if config.GPT4_API_KEY and config.GPT4_API_KEY != "YOUR_GPT4_API_KEY_HERE":
                from chart_extractor import ChartPriceExtractor
                self.chart_extractor = ChartPriceExtractor(gpt4_api_key=config.GPT4_API_KEY)
                logging.info("Chart extractor initialized")
        except Exception as e:
            logging.warning(f"Chart extractor not available: {e}")

        # Create temp directory
        self.temp_dir = Path("temp_charts")
        self.temp_dir.mkdir(exist_ok=True)

    async def on_ready(self):
        """Called when bot is ready"""
        self.last_heartbeat = time.time()
        logging.info(f"✓ Logged in as {self.user}")
        logging.info(f"✓ Monitoring {len(self.config.CHANNEL_IDS)} channels")

        print("\n" + "="*60)
        print("✅ STABLE NEIL BOT ACTIVE")
        print("="*60)
        print(f"📊 Monitoring {len(self.config.CHANNEL_IDS)} channels")
        print(f"👤 Tracking {len(self.config.NEIL_USERNAMES)} usernames")
        print(f"🤖 Chart Extraction: {'Enabled' if self.chart_extractor else 'Disabled'}")
        print("="*60)
        print("\n⏳ Waiting for signals...\n")

        # Start heartbeat monitor
        self.loop.create_task(self.heartbeat_monitor())

    async def heartbeat_monitor(self):
        """Monitor connection health"""
        while not self.is_closed():
            await asyncio.sleep(30)  # Check every 30 seconds

            time_since_heartbeat = time.time() - self.last_heartbeat
            if time_since_heartbeat > 120:  # No activity for 2 minutes
                logging.warning(f"No heartbeat for {time_since_heartbeat:.0f}s")

    async def on_message(self, message):
        """Process incoming messages"""
        try:
            self.last_heartbeat = time.time()
            self.message_count += 1

            # Skip if not in monitored channels
            if message.channel.id not in self.config.CHANNEL_IDS:
                return

            # Check if from Neil or has alert tag
            is_from_neil = any(username.lower() in message.author.name.lower()
                             for username in self.config.NEIL_USERNAMES)
            has_alert_tag = any(tag.lower() in message.content.lower()
                              for tag in self.config.ALERT_TAGS)

            if not (is_from_neil or has_alert_tag):
                return

            # Detect signal
            signal = self.detector.detect_signal(message.content)

            if signal:
                print(f"🔍 Signal detected from {message.author.name}")

                # Enrich signal
                signal.message_id = message.id
                signal.author = message.author.name
                signal.channel_id = message.channel.id

                # Process attachments if available
                if message.attachments and self.chart_extractor:
                    await self.process_chart_async(message, signal)

                # Save to database
                self.db.save_signal(signal)
                self.signal_count += 1

                # Print alert
                self.print_signal_alert(signal)

                # React to message
                try:
                    await message.add_reaction("👀")
                except:
                    pass

        except Exception as e:
            logging.error(f"Error processing message: {e}", exc_info=True)

    async def process_chart_async(self, message, signal):
        """Process chart images without blocking"""
        try:
            for attachment in message.attachments[:1]:  # Process first image only
                if not attachment.content_type or not attachment.content_type.startswith('image/'):
                    continue

                # Download image
                image_path = self.temp_dir / f"chart_{message.id}.png"

                async with aiohttp.ClientSession() as session:
                    async with session.get(attachment.url) as resp:
                        if resp.status == 200:
                            with open(image_path, 'wb') as f:
                                f.write(await resp.read())

                # Extract prices in background (with timeout)
                try:
                    loop = asyncio.get_event_loop()
                    result = await asyncio.wait_for(
                        loop.run_in_executor(
                            self.executor,
                            self.chart_extractor.extract_prices,
                            str(image_path),
                            signal.signal_type
                        ),
                        timeout=15  # 15 second timeout
                    )

                    # Update signal with extracted prices
                    if result.stop_loss:
                        signal.stop_loss = result.stop_loss
                    if result.take_profit_1:
                        signal.take_profit_1 = result.take_profit_1
                    if result.take_profit_2:
                        signal.take_profit_2 = result.take_profit_2
                    if result.take_profit_3:
                        signal.take_profit_3 = result.take_profit_3
                    if result.entry_price:
                        signal.entry_price = result.entry_price

                    if any([signal.stop_loss, signal.take_profit_1]):
                        print(f"✅ Extracted prices - SL: {signal.stop_loss} | TP1: {signal.take_profit_1}")

                except asyncio.TimeoutError:
                    logging.warning("Chart extraction timed out")

                # Clean up
                try:
                    os.remove(image_path)
                except:
                    pass

        except Exception as e:
            logging.error(f"Error processing chart: {e}")

    def print_signal_alert(self, signal: TradingSignal):
        """Print formatted signal alert"""
        type_emoji = "🟢" if signal.signal_type == "LONG" else "🔴"

        print(f"\n{'='*60}")
        print(f"🚨 {type_emoji} {signal.signal_type} SIGNAL - {signal.ticker}")
        print(f"{'='*60}")
        print(f"Time: {signal.timestamp.strftime('%H:%M:%S')}")
        print(f"Entry: {signal.notes if signal.notes else 'MARKET'}")

        if any([signal.entry_price, signal.stop_loss, signal.take_profit_1]):
            print(f"\n📊 PRICE LEVELS:")
            if signal.entry_price:
                print(f"  Entry:     ${signal.entry_price:,.4f}")
            if signal.stop_loss:
                print(f"  🛑 SL:     ${signal.stop_loss:,.4f}")
            if signal.take_profit_1:
                print(f"  🎯 TP1:    ${signal.take_profit_1:,.4f}")
            if signal.take_profit_2:
                print(f"  🎯 TP2:    ${signal.take_profit_2:,.4f}")
            if signal.take_profit_3:
                print(f"  🎯 TP3:    ${signal.take_profit_3:,.4f}")
        else:
            print(f"\n⚠️  NO PRICES EXTRACTED - Check Discord")

        print(f"{'='*60}\n")

    async def on_disconnect(self):
        """Called when bot disconnects"""
        logging.warning("Bot disconnected from Discord")

    async def close(self):
        """Cleanup on shutdown"""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=False)
        await super().close()

# ============================================================================
# MAIN RUNNER WITH AUTO-RESTART
# ============================================================================

async def run_bot_with_restart(config: Config, max_retries: int = 10):
    """Run bot with automatic restart on failure"""
    retry_count = 0

    while retry_count < max_retries:
        try:
            bot = StableNeilBot(config)

            # Run the bot
            await bot.start(config.DISCORD_TOKEN)

        except discord.errors.LoginFailure:
            print("ERROR: Invalid Discord token!")
            break

        except (discord.errors.ConnectionClosed,
                discord.errors.GatewayNotFound,
                aiohttp.ClientError) as e:
            retry_count += 1
            wait_time = min(60, 5 * retry_count)  # Exponential backoff, max 60s

            print(f"\n⚠️  Connection lost: {e}")
            print(f"🔄 Reconnecting in {wait_time}s... (Attempt {retry_count}/{max_retries})")
            logging.warning(f"Connection lost, reconnecting in {wait_time}s")

            # Clean up old bot
            try:
                await bot.close()
            except:
                pass

            await asyncio.sleep(wait_time)

        except KeyboardInterrupt:
            print("\n\n👋 Bot stopped by user")
            try:
                await bot.close()
            except:
                pass
            break

        except Exception as e:
            retry_count += 1
            print(f"\n❌ Error: {e}")
            logging.error(f"Unexpected error: {e}", exc_info=True)

            if retry_count < max_retries:
                wait_time = min(60, 5 * retry_count)
                print(f"🔄 Restarting in {wait_time}s... (Attempt {retry_count}/{max_retries})")
                await asyncio.sleep(wait_time)
            else:
                print(f"\n❌ Failed after {max_retries} attempts")
                break

    print("\n✅ Bot shutdown complete")

def setup_logging(log_level: str = "INFO"):
    """Setup logging configuration"""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('neil_bot.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

    # Suppress Discord's verbose logs
    for logger_name in ['discord', 'discord.http', 'discord.gateway']:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

def handle_shutdown(signum, frame):
    """Handle shutdown signals gracefully"""
    print("\n⏹️  Shutdown signal received...")
    sys.exit(0)

def main():
    """Main entry point"""
    print("\n" + "="*60)
    print("Starting Stable Neil Signal Bot v2.0")
    print("="*60)

    # Set up signal handlers
    signal.signal(signal.SIGINT, handle_shutdown)
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, handle_shutdown)

    # Load configuration
    config = Config()

    # Setup logging
    setup_logging(config.LOG_LEVEL)

    # Validate token
    if not config.DISCORD_TOKEN or config.DISCORD_TOKEN == "YOUR_DISCORD_TOKEN_HERE":
        print("\nERROR: Discord token not configured!")
        print("Please edit config.json and add your Discord token")
        sys.exit(1)

    print("\n🚀 Starting bot with auto-reconnection...")
    print("Press Ctrl+C to stop\n")

    # Run the bot with restart capability
    try:
        asyncio.run(run_bot_with_restart(config, max_retries=10))
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        logging.error("Fatal error", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()