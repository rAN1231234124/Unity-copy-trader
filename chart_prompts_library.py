#!/usr/bin/env python3
"""
Library of specialized prompts for different chart extraction scenarios
These can be used to enhance the chart_extractor.py for specific chart types
"""

# Collection of specialized prompts for different scenarios

PROMPT_TEMPLATES = {
    # === PRIMARY EXTRACTION PROMPTS ===

    "trading_view_style": """Analyze this TradingView-style chart and extract trading levels.

TRADINGVIEW SPECIFIC ELEMENTS:
1. Position boxes with prices inside
2. Horizontal ray lines with price labels
3. Price labels on the right scale
4. Position size indicators
5. Risk/Reward ratio display

LOOK FOR:
- Red position box = Stop Loss
- Green position boxes = Take Profits (usually 3)
- Entry line with arrow
- Current price indicator

Extract exact prices and return as JSON:
{
  "stop_loss": [number],
  "take_profit_1": [number],
  "take_profit_2": [number],
  "take_profit_3": [number],
  "entry_price": [number]
}""",

    "mobile_screenshot": """Extract trading levels from this mobile trading app screenshot.

MOBILE CHART FEATURES:
- Compact price display
- Touch-friendly large text
- Simplified color coding
- Price bubbles or callouts
- Swipe indicators

COMMON ELEMENTS:
- Red area/line = Stop Loss
- Green areas = Profit targets
- Current price in header/status bar
- Order details in bottom panel

Read all visible prices and return as JSON.""",

    "professional_platform": """Extract precise price levels from this professional trading platform.

PLATFORM ELEMENTS TO CHECK:
1. Order panel (usually on right)
2. Chart with price levels
3. DOM (Depth of Market) ladder
4. Position summary box
5. P&L display

PRICE LOCATIONS:
- Pending orders list
- Chart annotations
- Order entry form
- Position details

Extract ALL price levels with maximum precision.""",

    # === FALLBACK EXTRACTION PROMPTS ===

    "ocr_focused": """Perform OCR to extract ALL numeric values from this chart image.

INSTRUCTIONS:
1. Scan the entire image for any numbers
2. Focus on decimal numbers (e.g., 197.63, 1.0823)
3. Look in corners, margins, and overlays
4. Check legend boxes and info panels

GROUP NUMBERS BY CONTEXT:
- Numbers in red areas = likely Stop Loss
- Numbers in green areas = likely Take Profits
- Largest/most prominent number = likely current price

Return all numbers found with their context.""",

    "color_analysis": """Analyze colors to identify trading zones and extract associated prices.

COLOR MAPPING:
- RED/PINK zones = Stop Loss area
- GREEN/LIME zones = Take Profit areas
- YELLOW/ORANGE = Entry or caution zones
- BLUE/CYAN = Alternative profit zones
- GRAY/WHITE = Support/resistance

FOR EACH COLORED ZONE:
1. Identify the color and shape
2. Find any text/numbers within or near it
3. Note the vertical position on the chart

Return zones with their associated price values.""",

    # === VALIDATION PROMPTS ===

    "double_check": """Verify the extracted price levels from this trading chart.

PREVIOUSLY EXTRACTED:
Stop Loss: {stop_loss}
TP1: {take_profit_1}
TP2: {take_profit_2}
TP3: {take_profit_3}

VERIFICATION TASKS:
1. Confirm these prices are visible on the chart
2. Check if the order makes logical sense
3. Look for any missed price levels
4. Verify decimal places are correct

Return corrected values if any errors found.""",

    "relationship_check": """Analyze the price relationships on this trading chart.

DETERMINE:
1. Is this a LONG or SHORT trade setup?
2. What is the current market price?
3. Where is the entry point?
4. Are stop loss and take profits logically placed?

VALIDATION:
- For LONG: SL < Entry < TP1 < TP2 < TP3
- For SHORT: TP1 > TP2 > TP3 > Entry > SL

Extract and validate all price levels.""",

    # === SPECIALIZED EXTRACTION PROMPTS ===

    "fibonacci_levels": """Extract Fibonacci retracement/extension levels from this chart.

LOOK FOR:
- Horizontal lines at Fib levels (23.6%, 38.2%, 50%, 61.8%, etc.)
- Price values at these levels
- Which levels are marked as targets or stops

COMMON USAGE:
- 61.8% or 78.6% level often used as Stop Loss
- Extension levels (127.2%, 161.8%, 261.8%) as Take Profits

Extract the relevant price levels.""",

    "support_resistance": """Identify support and resistance levels being used for trade setup.

IDENTIFY:
- Major horizontal S/R lines
- Previous swing highs/lows
- Round number levels
- Volume profile peaks

DETERMINE:
- Which S/R level is the Stop Loss
- Which levels are profit targets
- Entry point relative to S/R

Extract exact price values for trade levels.""",

    "order_flow": """Extract prices from order flow or footprint chart.

LOOK FOR:
- Volume clusters at price levels
- Delta divergences
- POC (Point of Control)
- Value area boundaries
- Aggressive buying/selling zones

IDENTIFY:
- Stop placement below/above volume voids
- Targets at high volume nodes
- Entry at imbalance zones

Extract relevant trading levels.""",

    "range_breakout": """Extract breakout trade levels from this range-bound chart.

IDENTIFY:
- Range boundaries (resistance and support)
- Breakout level
- Stop loss (usually opposite range boundary)
- Targets based on range height

MEASURE:
- Range height for projection
- Breakout confirmation level
- False breakout stop

Extract all relevant price levels.""",

    # === MULTI-TIMEFRAME PROMPTS ===

    "multiple_timeframes": """Extract price levels from multi-timeframe chart display.

IMPORTANT:
- Focus on the main/largest timeframe
- Ignore conflicting levels from other timeframes
- Look for confluence zones

PRIORITY:
1. Levels visible on all timeframes
2. Higher timeframe levels
3. Most recent/current setup

Extract the active trade levels only.""",

    # === ERROR RECOVERY PROMPTS ===

    "partial_view": """Extract whatever price information is visible in this partial chart view.

WORK WITH WHAT'S VISIBLE:
- Even if chart is cropped
- Even if some text is cut off
- Use price scale to estimate if needed

PRIORITY:
1. Any clearly visible prices
2. Partial numbers you can complete
3. Relative positions if absolute values unclear

Provide best effort extraction with confidence scores.""",

    "low_quality": """Extract price levels from this low quality/compressed chart image.

CHALLENGES:
- Blurry text
- JPEG artifacts
- Low resolution
- Color bleeding

STRATEGIES:
- Focus on larger text
- Use context for unclear digits
- Look for repeated patterns
- Compare similar shapes

Extract prices with confidence levels for each."""
}


def get_prompt_for_scenario(scenario: str, **kwargs) -> str:
    """
    Get appropriate prompt for specific scenario

    Args:
        scenario: Type of chart or extraction scenario
        **kwargs: Variables to format into prompt

    Returns:
        Formatted prompt string
    """
    prompt = PROMPT_TEMPLATES.get(scenario, PROMPT_TEMPLATES["comprehensive"])

    # Format prompt with any provided values
    if kwargs:
        try:
            prompt = prompt.format(**kwargs)
        except KeyError:
            pass  # Ignore missing keys

    return prompt


# Validation rules for different asset types
VALIDATION_RULES = {
    "crypto": {
        "max_range_percent": 50,    # Crypto can move 50% in a trade
        "min_range_percent": 0.5,    # Minimum 0.5% move expected
        "decimal_places": 2,         # Usually 2-8 decimal places
        "typical_risk_reward": 3.0   # Often aim for 1:3 risk:reward
    },
    "forex": {
        "max_range_percent": 5,      # Forex rarely moves >5% in a trade
        "min_range_percent": 0.01,   # Can have very small moves
        "decimal_places": 4,         # Usually 4-5 decimal places
        "typical_risk_reward": 2.0   # Often aim for 1:2 risk:reward
    },
    "stocks": {
        "max_range_percent": 20,     # Stocks can move 20% in a trade
        "min_range_percent": 0.1,    # Minimum 0.1% move expected
        "decimal_places": 2,         # Usually 2 decimal places
        "typical_risk_reward": 2.5   # Often aim for 1:2.5 risk:reward
    },
    "futures": {
        "max_range_percent": 10,     # Futures moderate volatility
        "min_range_percent": 0.05,   # Small moves possible
        "decimal_places": 2,         # Varies by contract
        "typical_risk_reward": 2.0   # Often aim for 1:2 risk:reward
    }
}


def validate_by_asset_type(prices: dict, asset_type: str = "crypto") -> list:
    """
    Validate extracted prices based on asset type characteristics

    Args:
        prices: Dictionary of extracted prices
        asset_type: Type of asset (crypto, forex, stocks, futures)

    Returns:
        List of validation warnings
    """
    warnings = []
    rules = VALIDATION_RULES.get(asset_type, VALIDATION_RULES["crypto"])

    # Check if prices exist
    price_values = [v for v in prices.values() if v is not None]
    if len(price_values) < 2:
        return ["Insufficient price data for validation"]

    # Calculate range
    min_price = min(price_values)
    max_price = max(price_values)
    price_range = max_price - min_price

    if min_price > 0:
        range_percent = (price_range / min_price) * 100

        # Check if range is reasonable
        if range_percent > rules["max_range_percent"]:
            warnings.append(f"Price range ({range_percent:.1f}%) exceeds typical {asset_type} movement")
        elif range_percent < rules["min_range_percent"]:
            warnings.append(f"Price range ({range_percent:.3f}%) seems too small for {asset_type}")

    # Check risk:reward ratio if we have SL and TP
    if prices.get('stop_loss') and prices.get('take_profit_1') and prices.get('entry_price'):
        risk = abs(prices['entry_price'] - prices['stop_loss'])
        reward = abs(prices['take_profit_1'] - prices['entry_price'])

        if risk > 0:
            rr_ratio = reward / risk
            if rr_ratio < 1.0:
                warnings.append(f"Risk:Reward ratio ({rr_ratio:.1f}) is less than 1:1")
            elif rr_ratio > 10.0:
                warnings.append(f"Risk:Reward ratio ({rr_ratio:.1f}) seems unrealistic")

    return warnings


# Chart pattern recognition helpers
def identify_chart_type(image_features: dict) -> str:
    """
    Identify the type of chart based on visual features

    Args:
        image_features: Dictionary describing image characteristics

    Returns:
        Best matching chart type
    """
    # This would be enhanced with actual image analysis
    # For now, returning a basic classification

    if image_features.get('has_volume_bars'):
        return 'professional_platform'
    elif image_features.get('is_mobile_aspect'):
        return 'mobile_screenshot'
    elif image_features.get('has_fibonacci'):
        return 'fibonacci_levels'
    elif image_features.get('has_range_box'):
        return 'range_breakout'
    else:
        return 'trading_view_style'