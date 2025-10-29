#!/usr/bin/env python3
"""
Bot Monitor - Keeps the bot running and logs connection issues
"""

import subprocess
import time
import datetime
import sys
import os

def monitor_bot():
    """Monitor and restart bot as needed"""

    print("="*60)
    print("BOT MONITOR STARTED")
    print("="*60)
    print(f"Time: {datetime.datetime.now()}")
    print("This will keep your bot running 24/7")
    print("Press Ctrl+C to stop monitoring\n")

    restart_count = 0
    max_restarts = 100  # Allow many restarts

    # Log file for monitoring
    log_file = "monitor.log"

    while restart_count < max_restarts:
        try:
            start_time = datetime.datetime.now()

            print(f"\n🚀 Starting bot... (Attempt #{restart_count + 1})")
            print(f"Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

            # Log start
            with open(log_file, 'a') as f:
                f.write(f"\n[{start_time}] Starting bot (Attempt #{restart_count + 1})\n")

            # Run the stable version
            process = subprocess.run(
                [sys.executable, "neil_bot_stable.py"],
                capture_output=False,
                text=True
            )

            # Calculate uptime
            end_time = datetime.datetime.now()
            uptime = end_time - start_time

            print(f"\n⚠️  Bot stopped after {uptime}")
            print(f"Exit code: {process.returncode}")

            # Log stop
            with open(log_file, 'a') as f:
                f.write(f"[{end_time}] Bot stopped after {uptime}, exit code: {process.returncode}\n")

            if process.returncode == 0:
                # Clean exit
                print("Bot exited cleanly")
                break

            # Wait before restart
            restart_count += 1
            if restart_count < max_restarts:
                wait_time = min(30, 5 + restart_count * 2)  # Gradually increase wait time
                print(f"🔄 Restarting in {wait_time} seconds...")
                time.sleep(wait_time)

        except KeyboardInterrupt:
            print("\n\n👋 Monitor stopped by user")
            break
        except Exception as e:
            print(f"\n❌ Monitor error: {e}")
            restart_count += 1
            time.sleep(10)

    print("\n" + "="*60)
    print("MONITOR STOPPED")
    print(f"Total restarts: {restart_count}")
    print("="*60)

if __name__ == "__main__":
    monitor_bot()