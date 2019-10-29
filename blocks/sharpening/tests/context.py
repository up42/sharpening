import os
import sys

# Path hacks to make the code available for testing
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

# Import the required classes and functions
# pylint: disable=unused-import,wrong-import-position
from src.sharpening import RasterSharpener
from src.helpers import (
    AOICLIPPED,
    LOG_FORMAT,
    get_logger,
    load_params,
    ensure_data_directories_exist,
    setup_test_directories,
)
