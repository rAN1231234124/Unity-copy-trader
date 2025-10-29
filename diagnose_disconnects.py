#!/usr/bin/env python3
"""
Diagnose Discord Bot Disconnection Issues
"""

import re
from datetime import datetime
from pathlib import Path

def analyze_log_file(log_file="neil_bot.log"):
    """Analyze bot log for disconnect patterns"""

    if not Path(log_file).exists():
        print(f"❌ Log file {log_file} not found")
        return

    print("="*60)
    print("DISCONNECT ANALYSIS")
    print("="*60)

    disconnects = []
    errors = []
    signals = []
    connections = []

    # Parse log file
    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            # Find disconnects
            if "disconnected" in line.lower():
                match = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", line)
                if match:
                    timestamp = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")
                    disconnects.append(timestamp)

            # Find errors
            if "error" in line.lower() or "exception" in line.lower():
                errors.append(line.strip())

            # Find successful connections
            if "logged in as" in line.lower() or "bot is ready" in line.lower():
                match = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", line)
                if match:
                    timestamp = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")
                    connections.append(timestamp)

            # Find signals
            if "signal detected" in line.lower():
                signals.append(line.strip())

    # Analyze disconnect patterns
    print(f"\n📊 STATISTICS:")
    print(f"  Total Disconnects: {len(disconnects)}")
    print(f"  Total Connections: {len(connections)}")
    print(f"  Total Signals: {len(signals)}")
    print(f"  Total Errors: {len(errors)}")

    if disconnects:
        print(f"\n⏰ DISCONNECT TIMES:")
        for dc in disconnects[-10:]:  # Last 10 disconnects
            print(f"  - {dc}")

        # Calculate average uptime
        if len(disconnects) > 1:
            uptimes = []
            for i in range(1, len(disconnects)):
                uptime = disconnects[i] - disconnects[i-1]
                uptimes.append(uptime.total_seconds() / 60)  # Minutes

            avg_uptime = sum(uptimes) / len(uptimes)
            max_uptime = max(uptimes)
            min_uptime = min(uptimes)

            print(f"\n📈 UPTIME ANALYSIS:")
            print(f"  Average time between disconnects: {avg_uptime:.1f} minutes")
            print(f"  Maximum uptime: {max_uptime:.1f} minutes")
            print(f"  Minimum uptime: {min_uptime:.1f} minutes")

            # Check for patterns
            print(f"\n🔍 PATTERN DETECTION:")

            if avg_uptime < 30:
                print("  ⚠️  Very frequent disconnects (< 30 min average)")
                print("  Possible causes:")
                print("  - Rate limiting by Discord")
                print("  - Network instability")
                print("  - Bot being detected as spam")

            elif avg_uptime < 60:
                print("  ⚠️  Frequent disconnects (30-60 min average)")
                print("  Possible causes:")
                print("  - Session timeout issues")
                print("  - Memory leaks")
                print("  - Discord gateway issues")

            else:
                print("  ✅ Relatively stable (> 60 min average uptime)")

    if errors:
        print(f"\n❌ RECENT ERRORS:")
        for error in errors[-5:]:  # Last 5 errors
            print(f"  {error[:100]}...")  # First 100 chars

    print(f"\n💡 RECOMMENDATIONS:")
    print("  1. Use the stable version: python neil_bot_stable.py")
    print("  2. Run with monitor for auto-restart: python monitor_bot.py")
    print("  3. Check your network connection stability")
    print("  4. Ensure Discord token is valid and not rate-limited")
    print("  5. Consider using a VPS for better stability")

    # Check for specific issues
    print(f"\n🔧 SPECIFIC ISSUES:")

    heartbeat_issues = sum(1 for e in errors if "heartbeat" in e.lower())
    if heartbeat_issues > 0:
        print(f"  ⚠️  Heartbeat issues detected ({heartbeat_issues} occurrences)")
        print("     Solution: Use neil_bot_stable.py with better async handling")

    timeout_issues = sum(1 for e in errors if "timeout" in e.lower())
    if timeout_issues > 0:
        print(f"  ⚠️  Timeout issues detected ({timeout_issues} occurrences)")
        print("     Solution: Chart extraction timeouts reduced in stable version")

    connection_closed = sum(1 for e in errors if "connectionclosed" in e.lower() or "connection closed" in e.lower())
    if connection_closed > 0:
        print(f"  ⚠️  Connection closed errors ({connection_closed} occurrences)")
        print("     Solution: Auto-reconnection in stable version")

    print("\n" + "="*60)

if __name__ == "__main__":
    print("\n🔍 Analyzing bot disconnection issues...\n")
    analyze_log_file()

    print("\n" + "="*60)
    print("SOLUTIONS TO TRY:")
    print("="*60)
    print("\n1. USE STABLE VERSION:")
    print("   python neil_bot_stable.py")
    print("\n2. RUN WITH MONITOR (Auto-restart):")
    print("   python monitor_bot.py")
    print("\n3. USE WINDOWS BATCH LAUNCHER:")
    print("   RUN_BOT.bat")
    print("\n4. CHECK YOUR CONFIG:")
    print("   - Ensure Discord token is valid")
    print("   - Reduce number of monitored channels if too many")
    print("   - Disable chart extraction if not needed")
    print("\n" + "="*60)