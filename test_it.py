"""
Test script for chart extractor
"""
from chart_extractor import ChartPriceExtractor
import logging
import sys
import json
from pathlib import Path

logging.basicConfig(level=logging.INFO)

def load_api_key():
    """Load API key from config.json"""
    config_path = Path("config.json")
    if not config_path.exists():
        print("ERROR: config.json not found!")
        print("Please create config.json with your OpenAI API key")
        sys.exit(1)

    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    api_key = config.get("gpt4_api_key", "")
    if not api_key or api_key == "YOUR_OPENAI_API_KEY_HERE":
        print("ERROR: OpenAI API key not configured in config.json!")
        print("Please add your API key to config.json")
        sys.exit(1)

    return api_key

def main():
    """Main test function"""
    # Get image path from command line or use default
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
    else:
        print("Usage: python test_it.py <path_to_chart_image>")
        print("\nExample: python test_it.py chart.png")
        sys.exit(1)

    # Check if image exists
    if not Path(image_path).exists():
        print(f"ERROR: Image file not found: {image_path}")
        sys.exit(1)

    # Load API key
    api_key = load_api_key()

    # Initialize extractor
    print("Initializing chart extractor...")
    extractor = ChartPriceExtractor(use_gpu=False, gpt4_api_key=api_key)

    # Extract prices
    print(f"Processing image: {image_path}")
    result = extractor.extract_prices(image_path)

    # Print results
    print("\n" + "="*60)
    print("EXTRACTION RESULTS")
    print("="*60)
    print(f"Stop Loss:  {result.stop_loss}")
    print(f"TP1:        {result.take_profit_1}")
    print(f"TP2:        {result.take_profit_2}")
    print(f"TP3:        {result.take_profit_3}")
    print(f"Entry:      {result.entry_price}")
    print(f"Confidence: {result.confidence_score:.1%}")
    print(f"Method:     {result.extraction_method}")
    print("="*60)

if __name__ == "__main__":
    main()
