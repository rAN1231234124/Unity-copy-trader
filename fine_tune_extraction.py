#!/usr/bin/env python3
"""
Fine-tune chart extraction for better accuracy
Provides options to adjust extraction behavior
"""

import json
from pathlib import Path


def create_tuned_extractor():
    """Create a fine-tuned chart extractor with adjusted prompts"""

    config = {
        "extraction_strategies": {
            # More precise prompt for BTC prices in 100k+ range
            "btc_precise": """Extract exact BTC price levels from this trading chart.

IMPORTANT: BTC prices are likely in the 100,000+ range (six figures).

1. Look for RED zones/lines - this is the Stop Loss
   - Should be BELOW current price for LONG trades
   - Read the exact number, likely 105,000-106,000 range

2. Look for GREEN zones/lines - these are Take Profits
   - Should be ABOVE current price for LONG trades
   - TP1: First green level (closest to current)
   - TP2: Second green level (middle)
   - TP3: Third green level (furthest)
   - Likely in 109,000-125,000 range

3. Current/Entry price
   - Look for arrows, markers, or current price indicator
   - Likely around 107,000-108,000

BE VERY PRECISE:
- Read each digit carefully
- Don't round numbers
- If you see 105,626.40 write exactly that
- If you see 109,147.50 write exactly that

Return exact prices as JSON:
{
  "stop_loss": [exact number from red zone],
  "take_profit_1": [lowest green zone price],
  "take_profit_2": [middle green zone price],
  "take_profit_3": [highest green zone price],
  "entry_price": [current/entry price]
}""",

            # Focus on decimal precision
            "decimal_precise": """Extract trading levels with EXACT decimal precision.

READ NUMBERS CHARACTER BY CHARACTER:
1. Main price (before decimal): Read each digit
2. Decimal point: Note position
3. Decimal places: Read each decimal digit

COMMON MISREADS TO AVOID:
- 105,626.40 vs 105,626.00 (check last digit)
- 109,147.50 vs 109,174.50 (check digit order)
- 112,890.20 vs 112,980.20 (check middle digits)

For each colored zone:
- RED = Stop Loss
- GREEN = Take Profits (ordered low to high)
- Current price marker = Entry

Return with exact decimal precision.""",

            # Alternative number reading
            "digit_by_digit": """Read each price digit-by-digit from the chart.

STEP 1: Find each price level location
- Red box/line location
- Each green box/line location
- Current price location

STEP 2: For each location, read digits left to right
- Hundred thousands digit
- Ten thousands digit
- Thousands digit
- Hundreds digit
- Tens digit
- Ones digit
- Decimal point
- First decimal place
- Second decimal place

STEP 3: Construct the complete number
Example: 1-0-5-6-2-6-.-4-0 = 105626.40

Return exact prices found."""
        },

        "validation_adjustments": {
            "btc_price_range": {
                "min": 90000,
                "max": 150000,
                "typical_sl_distance": 0.015,  # 1.5% from entry
                "typical_tp1_distance": 0.015,  # 1.5% from entry
                "typical_tp2_distance": 0.05,   # 5% from entry
                "typical_tp3_distance": 0.15    # 15% from entry
            }
        },

        "common_corrections": {
            "digit_swaps": [
                ("6", "8"),  # 6 often misread as 8
                ("1", "7"),  # 1 often misread as 7
                ("0", "8"),  # 0 often misread as 8
                ("3", "8"),  # 3 often misread as 8
                ("5", "6"),  # 5 often misread as 6
            ],

            "decimal_issues": [
                ".00", ".40", ".50", ".20", ".80"  # Common decimal values
            ]
        }
    }

    # Save configuration
    with open("extraction_tuning.json", "w") as f:
        json.dump(config, f, indent=2)

    print("Fine-tuning configuration created: extraction_tuning.json")
    return config


def analyze_extraction_accuracy(extracted_prices: dict, actual_prices: dict = None):
    """Analyze extraction accuracy and suggest improvements"""

    print("\n" + "="*60)
    print("EXTRACTION ACCURACY ANALYSIS")
    print("="*60)

    print("\nExtracted Prices:")
    print(f"  Entry:     ${extracted_prices.get('entry', 'N/A'):,.2f}")
    print(f"  Stop Loss: ${extracted_prices.get('sl', 'N/A'):,.2f}")
    print(f"  TP1:       ${extracted_prices.get('tp1', 'N/A'):,.2f}")
    print(f"  TP2:       ${extracted_prices.get('tp2', 'N/A'):,.2f}")
    print(f"  TP3:       ${extracted_prices.get('tp3', 'N/A'):,.2f}")

    if actual_prices:
        print("\nActual Prices (for comparison):")
        print(f"  Entry:     ${actual_prices.get('entry', 'N/A'):,.2f}")
        print(f"  Stop Loss: ${actual_prices.get('sl', 'N/A'):,.2f}")
        print(f"  TP1:       ${actual_prices.get('tp1', 'N/A'):,.2f}")
        print(f"  TP2:       ${actual_prices.get('tp2', 'N/A'):,.2f}")
        print(f"  TP3:       ${actual_prices.get('tp3', 'N/A'):,.2f}")

        print("\nDifferences:")
        for key in ['entry', 'sl', 'tp1', 'tp2', 'tp3']:
            if key in extracted_prices and key in actual_prices:
                diff = extracted_prices[key] - actual_prices[key]
                pct = (diff / actual_prices[key]) * 100 if actual_prices[key] != 0 else 0
                print(f"  {key.upper()}: {diff:+,.2f} ({pct:+.2f}%)")

    # Analyze price relationships
    print("\nPrice Relationship Analysis:")

    if 'entry' in extracted_prices and 'sl' in extracted_prices:
        sl_distance = abs(extracted_prices['entry'] - extracted_prices['sl'])
        sl_pct = (sl_distance / extracted_prices['entry']) * 100
        print(f"  SL Distance: {sl_distance:,.2f} ({sl_pct:.2f}% from entry)")

        if sl_pct < 0.5:
            print("    ⚠ Stop loss seems too close (< 0.5%)")
        elif sl_pct > 10:
            print("    ⚠ Stop loss seems too far (> 10%)")

    if 'entry' in extracted_prices and 'tp1' in extracted_prices:
        tp1_distance = abs(extracted_prices['tp1'] - extracted_prices['entry'])
        tp1_pct = (tp1_distance / extracted_prices['entry']) * 100
        print(f"  TP1 Distance: {tp1_distance:,.2f} ({tp1_pct:.2f}% from entry)")

        risk_reward = tp1_distance / sl_distance if 'sl' in extracted_prices else 0
        if risk_reward > 0:
            print(f"  Risk:Reward (TP1): 1:{risk_reward:.2f}")

    # Check for common issues
    print("\nCommon Issues Check:")

    # Check if prices are too round (might be missing decimals)
    for key, price in extracted_prices.items():
        if price and price % 100 == 0:
            print(f"  ⚠ {key.upper()} is very round ({price}) - check decimals")

    # Check if TPs are in order
    if all(k in extracted_prices for k in ['tp1', 'tp2', 'tp3']):
        if not (extracted_prices['tp1'] < extracted_prices['tp2'] < extracted_prices['tp3']):
            print("  ⚠ Take profits are not in ascending order")

    print("\nSuggestions for Better Accuracy:")
    print("1. Ensure chart includes clear price labels")
    print("2. Include the price axis (right side) in screenshot")
    print("3. Use high-quality, uncompressed images")
    print("4. Avoid charts with overlapping text")
    print("5. Check if prices are in expected range for the asset")


def main():
    """Main function"""
    print("="*60)
    print("CHART EXTRACTION FINE-TUNING TOOL")
    print("="*60)

    # Your extracted prices from the bot
    extracted = {
        'entry': 107468.0,
        'sl': 105626.4,
        'tp1': 109147.5,
        'tp2': 112890.2,
        'tp3': 123158.1
    }

    print("\nYour bot extracted these prices:")
    analyze_extraction_accuracy(extracted)

    print("\n" + "="*60)
    print("CREATING FINE-TUNED CONFIGURATION...")
    print("="*60)

    config = create_tuned_extractor()

    print("\nTo use the fine-tuned extraction:")
    print("1. The new prompts are optimized for BTC 100k+ prices")
    print("2. They focus on exact decimal reading")
    print("3. They account for common misreads")

    print("\nIf prices are still wrong, please provide:")
    print("- What the ACTUAL prices should be")
    print("- A screenshot of the chart")
    print("- Which numbers are being misread")

    # Interactive correction
    print("\n" + "="*60)
    correct = input("Do you know the CORRECT prices? (y/n): ").strip().lower()

    if correct == 'y':
        print("\nEnter the CORRECT prices (press Enter to skip):")
        actual = {}

        for key, label in [('entry', 'Entry'), ('sl', 'Stop Loss'),
                          ('tp1', 'TP1'), ('tp2', 'TP2'), ('tp3', 'TP3')]:
            value = input(f"  {label}: ").strip()
            if value:
                try:
                    actual[key] = float(value.replace(',', ''))
                except ValueError:
                    pass

        if actual:
            print("\nComparing extracted vs actual:")
            analyze_extraction_accuracy(extracted, actual)

            # Identify patterns
            print("\n" + "="*60)
            print("PATTERN ANALYSIS")
            print("="*60)

            for key in actual:
                if key in extracted:
                    ext_str = f"{extracted[key]:.2f}"
                    act_str = f"{actual[key]:.2f}"

                    if len(ext_str) == len(act_str):
                        diffs = []
                        for i, (e, a) in enumerate(zip(ext_str, act_str)):
                            if e != a and e != '.' and a != '.':
                                diffs.append(f"position {i}: '{e}' → '{a}'")

                        if diffs:
                            print(f"\n{key.upper()} digit differences:")
                            for d in diffs:
                                print(f"  {d}")

            print("\nThis analysis helps identify if GPT-4 is consistently misreading certain digits.")


if __name__ == "__main__":
    main()