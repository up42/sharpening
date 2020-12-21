"""
End-to-end test: Fetches data, creates output, stores it in /tmp and checks if output
is valid.
"""

from pathlib import Path

import geojson

from blockutils.e2e import E2ETest

# Disable unused params for assert
# pylint: disable=unused-argument
def asserts(input_dir: Path, output_dir: Path, quicklook_dir: Path, logger):
    # Print out bbox of one tile
    geojson_path = output_dir / "data.json"

    with open(str(geojson_path)) as f:
        feature_collection = geojson.load(f)

    logger.info(feature_collection.features[0].bbox)

    # Check number of files in output_prefix
    output_sharpen = output_dir / Path(
        feature_collection.features[0].properties["up42.data_path"]
    )

    logger.info(output_sharpen)

    assert output_sharpen.exists()


if __name__ == "__main__":
    e2e = E2ETest("sharpening")
    e2e.add_gs_bucket(
        "gs://floss-blocks-e2e-testing/e2e_sharpening/sentinel2_rgb/input/*"
    )
    e2e.asserts = asserts
    e2e.run()
