# Unity Copy Trader - Discord Trading Signal Bot

An advanced Discord bot that monitors trading signals from specific users, automatically extracts price levels from chart images using GPT-4 Vision, and saves them to a database for copy trading.

## ⚠️ Important Disclaimer

**This bot uses discord.py-self which violates Discord's Terms of Service. Use at your own risk - your account may be banned.**

## 🚀 Features

- **Real-time Signal Detection**: Monitors Discord channels for LONG/SHORT trading signals
- **Advanced Chart Analysis**: Uses GPT-4 Vision to extract:
  - Stop Loss levels (from red zones)
  - Take Profit levels (from green zones)
  - Entry prices
- **Multi-Strategy Extraction**: Tries multiple approaches for accurate price detection
- **Database Storage**: Saves all signals to SQLite database
- **Auto-Reconnection**: Automatically reconnects if Discord connection drops
- **Async Processing**: Non-blocking chart extraction prevents disconnections

## 📦 Installation

1. Clone the repository:
```bash
git clone https://github.com/YOUR_USERNAME/Unity-copy-trader.git
cd Unity-copy-trader
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure the bot:
```bash
cp config.example.json config.json
# Edit config.json with your settings
```

## ⚙️ Configuration

Create a `config.json` file with:

```json
{
  "discord_token": "YOUR_DISCORD_TOKEN",
  "gpt4_api_key": "YOUR_OPENAI_API_KEY",
  "channel_ids": [123456789, 987654321],
  "neil_usernames": ["Nurse Neil 💉 | Unity"],
  "alert_tags": ["@Neilarora Alerts"],
  "webhook_url": "",
  "database_path": "signals.db",
  "log_level": "INFO",
  "enable_notifications": true,
  "min_confidence": 0.7
}
```

## 🏃 Running the Bot

```bash
python neil_bot.py
```

## 📊 Chart Extraction System

The bot uses a sophisticated multi-strategy approach to extract prices from trading charts:

### Extraction Strategies:
1. **Comprehensive**: Scans for all visual elements
2. **Box-Focused**: Targets colored rectangles with prices
3. **Line-Focused**: Follows horizontal lines to price axis

### What It Detects:
- 🔴 Red zones/boxes → Stop Loss
- 🟢 Green zones/boxes → Take Profits
- 📍 Entry markers → Entry price
- 📊 Price axis labels

## 🔍 Troubleshooting

### Testing Chart Extraction:
```bash
python test_improved_extraction.py
```

### Diagnosing Chart Issues:
```bash
python diagnose_chart.py
```

### Fine-Tuning Accuracy:
```bash
python fine_tune_extraction.py
```

## 📁 Project Structure

```
Unity-copy-trader/
├── neil_bot.py                 # Main bot file
├── chart_extractor.py          # Advanced chart extraction with GPT-4 Vision
├── chart_extractor_async.py    # Async version for non-blocking extraction
├── chart_prompts_library.py    # Specialized prompts for different chart types
├── config.json                 # Configuration (DO NOT COMMIT)
├── requirements.txt            # Python dependencies
├── signals.db                  # SQLite database (auto-created)
├── temp_charts/               # Temporary chart storage
└── diagnostic_tools/
    ├── diagnose_chart.py      # Chart diagnostic tool
    ├── test_improved_extraction.py  # Test extraction system
    └── fine_tune_extraction.py     # Fine-tune extraction accuracy
```

## 🎯 Key Improvements

### Recent Updates:
- ✅ **Multi-strategy extraction** for better accuracy
- ✅ **Async processing** prevents Discord disconnections
- ✅ **Auto-reconnection** on connection drops
- ✅ **Enhanced validation** for price relationships
- ✅ **Timeout protection** for stuck extractions
- ✅ **Better error handling** and logging

## 📈 Database Schema

### Signals Table:
- `id`: Primary key
- `signal_type`: LONG or SHORT
- `ticker`: Trading symbol (BTC, ETH, etc.)
- `entry_price`: Entry price
- `stop_loss`: Stop loss price
- `take_profit_1-3`: Take profit levels
- `timestamp`: Signal time
- `confidence`: Extraction confidence score

## 🔧 Development

### Running Tests:
```bash
python -m pytest tests/
```

### Contributing:
1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Open a Pull Request

## 📝 License

This project is for educational purposes only. Use at your own risk.

## ⚠️ Security Notes

- **Never commit `config.json`** - it contains sensitive tokens
- Keep your Discord token and API keys secure
- Use environment variables for production deployments

## 🤝 Support

For issues or questions, please open an issue on GitHub.

---

**Remember**: This bot uses self-botting which violates Discord's ToS. Your account may be banned. Always use a dedicated account for testing.