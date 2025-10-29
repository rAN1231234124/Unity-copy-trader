#!/usr/bin/env python3
"""
Diagnostic tool to test chart extraction and identify issues
Helps understand why extraction might be failing
"""

import sys
import json
import base64
import openai
from pathlib import Path


def diagnose_chart(image_path: str, api_key: str):
    """Diagnose why chart extraction might be failing"""

    print("=" * 60)
    print("CHART EXTRACTION DIAGNOSTIC")
    print("=" * 60)

    # Check file exists
    if not Path(image_path).exists():
        print(f"❌ ERROR: File not found: {image_path}")
        return

    file_size = Path(image_path).stat().st_size / 1024  # KB
    print(f"✅ File found: {image_path}")
    print(f"📊 File size: {file_size:.1f} KB")

    # Initialize OpenAI
    client = openai.OpenAI(api_key=api_key)

    # Load image
    with open(image_path, 'rb') as f:
        image_data = base64.b64encode(f.read()).decode('utf-8')

    print("\n" + "=" * 60)
    print("RUNNING DIAGNOSTIC QUERIES...")
    print("=" * 60)

    # Test 1: Basic description
    print("\n1️⃣ BASIC IMAGE DESCRIPTION")
    print("-" * 30)

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe what you see in this image in 2-3 sentences."},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_data}", "detail": "high"}}
                ]
            }],
            max_tokens=200
        )
        description = response.choices[0].message.content
        print(f"Description: {description}")
    except Exception as e:
        print(f"❌ Error: {e}")
        return

    # Test 2: Color detection
    print("\n2️⃣ COLOR DETECTION")
    print("-" * 30)

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": """List all colored rectangles, boxes, or zones you see:
- Red areas (location and what's inside)
- Green areas (location and what's inside)
- Any other colored zones

Be specific about what text or numbers appear in each colored area."""},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_data}", "detail": "high"}}
                ]
            }],
            max_tokens=300
        )
        colors = response.choices[0].message.content
        print(f"Colored zones: {colors}")
    except Exception as e:
        print(f"❌ Error: {e}")

    # Test 3: Number detection
    print("\n3️⃣ NUMBER DETECTION")
    print("-" * 30)

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": """List ALL numbers you can see in this image:
- Any price-like numbers (e.g., 67,234.50 or 1.0823)
- Numbers on axes
- Numbers in colored areas
- Any other visible numbers

List them exactly as they appear."""},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_data}", "detail": "high"}}
                ]
            }],
            max_tokens=400
        )
        numbers = response.choices[0].message.content
        print(f"Numbers found: {numbers}")
    except Exception as e:
        print(f"❌ Error: {e}")

    # Test 4: Text detection
    print("\n4️⃣ TEXT LABELS DETECTION")
    print("-" * 30)

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": """List any text labels or annotations you see:
- Labels like "TP1", "TP2", "SL", "Entry"
- Any text near lines or boxes
- Axis labels
- Any other readable text

Quote the exact text you see."""},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_data}", "detail": "high"}}
                ]
            }],
            max_tokens=300
        )
        text = response.choices[0].message.content
        print(f"Text found: {text}")
    except Exception as e:
        print(f"❌ Error: {e}")

    # Test 5: Chart type identification
    print("\n5️⃣ CHART TYPE IDENTIFICATION")
    print("-" * 30)

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": """What type of chart is this?
- Is it a trading chart (candlestick, line chart)?
- What platform does it appear to be from (TradingView, MT4, etc.)?
- Are there price levels marked?
- Can you see a price scale/axis?"""},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_data}", "detail": "high"}}
                ]
            }],
            max_tokens=200
        )
        chart_type = response.choices[0].message.content
        print(f"Chart type: {chart_type}")
    except Exception as e:
        print(f"❌ Error: {e}")

    # Test 6: Extraction attempt
    print("\n6️⃣ EXTRACTION ATTEMPT")
    print("-" * 30)

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": """Try to extract trading levels from this chart.
Look for:
- Stop Loss (usually red)
- Take Profits (usually green)
- Entry price

Return as JSON or explain why you can't extract these values:
{
  "stop_loss": null or number,
  "take_profit_1": null or number,
  "take_profit_2": null or number,
  "take_profit_3": null or number,
  "entry_price": null or number,
  "extraction_notes": "explanation if values can't be found"
}"""},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_data}", "detail": "high"}}
                ]
            }],
            max_tokens=400
        )
        extraction = response.choices[0].message.content
        print(f"Extraction result:\n{extraction}")
    except Exception as e:
        print(f"❌ Error: {e}")

    print("\n" + "=" * 60)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 60)

    print("\n📋 TROUBLESHOOTING SUGGESTIONS:")
    print("-" * 30)
    print("If extraction is failing, check:")
    print("1. ❓ Are price numbers clearly visible in the image?")
    print("2. ❓ Are there colored boxes/zones with prices inside?")
    print("3. ❓ Is the price scale/axis included in the screenshot?")
    print("4. ❓ Is the image quality good (not blurry/compressed)?")
    print("5. ❓ Are prices in standard format (not abbreviated)?")
    print("\nFor best results, charts should have:")
    print("• Clear price labels on colored zones")
    print("• Visible price axis on the right")
    print("• High contrast between text and background")
    print("• Standard price notation (67,234.50 not 67.2k)")


def main():
    """Main entry point"""

    # Check for API key in config
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
            api_key = config.get('gpt4_api_key')
    except:
        print("❌ Could not load GPT-4 API key from config.json")
        api_key = input("Enter your GPT-4 API key: ").strip()

    if not api_key or api_key == "YOUR_GPT4_API_KEY_HERE":
        print("❌ Valid GPT-4 API key required")
        return

    # Get image path
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
    else:
        # Try to find a recent chart
        from pathlib import Path
        charts = list(Path("temp_charts").glob("*.png")) if Path("temp_charts").exists() else []

        if charts:
            print("📊 Found charts in temp_charts/")
            for i, chart in enumerate(charts[-5:], 1):
                print(f"  {i}. {chart.name}")

            choice = input("\nEnter number to diagnose (or path to other image): ").strip()

            if choice.isdigit() and 1 <= int(choice) <= len(charts):
                image_path = str(charts[-5:][int(choice)-1])
            else:
                image_path = choice
        else:
            image_path = input("Enter path to chart image: ").strip()

    diagnose_chart(image_path, api_key)


if __name__ == "__main__":
    main()