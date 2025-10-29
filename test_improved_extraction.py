#!/usr/bin/env python3
"""
Test script for improved chart extraction
Demonstrates the new multi-strategy approach
"""

import logging
import sys
import os
from pathlib import Path
from chart_extractor import ChartPriceExtractor

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def test_extraction():
    """Test the improved chart extraction"""

    # Initialize extractor
    # Note: You need to add your GPT-4 API key to config.json
    print("=" * 60)
    print("IMPROVED CHART EXTRACTION TEST")
    print("=" * 60)

    # Check for API key
    try:
        import json
        with open('config.json', 'r') as f:
            config = json.load(f)
            api_key = config.get('gpt4_api_key')

        if not api_key or api_key == "YOUR_GPT4_API_KEY_HERE":
            print("\n⚠️  Please add your GPT-4 API key to config.json")
            print("   The key should be in the 'gpt4_api_key' field")
            return
    except FileNotFoundError:
        print("\n⚠️  config.json not found. Please create it first.")
        return

    # Initialize the extractor
    print("\n📊 Initializing Chart Extractor...")
    extractor = ChartPriceExtractor(gpt4_api_key=api_key)

    # Look for test images in temp_charts directory
    chart_dir = Path("temp_charts")
    if not chart_dir.exists():
        print(f"\n⚠️  No temp_charts directory found")
        print("   The bot will create this when it processes Discord messages")
        return

    # Find chart images
    chart_files = list(chart_dir.glob("*.png")) + list(chart_dir.glob("*.jpg"))

    if not chart_files:
        print(f"\n⚠️  No chart images found in {chart_dir}")
        print("   Run the bot first to capture some chart images")
        return

    print(f"\n✅ Found {len(chart_files)} chart image(s)")

    # Test each image
    for i, image_path in enumerate(chart_files[:3], 1):  # Test first 3 images
        print(f"\n{'='*60}")
        print(f"TEST {i}: {image_path.name}")
        print(f"{'='*60}")

        # Test both LONG and SHORT interpretations
        for trade_direction in ["LONG", "SHORT"]:
            print(f"\n🔍 Testing as {trade_direction} trade...")

            result = extractor.extract_prices(
                str(image_path),
                trade_direction=trade_direction
            )

            # Display results
            print(f"\n📈 Extraction Results ({trade_direction}):")
            print(f"   Method: {result.extraction_method}")
            print(f"   Confidence: {result.confidence_score:.1%}")
            print(f"   Processing Time: {result.processing_time:.2f}s")

            print(f"\n💰 Extracted Prices:")
            if result.stop_loss:
                print(f"   🛑 Stop Loss:    ${result.stop_loss:,.4f}")
            if result.entry_price:
                print(f"   🎯 Entry:        ${result.entry_price:,.4f}")
            if result.take_profit_1:
                print(f"   ✅ Take Profit 1: ${result.take_profit_1:,.4f}")
            if result.take_profit_2:
                print(f"   ✅ Take Profit 2: ${result.take_profit_2:,.4f}")
            if result.take_profit_3:
                print(f"   ✅ Take Profit 3: ${result.take_profit_3:,.4f}")

            if not any([result.stop_loss, result.take_profit_1]):
                print(f"   ❌ No prices extracted")

            # Show validation status
            print(f"\n✔️  Validation:")
            if result.validation_passed:
                print(f"   ✅ All validations passed")
            else:
                print(f"   ⚠️  Validation issues found:")
                for error in result.validation_errors[:3]:  # Show first 3 errors
                    print(f"      - {error}")

            # Show raw extraction data if available
            if result.raw_extraction and 'all_prices_found' in result.raw_extraction:
                print(f"\n🔢 All prices detected in image:")
                all_prices = result.raw_extraction.get('all_prices_found', [])
                if all_prices:
                    print(f"   {all_prices}")

    print(f"\n{'='*60}")
    print("TEST COMPLETE")
    print(f"{'='*60}\n")

    # Show improvements made
    print("🎯 KEY IMPROVEMENTS IMPLEMENTED:")
    print("   ✅ Multiple extraction strategies (comprehensive, box-focused, line-focused)")
    print("   ✅ Better prompt clarity - focused on visual elements")
    print("   ✅ Enhanced validation with detailed error messages")
    print("   ✅ Support for different chart types and styles")
    print("   ✅ Confidence scoring based on extraction quality")
    print("   ✅ Fallback strategies if primary extraction fails")
    print("   ✅ Better handling of entry points and current price")
    print("   ✅ Validation considers trade direction (LONG vs SHORT)")
    print()

if __name__ == "__main__":
    test_extraction()