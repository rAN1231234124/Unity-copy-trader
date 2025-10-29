#!/usr/bin/env python3
"""
Advanced Chart Price Extractor with Multiple Strategies
Improved prompts for better detection of trading indicators
"""

import os
import json
import base64
import logging
import openai
import time
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass, field


@dataclass
class ChartExtractionResult:
    """Result from chart extraction with detailed information"""
    stop_loss: Optional[float] = None
    take_profit_1: Optional[float] = None
    take_profit_2: Optional[float] = None
    take_profit_3: Optional[float] = None
    entry_price: Optional[float] = None
    confidence_score: float = 0.0
    extraction_method: str = "gpt4_vision"
    validation_passed: bool = False
    validation_errors: List[str] = field(default_factory=list)
    processing_time: float = 0.0
    raw_extraction: Optional[Dict] = None  # Store raw GPT response for debugging


class ChartPriceExtractor:
    """Advanced chart extractor with multiple extraction strategies"""

    # Define different prompt strategies for various chart types
    EXTRACTION_STRATEGIES = {
        "comprehensive": """You are an expert trading chart analyst. Extract ALL price levels from this trading chart.

WHAT TO LOOK FOR:
1. COLORED ZONES/BOXES:
   • RED boxes/zones/rectangles = Stop Loss (SL)
   • GREEN/TEAL/BLUE boxes/zones = Take Profits (TP1, TP2, TP3)
   • YELLOW/ORANGE zones = Entry zones
   • Look for price values written INSIDE these colored areas

2. HORIZONTAL LINES:
   • Solid horizontal lines with price labels
   • Dashed/dotted lines indicating key levels
   • Support and resistance lines

3. TEXT ANNOTATIONS:
   • Price labels on the right axis
   • Text directly on the chart showing prices
   • Labels like "TP1:", "TP2:", "SL:", "Entry:"
   • Numbers inside or near colored zones

4. VISUAL INDICATORS:
   • Arrows pointing to specific price levels
   • Crosshairs or markers at entry points
   • Any highlighted price values

EXTRACTION RULES:
- Read EXACT prices, including all decimal places
- Look for prices both inside colored zones AND on the price axis
- If you see multiple similar prices, they are likely different levels
- Entry price might be marked as "CMP" (Current Market Price) or with an arrow

OUTPUT FORMAT (JSON only):
{
  "stop_loss": [exact price or null],
  "take_profit_1": [exact price or null],
  "take_profit_2": [exact price or null],
  "take_profit_3": [exact price or null],
  "entry_price": [exact price or null],
  "current_price": [current market price if visible],
  "additional_levels": [any other important price levels as array]
}""",

        "box_focused": """Focus on extracting prices from COLORED BOXES and RECTANGLES on this trading chart.

STEP 1: Identify all colored rectangular zones
- RED boxes = Stop Loss levels
- GREEN/TEAL boxes = Take Profit levels
- Look for text/numbers INSIDE each box

STEP 2: Read the exact price value in each box
- Prices are usually displayed as white or black text inside the colored area
- May appear as: "197.63" or "TP1: 197.63" or just the number

STEP 3: Check box borders
- Some boxes have the price written on their border/edge
- Look at where boxes meet the right price axis

CRITICAL: Each colored box represents a different price level
- Don't skip any boxes
- Read every number carefully

Return JSON with exact prices from each box:
{
  "stop_loss": [price from red box],
  "take_profit_1": [price from first green box],
  "take_profit_2": [price from second green box],
  "take_profit_3": [price from third green box],
  "entry_price": [entry price if marked]
}""",

        "line_focused": """Extract prices from HORIZONTAL LINES and PRICE AXIS on this trading chart.

WHAT TO IDENTIFY:
1. Horizontal lines crossing the chart
2. Where each line intersects the right price axis
3. Price values displayed at these intersection points

HOW TO READ:
- Follow each horizontal line to the right edge
- Read the exact price value where it meets the scale
- Lines may be solid, dashed, or dotted
- Different colors indicate different purposes:
  * Red lines = Stop Loss
  * Green lines = Take Profits
  * White/gray = Support/Resistance

IMPORTANT:
- Some lines have labels directly on them
- Check for small text boxes attached to lines
- Entry point may be marked with an arrow

Return exact prices in JSON:
{
  "stop_loss": [lowest/highest price depending on trade direction],
  "take_profit_1": [first target price],
  "take_profit_2": [second target price],
  "take_profit_3": [third target price],
  "entry_price": [entry level if marked]
}""",

        "annotation_focused": """Extract all TEXT ANNOTATIONS and LABELS showing prices on this chart.

SEARCH FOR:
1. Any numbers that look like prices (e.g., 197.63, 1.0823)
2. Labels with "TP1", "TP2", "TP3", "SL", "Entry"
3. Price values in corners or margins
4. Numbers inside colored zones
5. Text overlaid on the chart

COMMON LOCATIONS:
- Inside colored rectangles
- Along the right price axis
- Floating text on the chart
- Near arrows or markers
- In legend or info boxes

READ CAREFULLY:
- Include ALL decimal places
- Don't confuse similar numbers (202 vs 208)
- If multiple prices are close together, they're different levels

Output as JSON with all found prices:
{
  "stop_loss": [price labeled as SL or in red],
  "take_profit_1": [price labeled as TP1],
  "take_profit_2": [price labeled as TP2],
  "take_profit_3": [price labeled as TP3],
  "entry_price": [entry or current price],
  "all_prices_found": [array of all price values seen]
}"""
    }

    def __init__(self, gpt4_api_key: str = None):
        """Initialize with GPT-4 API key"""
        self.openai_client = openai.OpenAI(api_key=gpt4_api_key) if gpt4_api_key else None
        logging.info("Advanced chart extractor initialized with GPT-4 Vision")

    def extract_prices(self, image_path: str, trade_direction: str = "LONG") -> ChartExtractionResult:
        """
        Main extraction pipeline - tries multiple strategies for best results

        Args:
            image_path: Path to chart image
            trade_direction: "LONG" or "SHORT" to validate price relationships
        """
        start_time = time.time()

        try:
            if not os.path.exists(image_path):
                logging.error(f"Image file not found: {image_path}")
                return ChartExtractionResult()

            if not self.openai_client:
                logging.error("No GPT-4 API key provided!")
                return ChartExtractionResult()

            # Try comprehensive strategy first
            logging.info("🔍 Attempting comprehensive extraction strategy...")
            result = self._extract_with_strategy(image_path, "comprehensive")

            # Validate the extraction
            validation_errors = self._validate_extraction(result, trade_direction)

            if not validation_errors:
                logging.info("✅ Comprehensive strategy succeeded!")
                result.validation_passed = True
            else:
                logging.warning(f"⚠️ Validation issues: {validation_errors}")
                result.validation_errors = validation_errors

                # Try box-focused strategy if comprehensive failed
                logging.info("🔍 Trying box-focused extraction strategy...")
                box_result = self._extract_with_strategy(image_path, "box_focused")
                box_errors = self._validate_extraction(box_result, trade_direction)

                if not box_errors or len(box_errors) < len(validation_errors):
                    logging.info("📦 Box-focused strategy provided better results")
                    result = box_result
                    result.validation_errors = box_errors
                    result.validation_passed = not bool(box_errors)
                else:
                    # Try line-focused as last resort
                    logging.info("🔍 Trying line-focused extraction strategy...")
                    line_result = self._extract_with_strategy(image_path, "line_focused")
                    line_errors = self._validate_extraction(line_result, trade_direction)

                    if not line_errors or len(line_errors) < len(validation_errors):
                        logging.info("📈 Line-focused strategy provided better results")
                        result = line_result
                        result.validation_errors = line_errors
                        result.validation_passed = not bool(line_errors)

            result.processing_time = time.time() - start_time

            # Log extraction summary
            self._log_extraction_summary(result)

            return result

        except Exception as e:
            logging.error(f"Extraction failed: {e}", exc_info=True)
            return ChartExtractionResult(
                processing_time=time.time() - start_time,
                validation_errors=[str(e)]
            )

    def _extract_with_strategy(self, image_path: str, strategy: str) -> ChartExtractionResult:
        """Extract prices using a specific strategy"""
        try:
            with open(image_path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')

            prompt = self.EXTRACTION_STRATEGIES.get(strategy, self.EXTRACTION_STRATEGIES["comprehensive"])

            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
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
                max_tokens=500,
                temperature=0
            )

            # Parse response
            content = response.choices[0].message.content.strip()

            # Clean up markdown formatting if present
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0]
            elif '```' in content:
                content = content.split('```')[1].split('```')[0]

            # Parse JSON
            data = json.loads(content)

            result = ChartExtractionResult(
                stop_loss=self._parse_price(data.get('stop_loss')),
                take_profit_1=self._parse_price(data.get('take_profit_1')),
                take_profit_2=self._parse_price(data.get('take_profit_2')),
                take_profit_3=self._parse_price(data.get('take_profit_3')),
                entry_price=self._parse_price(data.get('entry_price')),
                confidence_score=0.85,
                extraction_method=f"gpt4_vision_{strategy}",
                raw_extraction=data
            )

            # Check if we got additional useful data
            if 'current_price' in data and data['current_price'] and not result.entry_price:
                result.entry_price = self._parse_price(data['current_price'])

            # Boost confidence if we found multiple price levels
            found_count = sum([
                result.stop_loss is not None,
                result.take_profit_1 is not None,
                result.take_profit_2 is not None,
                result.take_profit_3 is not None
            ])

            if found_count >= 3:
                result.confidence_score = 0.95
            elif found_count >= 2:
                result.confidence_score = 0.85
            else:
                result.confidence_score = 0.70

            return result

        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse GPT-4 response as JSON: {e}")
            return ChartExtractionResult(extraction_method=f"gpt4_vision_{strategy}_failed")
        except Exception as e:
            logging.error(f"Strategy {strategy} extraction failed: {e}")
            return ChartExtractionResult(extraction_method=f"gpt4_vision_{strategy}_failed")

    def _parse_price(self, value) -> Optional[float]:
        """Parse a price value, handling various formats"""
        if value is None or value == "null":
            return None

        try:
            if isinstance(value, (int, float)):
                return float(value)

            if isinstance(value, str):
                # Remove common formatting
                cleaned = value.replace('$', '').replace(',', '').strip()
                if cleaned and cleaned != 'null':
                    return float(cleaned)
        except (ValueError, TypeError):
            logging.warning(f"Could not parse price value: {value}")

        return None

    def _validate_extraction(self, result: ChartExtractionResult, trade_direction: str) -> List[str]:
        """
        Comprehensive validation of extracted prices
        Returns list of validation errors (empty list means valid)
        """
        errors = []

        # Check if we have at least minimal data
        has_any_data = any([
            result.stop_loss,
            result.take_profit_1,
            result.take_profit_2,
            result.take_profit_3
        ])

        if not has_any_data:
            errors.append("No price levels extracted")
            return errors

        # Collect take profit levels
        tp_levels = []
        if result.take_profit_1:
            tp_levels.append(('TP1', result.take_profit_1))
        if result.take_profit_2:
            tp_levels.append(('TP2', result.take_profit_2))
        if result.take_profit_3:
            tp_levels.append(('TP3', result.take_profit_3))

        # Validate TP ordering
        if len(tp_levels) >= 2:
            for i in range(len(tp_levels) - 1):
                current_name, current_price = tp_levels[i]
                next_name, next_price = tp_levels[i + 1]

                if trade_direction == "LONG":
                    if current_price >= next_price:
                        errors.append(f"LONG trade: {current_name}({current_price}) should be < {next_name}({next_price})")
                else:  # SHORT
                    if current_price <= next_price:
                        errors.append(f"SHORT trade: {current_name}({current_price}) should be > {next_name}({next_price})")

        # Validate SL position relative to TPs
        if result.stop_loss and tp_levels:
            if trade_direction == "LONG":
                # SL should be below all TPs
                for tp_name, tp_price in tp_levels:
                    if result.stop_loss >= tp_price:
                        errors.append(f"LONG trade: SL({result.stop_loss}) should be < {tp_name}({tp_price})")
            else:  # SHORT
                # SL should be above all TPs
                for tp_name, tp_price in tp_levels:
                    if result.stop_loss <= tp_price:
                        errors.append(f"SHORT trade: SL({result.stop_loss}) should be > {tp_name}({tp_price})")

        # Validate entry price if present
        if result.entry_price and result.stop_loss and tp_levels:
            if trade_direction == "LONG":
                # Entry should be between SL and first TP
                if result.entry_price <= result.stop_loss:
                    errors.append(f"LONG trade: Entry({result.entry_price}) should be > SL({result.stop_loss})")
                if tp_levels and result.entry_price >= tp_levels[0][1]:
                    errors.append(f"LONG trade: Entry({result.entry_price}) should be < TP1({tp_levels[0][1]})")
            else:  # SHORT
                # Entry should be between first TP and SL
                if result.entry_price >= result.stop_loss:
                    errors.append(f"SHORT trade: Entry({result.entry_price}) should be < SL({result.stop_loss})")
                if tp_levels and result.entry_price <= tp_levels[0][1]:
                    errors.append(f"SHORT trade: Entry({result.entry_price}) should be > TP1({tp_levels[0][1]})")

        # Check for unrealistic price differences
        all_prices = [p for p in [result.stop_loss, result.take_profit_1,
                                  result.take_profit_2, result.take_profit_3] if p]

        if len(all_prices) >= 2:
            min_price = min(all_prices)
            max_price = max(all_prices)
            price_range = max_price - min_price

            # Check if range is too large (>50% of min price) or too small (<0.1% of min price)
            if min_price > 0:
                range_percent = (price_range / min_price) * 100
                if range_percent > 50:
                    errors.append(f"Price range seems too large: {range_percent:.1f}% of base price")
                elif range_percent < 0.1:
                    errors.append(f"Price range seems too small: {range_percent:.3f}% of base price")

        return errors

    def _log_extraction_summary(self, result: ChartExtractionResult):
        """Log a summary of the extraction results"""
        summary = []

        if result.stop_loss:
            summary.append(f"SL: {result.stop_loss:.4f}")
        if result.take_profit_1:
            summary.append(f"TP1: {result.take_profit_1:.4f}")
        if result.take_profit_2:
            summary.append(f"TP2: {result.take_profit_2:.4f}")
        if result.take_profit_3:
            summary.append(f"TP3: {result.take_profit_3:.4f}")
        if result.entry_price:
            summary.append(f"Entry: {result.entry_price:.4f}")

        if summary:
            logging.info(f"📊 Extracted prices: {' | '.join(summary)}")
            logging.info(f"🎯 Confidence: {result.confidence_score:.1%} | Method: {result.extraction_method}")

            if result.validation_errors:
                logging.warning(f"⚠️ Validation issues: {len(result.validation_errors)} error(s)")
        else:
            logging.warning("❌ No prices extracted from chart")


# Maintain backwards compatibility
HybridChartExtractor = ChartPriceExtractor