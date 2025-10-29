"""
Advanced Neil Trading Signal Bot
Monitors Discord messages for trading signals with enhanced detection and logging

⚠️ WARNING: This uses discord.py-self which violates Discord's Terms of Service.
Use at your own risk. Your account may be banned.
"""

import discord
import re
import json
import sqlite3
import asyncio
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from pathlib import Path
import logging
from dataclasses import dataclass, asdict
import sys
import os
import aiohttp
from concurrent.futures import ThreadPoolExecutor

# Force UTF-8 encoding environment variable for Windows
if sys.platform == 'win32':
    import codecs
    if sys.stdout.encoding != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if sys.stderr.encoding != 'utf-8':
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Chart extractor will be lazy-loaded when needed to avoid blocking startup
CHART_EXTRACTOR_AVAILABLE = True  # Assume available, will check on first use
ChartPriceExtractor = None  # Will be imported when needed

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
            self.create_default_config()

        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except json.JSONDecodeError as e:
            print(f"ERROR: Invalid JSON in {self.config_file}: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"ERROR: Failed to load config file: {e}")
            sys.exit(1)

        self.DISCORD_TOKEN = config.get("discord_token", "")
        self.GPT4_API_KEY = config.get("gpt4_api_key", "")
        self.CHANNEL_IDS = config.get("channel_ids", [])
        self.NEIL_USERNAMES = config.get("neil_usernames", ["Nurse Neil 💉 | Unity"])
        self.ALERT_TAGS = config.get("alert_tags", ["@Neilarora Alerts"])
        self.WEBHOOK_URL = config.get("webhook_url", "")
        self.DATABASE_PATH = config.get("database_path", "signals.db")
        self.LOG_LEVEL = config.get("log_level", "INFO")
        self.ENABLE_NOTIFICATIONS = config.get("enable_notifications", True)
        self.MIN_CONFIDENCE = config.get("min_confidence", 0.7)

        # Validate required fields
        if not self.CHANNEL_IDS:
            print("WARNING: No channel IDs configured in config.json")
        if not self.NEIL_USERNAMES:
            print("WARNING: No Neil usernames configured in config.json")

    def create_default_config(self):
        """Create default configuration file"""
        default_config = {
            "discord_token": "YOUR_DISCORD_TOKEN_HERE",
            "channel_ids": [123456789],
            "neil_usernames": ["Nurse Neil 💉 | Unity"],
            "alert_tags": ["@Neilarora Alerts"],
            "webhook_url": "",
            "database_path": "signals.db",
            "log_level": "INFO",
            "enable_notifications": True,
            "min_confidence": 0.7
        }

        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=4, ensure_ascii=False)

        print(f"Created default config file: {self.config_file}")
        print("Please edit the config file with your Discord token and channel IDs")
        sys.exit(1)

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
    dca_levels: Optional[List[float]] = None
    notes: Optional[str] = None  # Used to store entry type (CMP or MARKET)
    message_id: Optional[int] = None
    author: Optional[str] = None
    channel_id: Optional[int] = None

    def to_dict(self):
        """Convert to dictionary"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data

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

            # Create signals table
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
                    dca_levels TEXT,
                    notes TEXT,
                    message_id INTEGER,
                    author TEXT,
                    channel_id INTEGER
                )
            """)

            # Create performance tracking table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    signal_id INTEGER,
                    outcome TEXT,
                    profit_loss REAL,
                    close_timestamp DATETIME,
                    notes TEXT,
                    FOREIGN KEY (signal_id) REFERENCES signals(id)
                )
            """)

            # Create statistics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS statistics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE NOT NULL,
                    total_signals INTEGER DEFAULT 0,
                    long_signals INTEGER DEFAULT 0,
                    short_signals INTEGER DEFAULT 0,
                    avg_confidence REAL DEFAULT 0
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

            dca_levels_json = json.dumps(signal.dca_levels) if signal.dca_levels else None

            cursor.execute("""
                INSERT INTO signals (
                    signal_type, ticker, raw_message, timestamp, confidence,
                    entry_price, stop_loss, take_profit_1, take_profit_2, take_profit_3,
                    leverage, dca_levels, notes, message_id, author, channel_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                signal.signal_type, signal.ticker, signal.raw_message,
                signal.timestamp.isoformat(), signal.confidence,
                signal.entry_price, signal.stop_loss,
                signal.take_profit_1, signal.take_profit_2, signal.take_profit_3,
                signal.leverage, dca_levels_json, signal.notes,
                signal.message_id, signal.author, signal.channel_id
            ))

            signal_id = cursor.lastrowid
            conn.commit()
            conn.close()

            logging.info(f"Signal saved to database: {signal.ticker} {signal.signal_type}")
            return signal_id
        except sqlite3.Error as e:
            logging.error(f"Failed to save signal to database: {e}")
            return -1

    def get_recent_signals(self, limit: int = 10) -> List[TradingSignal]:
        """Get recent signals from database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM signals
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))

            rows = cursor.fetchall()
            conn.close()

            # Convert rows to TradingSignal objects
            signals = []
            for row in rows:
                try:
                    dca_levels = json.loads(row[12]) if row[12] else None
                    signal = TradingSignal(
                        signal_type=row[1],
                        ticker=row[2],
                        raw_message=row[3],
                        timestamp=datetime.fromisoformat(row[4]),
                        confidence=row[5],
                        entry_price=row[6],
                        stop_loss=row[7],
                        take_profit_1=row[8],
                        take_profit_2=row[9],
                        take_profit_3=row[10],
                        leverage=row[11],
                        dca_levels=dca_levels,
                        notes=row[13],
                        message_id=row[14],
                        author=row[15],
                        channel_id=row[16]
                    )
                    signals.append(signal)
                except (ValueError, json.JSONDecodeError) as e:
                    logging.warning(f"Skipping malformed signal row: {e}")
                    continue

            return signals
        except sqlite3.Error as e:
            logging.error(f"Failed to retrieve signals from database: {e}")
            return []

    def get_statistics(self, days: int = 7) -> Dict:
        """Get trading statistics"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN signal_type = 'LONG' THEN 1 ELSE 0 END) as longs,
                    SUM(CASE WHEN signal_type = 'SHORT' THEN 1 ELSE 0 END) as shorts,
                    AVG(confidence) as avg_confidence
                FROM signals
                WHERE timestamp >= datetime('now', '-' || ? || ' days')
            """, (days,))

            row = cursor.fetchone()
            conn.close()

            return {
                'total_signals': row[0] or 0,
                'long_signals': row[1] or 0,
                'short_signals': row[2] or 0,
                'avg_confidence': round(row[3] or 0, 2)
            }
        except sqlite3.Error as e:
            logging.error(f"Failed to retrieve statistics from database: {e}")
            return {
                'total_signals': 0,
                'long_signals': 0,
                'short_signals': 0,
                'avg_confidence': 0
            }

# ============================================================================
# SIGNAL DETECTOR
# ============================================================================

class SignalDetector:
    """Advanced signal detection with multiple patterns"""

    # Comprehensive patterns - catches all variations including past tense
    LONG_PATTERNS = [
        # Present tense
        r"going\s+longs?\s+(?:on\s+)?(\$?[A-Z]{2,10})",
        r"taking\s+(?:a|an)\s+(\$?[A-Z]{2,10})\s+long",
        r"(?:^|\s)long(?:ing)?\s+(\$?[A-Z]{2,10})",
        r"(\$?[A-Z]{2,10})\s+long",

        # Past tense - "longed"
        r"longed\s+(?:on\s+)?(\$?[A-Z]{2,10})",
        r"went\s+longs?\s+(?:on\s+)?(\$?[A-Z]{2,10})",

        # Buying variations
        r"(?:just\s+)?bought\s+(?:some\s+)?(?:spot\s+)?(\$?[A-Z]{2,10})",
        r"buying\s+(\$?[A-Z]{2,10})",
        r"entered\s+(?:a\s+)?long\s+(?:on\s+)?(\$?[A-Z]{2,10})",
        r"entered\s+(\$?[A-Z]{2,10})\s+long",

        # Market orders
        r"market\s+long(?:ing|ed)?\s+(?:on\s+)?(\$?[A-Z]{2,10})",

        # "Long BTC here" or "Longed BTC here"
        r"long(?:ed|ing)?\s+(\$?[A-Z]{2,10})\s+here",

        # "BTC long here"
        r"(\$?[A-Z]{2,10})\s+long\s+here",
    ]

    SHORT_PATTERNS = [
        # Present tense
        r"going\s+shorts?\s+(?:on\s+)?(\$?[A-Z]{2,10})",
        r"taking\s+(?:a|an)\s+(\$?[A-Z]{2,10})\s+short",
        r"(?:^|\s)short(?:ing)?\s+(\$?[A-Z]{2,10})",
        r"(\$?[A-Z]{2,10})\s+short",

        # Past tense - "shorted"
        r"shorted\s+(?:on\s+)?(\$?[A-Z]{2,10})",
        r"went\s+shorts?\s+(?:on\s+)?(\$?[A-Z]{2,10})",

        # Selling variations
        r"(?:just\s+)?sold\s+(?:some\s+)?(\$?[A-Z]{2,10})",
        r"selling\s+(\$?[A-Z]{2,10})",
        r"entered\s+(?:a\s+)?short\s+(?:on\s+)?(\$?[A-Z]{2,10})",
        r"entered\s+(\$?[A-Z]{2,10})\s+short",

        # Market orders
        r"market\s+short(?:ing|ed)?\s+(?:on\s+)?(\$?[A-Z]{2,10})",

        # "Short BTC here" or "Shorted BTC here"
        r"short(?:ed|ing)?\s+(\$?[A-Z]{2,10})\s+here",

        # "BTC short here"
        r"(\$?[A-Z]{2,10})\s+short\s+here",
    ]

    def __init__(self):
        # Compile patterns for efficiency
        self.long_regex = [re.compile(pattern, re.IGNORECASE) for pattern in self.LONG_PATTERNS]
        self.short_regex = [re.compile(pattern, re.IGNORECASE) for pattern in self.SHORT_PATTERNS]

    def detect_signal(self, message_content: str) -> Optional[TradingSignal]:
        """
        Detect trading signal from message content
        Returns TradingSignal object or None
        """

        # Check for LONG signals
        for pattern in self.long_regex:
            match = pattern.search(message_content)
            if match:
                ticker = self._clean_ticker(match.group(1))
                signal = self._build_signal(
                    signal_type="LONG",
                    ticker=ticker,
                    message=message_content
                )
                return signal

        # Check for SHORT signals
        for pattern in self.short_regex:
            match = pattern.search(message_content)
            if match:
                ticker = self._clean_ticker(match.group(1))
                signal = self._build_signal(
                    signal_type="SHORT",
                    ticker=ticker,
                    message=message_content
                )
                return signal

        return None

    def _clean_ticker(self, ticker: str) -> str:
        """Clean ticker symbol"""
        return ticker.replace('$', '').upper().strip()

    def _build_signal(self, signal_type: str, ticker: str, message: str) -> TradingSignal:
        """Build signal with minimal extraction - price data comes from images"""

        # Detect entry type (CMP vs MARKET)
        entry_type = "CMP" if re.search(r"\bat\s+cmp\b", message, re.IGNORECASE) else "MARKET"

        signal = TradingSignal(
            signal_type=signal_type,
            ticker=ticker,
            raw_message=message,
            timestamp=datetime.now(),
            confidence=0.9,  # High confidence for pattern matches
            notes=entry_type  # Store if it's CMP or MARKET entry
        )

        return signal


# ============================================================================
# NOTIFICATION MANAGER
# ============================================================================

class NotificationManager:
    """Handles notifications and alerts"""

    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url

    def format_signal_alert(self, signal: TradingSignal) -> str:
        """Format signal as text alert"""

        type_emoji = "🟢" if signal.signal_type == "LONG" else "🔴"

        alert = f"\n{'='*60}\n"
        alert += f"🚨 {type_emoji} {signal.signal_type} SIGNAL - {signal.ticker}\n"
        alert += f"{'='*60}\n"
        alert += f"Time: {signal.timestamp.strftime('%H:%M:%S')}\n"
        alert += f"Entry: {signal.notes if signal.notes else 'MARKET'}\n"

        # Show extracted price levels if available
        has_prices = any([signal.entry_price, signal.stop_loss, signal.take_profit_1])

        if has_prices:
            alert += f"\n📊 PRICE LEVELS:\n"
            if signal.entry_price:
                alert += f"  Entry:     ${signal.entry_price:,.4f}\n"
            if signal.stop_loss:
                alert += f"  🛑 SL:     ${signal.stop_loss:,.4f}\n"
            if signal.take_profit_1:
                alert += f"  🎯 TP1:    ${signal.take_profit_1:,.4f}\n"
            if signal.take_profit_2:
                alert += f"  🎯 TP2:    ${signal.take_profit_2:,.4f}\n"
            if signal.take_profit_3:
                alert += f"  🎯 TP3:    ${signal.take_profit_3:,.4f}\n"

            if signal.notes and "OCR" in signal.notes:
                alert += f"\n{signal.notes}\n"
        else:
            alert += f"\n⚠️  NO PRICES EXTRACTED - Check Discord\n"

        alert += f"{'='*60}\n"

        return alert

    async def send_notification(self, signal: TradingSignal):
        """Send notification via webhook"""
        if not self.webhook_url:
            return

        # TODO: Implement webhook notification (Discord, Telegram, etc.)
        # This would require additional libraries like aiohttp
        pass

# ============================================================================
# DISCORD BOT CLIENT
# ============================================================================

class NeilBot(discord.Client):
    """Advanced Discord bot for monitoring Neil's signals"""

    def __init__(self, config: Config, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = config
        self.db = DatabaseManager(config.DATABASE_PATH)
        self.detector = SignalDetector()
        self.notifier = NotificationManager(config.WEBHOOK_URL)
        self.message_count = 0
        self.signal_count = 0
        self.pending_signal = None  # Store signal waiting for chart
        self.pending_signal_time = None  # Timestamp of signal

        # Initialize thread pool for async operations
        self.executor = ThreadPoolExecutor(max_workers=2)

        # Initialize chart extractor if available (lazy-loaded)
        if CHART_EXTRACTOR_AVAILABLE:
            try:
                # Lazy-load the chart extractor to avoid blocking bot startup
                from chart_extractor import HybridChartExtractor
                gpt4_key = config.GPT4_API_KEY
                self.chart_extractor = HybridChartExtractor(gpt4_api_key=gpt4_key)
                logging.info("Chart extractor initialized with GPT-4 Vision")
            except Exception as e:
                error_msg = str(e).encode('ascii', errors='ignore').decode('ascii')
                logging.error(f"Failed to initialize chart extractor: {error_msg}")
                logging.info("Bot will continue without image extraction feature")
                self.chart_extractor = None
        else:
            self.chart_extractor = None

        # Create temp directory for downloaded images
        self.temp_dir = Path("temp_charts")
        self.temp_dir.mkdir(exist_ok=True)

    async def on_ready(self):
        """Called when bot is ready"""
        logging.info(f"✓ Logged in as {self.user}")
        logging.info(f"✓ Monitoring {len(self.config.CHANNEL_IDS)} channel(s)")
        logging.info(f"✓ Database: {self.config.DATABASE_PATH}")
        logging.info(f"✓ Bot is ready and listening for signals...")

        print("\n" + "=" * 60, flush=True)
        print("✅ NEIL SIGNAL BOT ACTIVE", flush=True)
        print("=" * 60, flush=True)
        print(f"📊 Monitoring {len(self.config.CHANNEL_IDS)} channels", flush=True)
        print(f"👤 Tracking {len(self.config.NEIL_USERNAMES)} usernames", flush=True)
        print(f"🤖 Chart Extraction: {'GPT-4 Vision' if self.chart_extractor else 'Disabled'}", flush=True)
        print("=" * 60, flush=True)
        print("\n⏳ Waiting for signals...\n", flush=True)

    async def on_message(self, message):
        """Process incoming messages"""
        try:
            self.message_count += 1

            # Skip if not in monitored channels
            if message.channel.id not in self.config.CHANNEL_IDS:
                return

            # Check if from Neil or has alert tag
            is_from_neil = any(username.lower() in message.author.name.lower()
                             for username in self.config.NEIL_USERNAMES)
            has_alert_tag = any(tag.lower() in message.content.lower()
                              for tag in self.config.ALERT_TAGS)

            # Check if this is an image following a recent signal (from Neil)
            if self.pending_signal and message.attachments and is_from_neil:
                # Check if within 30 seconds of the signal
                if datetime.now() - self.pending_signal_time < timedelta(seconds=30):
                    logging.info("Found image following signal, processing...")
                    await self._process_chart_images(message, self.pending_signal)

                    # Save updated signal
                    self.db.save_signal(self.pending_signal)

                    # Print updated alert
                    alert = self.notifier.format_signal_alert(self.pending_signal)
                    print(alert)

                    self.pending_signal = None
                    self.pending_signal_time = None
                return

            if not (is_from_neil or has_alert_tag):
                return

            # Detect signal from text
            signal = self.detector.detect_signal(message.content)

            if signal:
                print(f"🔍 Signal detected from {message.author.name}")
                if signal.confidence < self.config.MIN_CONFIDENCE:
                    return

                # Enrich signal
                signal.message_id = message.id
                signal.author = message.author.name
                signal.channel_id = message.channel.id

                # Wait and check for attachments
                logging.info(f"Waiting for attachments... (initial count: {len(message.attachments)})")
                await asyncio.sleep(3)
                message = await message.channel.fetch_message(message.id)
                logging.info(f"After re-fetch: {len(message.attachments)} attachments found")

                if message.attachments:
                    print(f"📸 Processing {len(message.attachments)} chart image(s)...")
                    await self._process_chart_images(message, signal)
                    self.pending_signal = None
                else:
                    # No attachments yet - store signal and wait for next message
                    logging.warning("No attachments found, waiting for next message...")
                    self.pending_signal = signal
                    self.pending_signal_time = datetime.now()

                # Save to database
                signal_id = self.db.save_signal(signal)
                self.signal_count += 1

                # Print alert
                alert = self.notifier.format_signal_alert(signal)
                print(alert)

                # React
                try:
                    await message.add_reaction("👀")
                except:
                    pass

        except Exception as e:
            error_msg = str(e).encode('ascii', errors='ignore').decode('ascii')
            logging.error(f"Error processing message: {error_msg}", exc_info=True)

    async def _process_chart_images(self, message, signal: TradingSignal):
        """
        Process chart images attached to the message
        Downloads images and extracts price levels using OCR
        """
        if not self.chart_extractor:
            logging.info("Chart extractor not available, skipping image processing")
            return

        for attachment in message.attachments:
            # Check if attachment is an image
            if not attachment.content_type or not attachment.content_type.startswith('image/'):
                continue

            try:
                # Download image
                image_path = self.temp_dir / f"chart_{message.id}_{attachment.id}.{attachment.filename.split('.')[-1]}"

                logging.info(f"Downloading chart image: {attachment.filename}")

                async with aiohttp.ClientSession() as session:
                    async with session.get(attachment.url) as resp:
                        if resp.status == 200:
                            with open(image_path, 'wb') as f:
                                f.write(await resp.read())
                        else:
                            logging.error(f"Failed to download image: HTTP {resp.status}")
                            continue

                # Extract prices from chart ASYNCHRONOUSLY to avoid blocking Discord heartbeat
                logging.info(f"Extracting prices from chart (Trade: {signal.signal_type})...")

                # Run extraction in a thread pool to avoid blocking
                # Add timeout to prevent hanging forever
                loop = asyncio.get_event_loop()
                try:
                    extraction_result = await asyncio.wait_for(
                        loop.run_in_executor(
                            self.executor,  # Use our dedicated thread pool
                            self.chart_extractor.extract_prices,
                            str(image_path),
                            signal.signal_type  # Pass LONG or SHORT
                        ),
                        timeout=30  # 30 second timeout
                    )
                except asyncio.TimeoutError:
                    logging.error("Chart extraction timed out after 30 seconds")
                    # Create empty result on timeout
                    from chart_extractor import ChartExtractionResult
                    extraction_result = ChartExtractionResult(
                        validation_errors=["Extraction timed out"],
                        extraction_method="timeout"
                    )

                # Update signal with extracted prices
                if extraction_result.stop_loss:
                    signal.stop_loss = extraction_result.stop_loss
                    logging.info(f"Extracted Stop Loss: {signal.stop_loss}")

                if extraction_result.take_profit_1:
                    signal.take_profit_1 = extraction_result.take_profit_1
                    logging.info(f"Extracted TP1: {signal.take_profit_1}")

                if extraction_result.take_profit_2:
                    signal.take_profit_2 = extraction_result.take_profit_2
                    logging.info(f"Extracted TP2: {signal.take_profit_2}")

                if extraction_result.take_profit_3:
                    signal.take_profit_3 = extraction_result.take_profit_3
                    logging.info(f"Extracted TP3: {signal.take_profit_3}")

                if extraction_result.entry_price:
                    signal.entry_price = extraction_result.entry_price
                    logging.info(f"Extracted Entry: {signal.entry_price}")

                # Add extraction metadata to notes
                metadata = []
                metadata.append(f"Method: {extraction_result.extraction_method}")
                metadata.append(f"Confidence: {extraction_result.confidence_score:.1%}")
                metadata.append(f"Time: {extraction_result.processing_time:.1f}s")

                if extraction_result.validation_passed:
                    metadata.append("✓ Validated")
                    print(f"✅ Extracted prices - SL: {signal.stop_loss} | TP1: {signal.take_profit_1} | TP2: {signal.take_profit_2} | TP3: {signal.take_profit_3}")
                else:
                    metadata.append("⚠ Validation failed")
                    if extraction_result.validation_errors:
                        print(f"⚠️ Validation issues: {', '.join(extraction_result.validation_errors[:2])}")
                        for error in extraction_result.validation_errors:
                            logging.warning(f"Validation error: {error}")

                conf_note = " | ".join(metadata)
                if signal.notes:
                    signal.notes += f" | {conf_note}"
                else:
                    signal.notes = conf_note

                # Clean up temp file
                try:
                    os.remove(image_path)
                except:
                    pass

            except Exception as e:
                error_msg = str(e).encode('ascii', errors='ignore').decode('ascii')
                logging.error(f"Error processing chart image: {error_msg}", exc_info=True)

    async def on_disconnect(self):
        """Called when bot disconnects"""
        logging.warning("Bot disconnected from Discord")

    async def on_error(self, event, *args, **kwargs):
        """Handle errors"""
        logging.error(f"Error in {event}", exc_info=True)

    async def close(self):
        """Cleanup on bot shutdown"""
        # Shutdown thread pool executor
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=False)
        await super().close()

    def get_stats(self) -> Dict:
        """Get bot statistics"""
        return {
            'messages_processed': self.message_count,
            'signals_detected': self.signal_count,
            'database_stats': self.db.get_statistics()
        }

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def setup_logging(log_level: str = "INFO"):
    """Setup logging configuration"""
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('neil_bot.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

    # Suppress Discord's verbose event parsing logs
    discord_logger = logging.getLogger('discord')
    discord_logger.setLevel(logging.WARNING)  # Only show warnings and errors from Discord

    # Suppress HTTP request logs
    http_logger = logging.getLogger('discord.http')
    http_logger.setLevel(logging.WARNING)

    # Suppress gateway logs
    gateway_logger = logging.getLogger('discord.gateway')
    gateway_logger.setLevel(logging.WARNING)

def main():
    """Main entry point with auto-restart on disconnect"""
    print("\n" + "=" * 60, flush=True)
    print("Starting Neil Signal Bot", flush=True)
    print("=" * 60, flush=True)

    # Load configuration
    config = Config()

    # Setup logging
    setup_logging(config.LOG_LEVEL)

    # Validate token
    if not config.DISCORD_TOKEN or config.DISCORD_TOKEN == "YOUR_DISCORD_TOKEN_HERE":
        print("\nERROR: Discord token not configured!")
        print("Please edit config.json and add your Discord token")
        print("\nWARNING: Using selfbots violates Discord ToS")
        print("Your account may be banned. Use at your own risk.\n")
        sys.exit(1)

    # Run bot with auto-restart
    restart_count = 0
    max_restarts = 5

    while restart_count < max_restarts:
        try:
            # Create and run bot
            bot = NeilBot(config)
            print("\nConnecting to Discord...", flush=True)
            bot.run(config.DISCORD_TOKEN)  # discord.py-self doesn't need bot=False

            # If we get here, the bot stopped normally
            break

        except KeyboardInterrupt:
            print("\n\nBot stopped by user")
            if hasattr(locals(), 'bot'):
                stats = bot.get_stats()
                print(f"\nSession Statistics:")
                print(f"  Messages Processed: {stats['messages_processed']}")
                print(f"  Signals Detected: {stats['signals_detected']}")
            break

        except discord.errors.ConnectionClosed:
            restart_count += 1
            print(f"\n⚠ Discord connection lost. Restarting... (Attempt {restart_count}/{max_restarts})")
            logging.warning(f"Discord connection lost, attempting restart {restart_count}/{max_restarts}")

            # Clean up the old bot instance
            if hasattr(locals(), 'bot'):
                try:
                    asyncio.run(bot.close())
                except:
                    pass

            # Wait before reconnecting
            import time
            time.sleep(5)
            continue

        except Exception as e:
            print(f"\nError: {e}")
            logging.error("Bot error", exc_info=True)
            restart_count += 1

            if restart_count < max_restarts:
                print(f"Restarting... (Attempt {restart_count}/{max_restarts})")
                import time
                time.sleep(5)
            else:
                print(f"\nFatal error after {max_restarts} restart attempts")
                sys.exit(1)

    if restart_count >= max_restarts:
        print(f"\nBot stopped after {max_restarts} restart attempts")
        sys.exit(1)

if __name__ == "__main__":
    main()
