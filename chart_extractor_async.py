#!/usr/bin/env python3
"""
Async-compatible Chart Price Extractor to prevent Discord disconnects
Includes timeout handling and better error recovery
"""

import os
import json
import base64
import logging
import openai
import time
import asyncio
from typing import Optional, List, Dict
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor


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
    raw_extraction: Optional[Dict] = None
    error_message: Optional[str] = None


class AsyncChartPriceExtractor:
    """Async chart extractor that won't block Discord heartbeat"""

    # Simplified, more direct prompts for better extraction
    EXTRACTION_STRATEGIES = {
        "simple_direct": """Look at this trading chart and find ALL visible price numbers.

FIND THESE NUMBERS:
- Any number that looks like a price (e.g., 67,234.5 or 1.0823)
- Numbers in RED areas (Stop Loss)
- Numbers in GREEN areas (Take Profits)
- Numbers on the right side (price scale)
- Current price if shown

Return ONLY the prices you can see as JSON:
{
  "stop_loss": [number from red area],
  "take_profit_1": [lowest green area price],
  "take_profit_2": [middle green area price],
  "take_profit_3": [highest green area price],
  "entry_price": [current price or entry],
  "all_visible_prices": [list all numbers you see]
}

If you can't see clear prices, return null for those fields.""",

        "color_zones": """Focus ONLY on colored rectangles/boxes in this chart.

STEP 1: Find all RED rectangles
- What price is shown in or near the red area?

STEP 2: Find all GREEN rectangles
- List each green box's price from lowest to highest

STEP 3: Find current price
- Look for arrows, markers, or "current price" labels

Return as JSON:
{
  "stop_loss": [price in red zone],
  "take_profit_1": [first green zone price],
  "take_profit_2": [second green zone price],
  "take_profit_3": [third green zone price],
  "entry_price": [current/entry price]
}""",

        "text_scan": """Extract ALL text that contains numbers from this chart image.

SCAN FOR:
1. Any text with numbers
2. Labels like "TP", "SL", "Entry"
3. Price axis labels
4. Numbers inside colored areas
5. Floating text annotations

List EVERYTHING you find, then organize into:
{
  "stop_loss": [SL or red zone price],
  "take_profit_1": [TP1 or first target],
  "take_profit_2": [TP2 or second target],
  "take_profit_3": [TP3 or third target],
  "entry_price": [entry or current price],
  "raw_text_found": [all text with numbers]
}"""
    }

    def __init__(self, gpt4_api_key: str = None, max_workers: int = 1):
        """Initialize with GPT-4 API key and thread pool"""
        self.openai_client = openai.OpenAI(api_key=gpt4_api_key) if gpt4_api_key else None
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        logging.info("Async chart extractor initialized")

    async def extract_prices_async(self, image_path: str, trade_direction: str = "LONG") -> ChartExtractionResult:
        """
        Async wrapper for price extraction that won't block Discord

        Args:
            image_path: Path to chart image
            trade_direction: "LONG" or "SHORT"
        """
        loop = asyncio.get_event_loop()

        # Run extraction in thread pool to avoid blocking
        try:
            result = await loop.run_in_executor(
                self.executor,
                self._extract_prices_sync,
                image_path,
                trade_direction
            )
            return result
        except Exception as e:
            logging.error(f"Async extraction failed: {e}")
            return ChartExtractionResult(
                error_message=str(e),
                extraction_method="failed"
            )

    def _extract_prices_sync(self, image_path: str, trade_direction: str) -> ChartExtractionResult:
        """Synchronous extraction with timeout handling"""
        start_time = time.time()

        try:
            if not os.path.exists(image_path):
                return ChartExtractionResult(error_message="Image file not found")

            if not self.openai_client:
                return ChartExtractionResult(error_message="No GPT-4 API key")

            # Try simple direct approach first
            logging.info("Trying simple direct extraction...")
            result = self._try_strategy(image_path, "simple_direct", timeout=10)

            if result and self._has_data(result):
                result.validation_passed = True
                result.processing_time = time.time() - start_time
                return result

            # Try color zones approach
            logging.info("Trying color zones extraction...")
            result = self._try_strategy(image_path, "color_zones", timeout=10)

            if result and self._has_data(result):
                result.validation_passed = True
                result.processing_time = time.time() - start_time
                return result

            # Last resort - text scan
            logging.info("Trying text scan extraction...")
            result = self._try_strategy(image_path, "text_scan", timeout=10)

            if result:
                result.processing_time = time.time() - start_time
                if self._has_data(result):
                    result.validation_passed = True
                else:
                    result.validation_errors = ["No price data extracted from chart"]
                return result

            return ChartExtractionResult(
                error_message="All extraction strategies failed",
                processing_time=time.time() - start_time
            )

        except Exception as e:
            logging.error(f"Extraction error: {e}")
            return ChartExtractionResult(
                error_message=str(e),
                processing_time=time.time() - start_time
            )

    def _try_strategy(self, image_path: str, strategy: str, timeout: int = 10) -> Optional[ChartExtractionResult]:
        """Try a single extraction strategy with timeout"""
        try:
            with open(image_path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')

            prompt = self.EXTRACTION_STRATEGIES.get(strategy, self.EXTRACTION_STRATEGIES["simple_direct"])

            # Make API call with timeout
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
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
                temperature=0,
                timeout=timeout
            )

            # Parse response
            content = response.choices[0].message.content.strip()

            # Clean JSON
            if '```' in content:
                content = content.split('```')[1].replace('json', '').strip()

            data = json.loads(content)

            result = ChartExtractionResult(
                stop_loss=self._parse_price(data.get('stop_loss')),
                take_profit_1=self._parse_price(data.get('take_profit_1')),
                take_profit_2=self._parse_price(data.get('take_profit_2')),
                take_profit_3=self._parse_price(data.get('take_profit_3')),
                entry_price=self._parse_price(data.get('entry_price')),
                extraction_method=f"gpt4_{strategy}",
                raw_extraction=data
            )

            # Calculate confidence
            found_count = sum([
                result.stop_loss is not None,
                result.take_profit_1 is not None,
                result.take_profit_2 is not None,
                result.take_profit_3 is not None
            ])

            result.confidence_score = min(0.95, 0.25 * found_count + 0.2)

            return result

        except json.JSONDecodeError as e:
            logging.warning(f"JSON parse error in {strategy}: {e}")
            return None
        except Exception as e:
            logging.warning(f"Strategy {strategy} failed: {e}")
            return None

    def _parse_price(self, value) -> Optional[float]:
        """Parse various price formats"""
        if value is None or value == "null":
            return None

        try:
            if isinstance(value, (int, float)):
                return float(value)

            if isinstance(value, str):
                # Handle comma-separated numbers like "67,234.5"
                cleaned = value.replace('$', '').replace(',', '').strip()
                if cleaned and cleaned != 'null':
                    return float(cleaned)
        except (ValueError, TypeError):
            pass

        return None

    def _has_data(self, result: ChartExtractionResult) -> bool:
        """Check if result has any useful data"""
        return any([
            result.stop_loss,
            result.take_profit_1,
            result.take_profit_2,
            result.take_profit_3,
            result.entry_price
        ])

    def cleanup(self):
        """Cleanup thread pool"""
        self.executor.shutdown(wait=False)


# Compatibility wrapper for existing code
class ChartPriceExtractor:
    """Wrapper to maintain compatibility with existing code"""

    def __init__(self, gpt4_api_key: str = None):
        self.async_extractor = AsyncChartPriceExtractor(gpt4_api_key)

    def extract_prices(self, image_path: str, trade_direction: str = "LONG") -> ChartExtractionResult:
        """Synchronous extraction for compatibility"""
        return self.async_extractor._extract_prices_sync(image_path, trade_direction)


# Maintain backwards compatibility
HybridChartExtractor = ChartPriceExtractor