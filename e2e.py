"""
End-to-end test: Fetches data, creates output, stores it in /tmp and checks if output
is valid.
"""

from pathlib import Path
import os
import sys

import geojson

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))
from helpers import setup_test_directories  # pylint: disable=wrong-import-position


if __name__ == "__main__":
    TESTNAME = "e2e_sharpening"
    TEST_DIR = Path("/tmp") / TESTNAME
    INPUT_DIR = TEST_DIR / "input"
    OUTPUT_DIR = TEST_DIR / "output"
    setup_test_directories(TEST_DIR)

    os.system(
        "gsutil cp -r gs://floss-blocks-e2e-testing/e2e_sharpening/sentinel2_rgb/input/ %s"
        % TEST_DIR
    )

    RUN_CMD = (
        """docker run -v %s:/tmp \
                 -e 'UP42_TASK_PARAMETERS={}' \
                  -it sharpening"""
        % TEST_DIR
    )

    os.system(RUN_CMD)

    # Print out bbox of one tile
    GEOJSON_PATH = OUTPUT_DIR / "data.json"

    with open(str(GEOJSON_PATH)) as f:
        FEATURE_COLLECTION = geojson.load(f)

    print(FEATURE_COLLECTION.features[0].bbox)

    # Check number of files in output_prefix
    OUTPUT_SHARPEN = OUTPUT_DIR / Path(
        FEATURE_COLLECTION.features[0].properties["up42.data_path"]
    )

    print(OUTPUT_SHARPEN)

    assert OUTPUT_SHARPEN.exists()
