#!/usr/bin/env python3
"""
Simple Discord connection test
"""

import discord
import asyncio
import json
import sys

# Load config
with open('config.json', 'r') as f:
    config = json.load(f)

token = config['discord_token']

class TestBot(discord.Client):
    async def on_ready(self):
        print(f'Successfully connected!')
        print(f'Logged in as: {self.user}')
        print(f'User ID: {self.user.id}')
        await self.close()  # Close connection after successful login

# Create client
client = TestBot()

print("Testing Discord connection...")
print(f"Token (partial): {token[:20]}...{token[-10:]}")

try:
    # Run with timeout
    async def run_with_timeout():
        try:
            await asyncio.wait_for(
                client.start(token),
                timeout=30.0
            )
        except asyncio.TimeoutError:
            print("Connection timeout after 30 seconds")
            print("This usually means:")
            print("1. Discord token is invalid or expired")
            print("2. Discord has blocked the connection")
            print("3. Network/firewall issue")
            await client.close()
        except discord.LoginFailure as e:
            print(f"LOGIN FAILED: {e}")
            print("Your Discord token is invalid!")
            await client.close()
        except Exception as e:
            print(f"Connection failed: {e}")
            await client.close()

    asyncio.run(run_with_timeout())

except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)