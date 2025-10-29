#!/usr/bin/env python3
"""
Simplified Chart Price Extractor with GPT-4 Vision
Includes validation and retry logic for improved accuracy
"""

import os
import json
import base64
import logging
import openai
from typing import Optional
from dataclasses import dataclass


@dataclass
class ChartExtractionResult:
    """Result from chart extraction"""
    stop_loss: Optional[float] = None
    take_profit_1: Optional[float] = None
    take_profit_2: Optional[float] = None
    take_profit_3: Optional[float] = None
    entry_price: Optional[float] = None
    confidence_score: float = 0.0
    extraction_method: str = "gpt4_vision"


class ChartPriceExtractor:
    """Simplified chart extractor using only GPT-4 Vision with validation"""

    def __init__(self, gpt4_api_key: str = None):
        """Initialize with GPT-4 API key"""
        self.openai_client = openai.OpenAI(api_key=gpt4_api_key) if gpt4_api_key else None
        logging.info("Chart extractor initialized with GPT-4 Vision")

    def _validate_extraction(self, result: ChartExtractionResult, trade_direction: str = "LONG") -> bool:
        """
        Validate extraction makes logical sense for trading
        Returns True if valid, False if something is wrong
        """
        prices = []

        # Collect all extracted prices
        if result.stop_loss:
            prices.append(('SL', result.stop_loss))
        if result.take_profit_1:
            prices.append(('TP1', result.take_profit_1))
        if result.take_profit_2:
            prices.append(('TP2', result.take_profit_2))
        if result.take_profit_3:
            prices.append(('TP3', result.take_profit_3))

        if len(prices) < 2:
            return True  # Not enough data to validate

        # For LONG: SL should be lowest, TPs should increase
        # For SHORT: SL should be highest, TPs should decrease

        # Simple check: are TPs in order?
        tp_prices = []
        if result.take_profit_1:
            tp_prices.append(result.take_profit_1)
        if result.take_profit_2:
            tp_prices.append(result.take_profit_2)
        if result.take_profit_3:
            tp_prices.append(result.take_profit_3)

        if len(tp_prices) >= 2:
            # Check if TPs are in ascending order (for LONG)
            if trade_direction == "LONG":
                for i in range(len(tp_prices) - 1):
                    if tp_prices[i] >= tp_prices[i + 1]:
                        logging.warning(f"❌ TP order invalid for LONG: TP{i+1}={tp_prices[i]} >= TP{i+2}={tp_prices[i+1]}")
                        return False
            # Check if TPs are in descending order (for SHORT)
            else:
                for i in range(len(tp_prices) - 1):
                    if tp_prices[i] <= tp_prices[i + 1]:
                        logging.warning(f"❌ TP order invalid for SHORT: TP{i+1}={tp_prices[i]} <= TP{i+2}={tp_prices[i+1]}")
                        return False

        # Check if SL is on correct side
        if result.stop_loss and tp_prices:
            if trade_direction == "LONG":
                if result.stop_loss >= min(tp_prices):
                    logging.warning(f"❌ SL={result.stop_loss} >= TP for LONG trade")
                    return False
            else:
                if result.stop_loss <= max(tp_prices):
                    logging.warning(f"❌ SL={result.stop_loss} <= TP for SHORT trade")
                    return False

        logging.info("✅ Extraction passed validation")
        return True

    def extract_prices(self, image_path: str, trade_direction: str = "LONG", max_retries: int = 2) -> ChartExtractionResult:
        """
        Main extraction pipeline - uses GPT-4 Vision with validation and retry

        Args:
            image_path: Path to chart image
            trade_direction: "LONG" or "SHORT" to validate correct price order
            max_retries: Number of retry attempts if validation fails
        """
        try:
            # Load image to verify it exists
            if not os.path.exists(image_path):
                logging.error(f"Image file not found: {image_path}")
                return ChartExtractionResult()

            # Use GPT-4 Vision with validation
            if self.openai_client:
                for attempt in range(max_retries + 1):
                    if attempt > 0:
                        logging.warning(f"🔄 Retry attempt {attempt}/{max_retries} - Previous extraction failed validation")

                    logging.info("🤖 Using GPT-4 Vision to extract prices...")
                    result = self._gpt4_vision_extract(image_path, retry_attempt=attempt)

                    # Validate the result
                    if self._validate_extraction(result, trade_direction):
                        if attempt > 0:
                            logging.info(f"✅ Retry successful on attempt {attempt}")
                        return result
                    else:
                        if attempt < max_retries:
                            logging.warning(f"⚠️ Extraction failed validation, retrying...")
                        else:
                            logging.error(f"❌ All {max_retries + 1} attempts failed validation")
                            # Return the result anyway but with lower confidence
                            result.confidence_score = 0.5
                            return result

                return result
            else:
                logging.error("❌ No GPT-4 API key provided!")
                return ChartExtractionResult()

        except Exception as e:
            error_msg = str(e).encode('ascii', errors='ignore').decode('ascii')
            logging.error(f"Extraction failed: {error_msg}", exc_info=True)
            return ChartExtractionResult()

    def _gpt4_vision_extract(self, image_path: str, retry_attempt: int = 0) -> ChartExtractionResult:
        """
        Extract prices using GPT-4 Vision API

        Args:
            image_path: Path to the chart image
            retry_attempt: Number of retry attempts (enhances prompt strictness)
        """
        try:
            with open(image_path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')

            # Add extra warning if this is a retry
            retry_warning = ""
            if retry_attempt > 0:
                retry_warning = """
⚠️⚠️⚠️ CRITICAL ALERT ⚠️⚠️⚠️
Previous extraction attempt FAILED validation!
The prices were NOT in logical order - you made a reading error.

Common mistakes to avoid:
- Confusing 202.22 with 208.33 (middle digit: 0 vs 8)
- Confusing 197.63 with 191.63 (second digit: 9 vs 1)
- Reading the same label twice
- Estimating instead of reading exact digits

BE EXTRA CAREFUL THIS TIME:
- Read each digit individually
- Verify the middle digits carefully (0 vs 8, 1 vs 7)
- Double-check your work before responding
- Make sure prices are in logical order

"""

            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": retry_warning + """You are a professional trading chart analyzer. Your task is to extract EXACT price levels from this trading chart with PERFECT decimal precision.

=== STEP 1: IDENTIFY THE KEY ELEMENTS ===
Look for:
- RED zones/lines = Stop Loss level
- GREEN/TEAL zones/lines = Take Profit levels (usually 3)
- Price scale on the RIGHT side of the chart
- Horizontal lines crossing through colored zones

=== STEP 2: LOCATE PRICE LABELS ===
Price labels appear where:
- Horizontal lines meet the RIGHT edge
- Inside or next to colored zones
- On the price axis (right side)

=== STEP 3: EXTRACT STOP LOSS ===
Find the RED zone/line:
- Read the EXACT price where the red horizontal line meets the price scale
- This is the Stop Loss (SL)
- Be precise with decimals

=== STEP 4: EXTRACT TAKE PROFITS ===
Find ALL GREEN/TEAL zones:
- There are usually 3 Take Profit levels (TP1, TP2, TP3)
- Read EXACT prices where green lines meet the price scale
- Order them correctly:
  - For LONG: TP1 < TP2 < TP3 (ascending)
  - For SHORT: TP1 > TP2 > TP3 (descending)

=== STEP 5: PRECISION VERIFICATION ===
For each price:
- Read every single digit carefully
- Don't round or estimate
- If you see 194.46, write exactly 194.46
- If you see 208.33, write exactly 208.33, NOT 202.22

=== STEP 6: COMMON MISTAKES TO AVOID ===
- DO NOT confuse similar-looking numbers
- 202.22 and 208.33 are DIFFERENT (check middle digit)
- 197.63 and 191.63 are DIFFERENT (check second digit)
- Always verify decimal places

=== STEP 7: FINAL QUALITY CHECK ===
Before outputting:
- Verify all prices are realistic (no negative, no extreme values)
- Check logical relationships (SL should be below TPs for long, above for short)
- Ensure you found at least SL and TP1

=== STEP 8: HANDLE SIMILAR-LOOKING NUMBERS ===
CRITICAL: When you see multiple prices close together (like 200.93, 202.22, 208.33):
- These are DIFFERENT numbers despite looking similar
- Do NOT confuse 202 with 208 - they differ by 6 points
- Read each digit individually: 2-0-8 is NOT the same as 2-0-2
- Verify by checking the middle digit: is it a 0 or an 8?
- If prices seem too close together (within 2 points), re-examine carefully

=== STEP 9: VERIFY LOGICAL ORDER ===
Before outputting, verify:
- For LONG trades: prices should INCREASE (SL → TP1 → TP2 → TP3)
- For SHORT trades: prices should DECREASE (TP1 → TP2 → TP3 → SL)
- If order is wrong, you made a reading error - GO BACK AND FIX IT

=== STEP 10: OUTPUT FORMAT ===
Return ONLY valid JSON with exact prices:
{
  "stop_loss": 194.46,
  "take_profit_1": 197.63,
  "take_profit_2": 200.93,
  "take_profit_3": 208.33,
  "entry_price": null
}

Use null for any level that doesn't exist.
BE EXACT WITH EVERY DECIMAL - ONE MISTAKE COSTS THOUSANDS!"""
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_data}",
                                "detail": "high"
                            }
                        }
                    ]
                }],
                max_tokens=300,
                temperature=0
            )

            # Parse response
            content = response.choices[0].message.content.strip()

            # Remove markdown if present
            if content.startswith('```'):
                content = content.split('```')[1]
                if content.startswith('json'):
                    content = content[4:]
                content = content.strip()

            # Parse JSON
            data = json.loads(content)

            result = ChartExtractionResult(
                stop_loss=data.get('stop_loss'),
                take_profit_1=data.get('take_profit_1'),
                take_profit_2=data.get('take_profit_2'),
                take_profit_3=data.get('take_profit_3'),
                entry_price=data.get('entry_price'),
                confidence_score=0.95  # Base confidence for GPT-4
            )

            return result

        except Exception as e:
            logging.error(f"GPT-4 extraction failed: {e}")
            return ChartExtractionResult()


# Backwards compatibility - keep the old name
HybridChartExtractor = ChartPriceExtractor