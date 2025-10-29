#!/usr/bin/env python3
"""Test which import is causing the hang"""

import sys
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

logging.info(f"Python version: {sys.version}")
logging.info(f"Platform: {sys.platform}")

logging.info("1. Importing standard libraries...")
import os
import json
from pathlib import Path
logging.info("✓ Standard libraries imported")

logging.info("2. Importing discord...")
import discord
logging.info("✓ Discord imported")

logging.info("3. Importing asyncio...")
import asyncio
logging.info("✓ Asyncio imported")

logging.info("4. Importing OpenCV...")
import warnings
warnings.filterwarnings('ignore', category=UserWarning, module='numpy')
warnings.filterwarnings('ignore', message='.*experimental.*')

import cv2
logging.info("✓ OpenCV imported")

logging.info("5. Importing NumPy...")
import numpy as np
logging.info(f"✓ NumPy imported - version: {np.__version__}")

logging.info("6. Testing basic NumPy operations...")
arr = np.array([1, 2, 3])
result = arr * 2
logging.info(f"✓ NumPy operations work: {arr} * 2 = {result}")

logging.info("7. Importing chart_extractor...")
from chart_extractor import HybridChartExtractor
logging.info("✓ Chart extractor imported")

logging.info("8. Testing complete - all imports successful!")