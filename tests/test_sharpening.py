import os
from pathlib import Path
from unittest import mock
from typing import List
import shutil

from shapely.geometry import box
import pytest
from geojson import FeatureCollection, Feature
import rasterio as rio
import numpy as np

from blockutils.common import (
    ensure_data_directories_exist,
    setup_test_directories,
)

from context import RasterSharpener


@pytest.fixture(scope="session", autouse=True)
def fixture():
    ensure_data_directories_exist()


# pylint: disable=redefined-outer-name
@pytest.fixture(scope="session")
def tmp_raster_fixture():
    """
    Copies the 3-band RGB Sentinel-2 small test image to the tmp input folder.
    :return: The input and output file paths.
    """
    test_dir = Path("/tmp")
    input_dir = test_dir / "input"
    setup_test_directories(test_dir)

    _location_ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
    mock_input_dir = os.path.join(_location_, "mock_data/sentinel2_rgb/input")
    shutil.rmtree(input_dir)
    shutil.copytree(mock_input_dir, input_dir)

    in_path = Path(
        "/tmp/input/3037abae-a132-4f7a-b506-fd6e2a0b4492/3a59da06-271d-45b2-"
        "9f3f-95038227af47.tif"
    )
    out_path = Path(str(in_path).replace("input", "output"))
    out_path = out_path.with_name(in_path.stem + "_sharpened.tif")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    return in_path, out_path


@pytest.fixture(scope="session")
def test_array_fixture():
    """
    Reads the 3-band RGB Sentinel-2 small test image.
    :return: 3d-array
    """
    _location_ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
    mock_input_path = os.path.join(
        _location_,
        "mock_data/sentinel2_rgb/input/3037abae-"
        "a132-4f7a-b506-fd6e2a0b4492/3a59da06-"
        "271d-45b2-9f3f-95038227af47.tif",
    )

    with rio.open(str(mock_input_path), "r") as src:
        band_count = src.meta["count"]
        img_array = np.stack(list(src.read(range(1, band_count + 1))))

    return img_array


@pytest.fixture()
def small_image():
    test_dir = Path("/tmp")
    input_dir = test_dir / "input"
    setup_test_directories(test_dir)

    _location_ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
    mock_input_dir = os.path.join(_location_, "mock_data/small_image/")
    shutil.rmtree(input_dir)
    shutil.copytree(mock_input_dir, input_dir)

    in_path = Path("/tmp/input/2622dbb9-2b2c-49cd-805d-717265d011ea.tif")
    out_path = Path(str(in_path).replace("input", "output"))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    return in_path, out_path


def test_from_dict():
    mock_dict_complete = {"strength": "strong"}
    sharpen_mock_dict_complete = RasterSharpener.from_dict(mock_dict_complete)
    assert sharpen_mock_dict_complete.strength == "strong"

    mock_dict_empty = {}
    sharpen_mock_dict_complete = RasterSharpener.from_dict(mock_dict_empty)
    assert sharpen_mock_dict_complete.strength == "medium"


def test_sharpen_array(test_array_fixture):
    sharpened = RasterSharpener().sharpen_array(test_array_fixture)
    assert sharpened.shape == (4, 256, 256)


def test_sharpen_raster(tmp_raster_fixture):
    in_path, out_path = tmp_raster_fixture
    RasterSharpener().sharpen_raster(in_path, out_path)
    assert out_path.exists()


@pytest.mark.parametrize(
    "strength, expected_mean",
    [
        ("light", 119.61306762695312),
        ("medium", 119.53784942626953),
        ("strong", 120.20846176147461),
    ],
)
# pylint: disable=unused-argument
def test_raster_sharpening_expected_pixel_values(
    tmp_raster_fixture, strength, expected_mean
):
    in_path, out_path = tmp_raster_fixture

    params_dict = {"strength": strength}

    RasterSharpener().from_dict(params_dict).sharpen_raster(in_path, out_path)
    assert out_path.exists()

    with rio.open(str(out_path), "r") as src:
        band_count = src.meta["count"]
        assert band_count == 4

        img_array = np.stack(list(src.read(range(1, band_count + 1))))

        assert img_array.shape == (4, 256, 256)
        assert img_array.mean() == expected_mean


def test_process(tmp_raster_fixture):
    """
    Checks the raster processing for multiple images.
    """
    in_path, _ = tmp_raster_fixture
    img_file_list = [in_path]

    feature_list: List[Feature] = []
    for img_path in img_file_list:
        bbox = [2.5, 1.0, 4.0, 5.0]
        geom = box(*bbox)

        in_properties = {
            "up42.data_path": str(Path(*img_path.parts[-2:])),
            "acquisitionDate": "2018-10-16T10:39:43.431Z",
        }
        feature_list.append(Feature(geometry=geom, bbox=bbox, properties=in_properties))
    input_fc = FeatureCollection(feature_list)

    output_fc = RasterSharpener().process(input_fc)

    # Check that all features are derived
    assert len(output_fc["features"]) == 1

    for feature in output_fc.features:
        # Check that file paths in metadata are relative
        feature_file = feature["properties"]["up42.data_path"]
        assert feature["properties"]["up42.data_path"]
        assert Path(feature_file).root == ""
        # Check that metadata is propagated
        assert feature["properties"]["acquisitionDate"] == "2018-10-16T10:39:43.431Z"
        # Check that feature outputs exist
        feature_path = Path("/tmp/output").joinpath(feature_file)
        assert feature_path.is_file()
        # Cleanup
        feature_path.unlink()


def test_process_data_path(tmp_raster_fixture):
    """
    Checks the raster processing for multiple images.
    """
    in_path, _ = tmp_raster_fixture
    img_file_list = [in_path]

    feature_list: List[Feature] = []
    for img_path in img_file_list:
        bbox = [2.5, 1.0, 4.0, 5.0]
        geom = box(*bbox)

        in_properties = {
            "up42.data_path": str(Path(*img_path.parts[-2:])),
            "acquisitionDate": "2018-10-16T10:39:43.431Z",
        }
        feature_list.append(Feature(geometry=geom, bbox=bbox, properties=in_properties))
    input_fc = FeatureCollection(feature_list)

    output_fc = RasterSharpener().process(input_fc)

    # Check that all features are derived
    assert len(output_fc["features"]) == 1

    for feature in output_fc.features:
        # Check that file paths in metadata are relative
        feature_file = feature["properties"]["up42.data_path"]
        assert feature["properties"]["up42.data_path"]
        assert Path(feature_file).root == ""
        # Check that metadata is propagated
        assert feature["properties"]["acquisitionDate"] == "2018-10-16T10:39:43.431Z"
        # Check that feature outputs exist
        feature_path = Path("/tmp/output").joinpath(feature_file)
        assert feature_path.is_file()
        # Cleanup
        feature_path.unlink()


@mock.patch.dict(
    "os.environ", {"UP42_TASK_PARAMETERS": '{"strength": "light"}'},
)
def test_run(tmp_raster_fixture):
    """
    Checks the raster processing for multiple images.
    """
    _, out_path = tmp_raster_fixture

    # Set params via env vars and load them
    os.environ[
        "UP42_TASK_PARAMETERS"
    ] = """
    {
      "strength": "light"
    }
    """

    RasterSharpener().run()

    assert out_path.exists()


# pylint: disable=unused-argument
@mock.patch.dict(
    "os.environ",
    {"UP42_TASK_PARAMETERS": '{"strength": {"type": "string", "default": "medium"}'},
)
def test_run_wrong_params(small_image):
    """
    Checks what happens when a wrong param type is passed,
    """

    with pytest.raises(ValueError):
        RasterSharpener().run()
