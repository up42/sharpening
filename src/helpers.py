import os
import json
from pathlib import Path
import shutil
import logging
from typing import Any, Iterable, Union, Tuple

from geojson import Feature, FeatureCollection
import rasterio as rio
from rasterio.windows import Window
import numpy as np


IN_CAPABILITY = "up42.data.aoiclipped"
OUT_CAPABILITY = "up42.data.aoiclipped"

LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


def get_logger(name, level=logging.DEBUG):
    logger = logging.getLogger(name)
    logger.setLevel(level)
    # create console handler and set level to debug
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    formatter = logging.Formatter(LOG_FORMAT)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    return logger


def set_capability(feature: Feature, capability: str, value: Any) -> Feature:
    feature["properties"][capability] = value
    return feature


def ensure_data_directories_exist():
    Path("/tmp/input/").mkdir(parents=True, exist_ok=True)
    Path("/tmp/output/").mkdir(parents=True, exist_ok=True)
    Path("/tmp/quicklooks/").mkdir(parents=True, exist_ok=True)


def setup_test_directories(test_dir: Path):
    """
    Creates given test directory (usually /tmp or /tmp/e2e_test) and empty input/output/quicklook subfolders.
    """
    test_dir.mkdir(parents=True, exist_ok=True)

    for folder in ["input", "output", "quicklooks"]:
        try:
            shutil.rmtree(test_dir / folder)
            Path(test_dir / folder).mkdir(parents=True, exist_ok=True)
        # Deleting subfolder sometimes does not work in temp, then remove all subfiles.
        except (PermissionError, OSError):
            Path(test_dir / folder).mkdir(parents=True, exist_ok=True)
            files_to_delete = Path(test_dir / folder).rglob("*.*")
            for file_path in files_to_delete:
                file_path.unlink()


def get_in_out_feature_names_and_paths(
    in_feature: Feature, in_capability: str, postfix: str = ""
) -> Tuple[str, str, Path, Path]:
    """
    Utility to generate the input and output feature names and file paths. Will create
    parent directory(ies) of output file by default. Optionally augments the output filename
    with a postfix.

    Parameters
    ----------
    in_feature : A Feature of a GeoJSON FeatureCollection describing all input datasets
    in_capability: Input capability key.
    postfix : (Optional) Additional string to add to the end of the file name before
        the file suffix. Adds "_" plus postfix.

    Returns
    -------
        Tuple with str of in- & output feature names and in- & output file paths.
    """
    in_feature_name = in_feature["properties"][in_capability]
    in_feature_path = Path("/tmp/input") / in_feature_name

    if postfix == "":
        out_feature_name = in_feature_name
    else:
        in_feature_name = Path(in_feature_name)
        out_feature_name = in_feature_name.with_name(
            in_feature_name.stem + "_" + postfix + in_feature_name.suffix
        )
    out_feature_path = Path("/tmp/output") / out_feature_name
    out_feature_path.parent.mkdir(parents=True, exist_ok=True)

    return (
        str(in_feature_name),
        str(out_feature_name),
        in_feature_path,
        out_feature_path,
    )


def load_params() -> dict:
    """
    Get the parameters for the current task directly from the task parameters.
    """
    helper_logger = get_logger(__name__)
    data: str = os.environ.get("UP42_TASK_PARAMETERS", "{}")
    helper_logger.debug("Fetching parameters for this block: %s", data)
    if data == "":
        data = "{}"
    return json.loads(data)


def load_metadata() -> FeatureCollection:
    """
    Get the geojson metadata from the provided location
    """
    ensure_data_directories_exist()
    if os.path.exists("/tmp/input/data.json"):
        with open("/tmp/input/data.json") as fp:
            data = json.loads(fp.read())

        features = []
        for feature in data["features"]:
            features.append(Feature(**feature))

        return FeatureCollection(features)
    else:
        return FeatureCollection([])


def save_metadata(result: FeatureCollection):
    """
    Save the geojson metadata to the provided location
    """
    ensure_data_directories_exist()
    with open("/tmp/output/data.json", "w") as json_file:
        json_file.write(json.dumps(result))


class WindowsUtil:
    """
    Utility class to handle raster IO in windows. Can do regular windows, buffered
    windows and transform windows.
    """

    def __init__(self, rio_ds: Union[rio.io.DatasetReader, rio.io.DatasetWriter]):
        """
        Initialize the instance with a rasterio dataset (read or write).
        """
        self.rio_ds = rio_ds
        self.windows = rio_ds.block_windows(1)

    def windows_buffered(self, buffer: int = 0) -> Iterable[Window]:
        """
        Method that returns a buffered windows with a given int buffer in each
        direction, limited to the raster boundaries.
        """
        for _, window in self.windows:
            buffered_window = self.buffer_window(window, buffer)
            yield window, buffered_window

    def buffer_window(self, window: Window, buffer: int) -> Window:
        """
        Buffers a window with a set number of pixels (buffer) in every possible direction
        given a shape of the overall raster file where window is derived from.
        For instance, if window matches the shape of the source raster file, the shape
        of the source raster file is returned in window format.
        window:
            Original window (for instance from block)
        buffer:
            Number of pixels to buffer by where possible
        """
        row_slice, col_slice = window.toslices()

        can_row_start = row_slice.start - buffer
        can_row_stop = row_slice.stop + buffer

        can_col_start = col_slice.start - buffer
        can_col_stop = col_slice.stop + buffer

        out_row_slice = slice(can_row_start, can_row_stop)
        out_col_slice = slice(can_col_start, can_col_stop)

        buffered_window = Window.from_slices(
            out_row_slice, out_col_slice, boundless=True
        )
        limited_buffered_window = self.limit_window_to_raster_bounds(buffered_window)
        return limited_buffered_window

    def limit_window_to_raster_bounds(
        self, window: Window, dst_height: int = None, dst_width: int = None
    ) -> Window:
        """
        Make sure the window fits in the dst raster. If not "clips" window to the
        bounds of the raster.
        This method is required because when applying a transform in the Windows
        precision in the Affine transformation can cause inconsistencies on the
        size of the windows in relation to the final output file.
        """
        if dst_height is None:
            dst_height = int(self.rio_ds.height)
        if dst_width is None:
            dst_width = int(self.rio_ds.width)

        window_slices_row, window_slices_col = window.toslices()
        result_row = [int(window_slices_row.start), int(window_slices_row.stop)]
        result_col = [int(window_slices_col.start), int(window_slices_col.stop)]

        if window_slices_row.start < 0:
            result_row[0] = 0
        if window_slices_row.stop > dst_height:
            result_row[1] = dst_height

        if window_slices_col.start < 0:
            result_col[0] = 0
        if window_slices_col.stop > dst_width:
            result_col[1] = dst_width

        return Window.from_slices(result_row, result_col)

    def crop_array_to_window(
        self, buffered_array: np.array, window: Window, window_buffer: Window
    ) -> np.array:
        """
        Crops an array created with the windows_buffered to the extent of
        window. Makes use of the a higher res Affine to "reproject" the original
        window to the extent of window_buffer.
        buffered_array:
            Buffered array read with window_buffer. Has same shape as buffered window.
        window:
            Original window. Buffered window cropped with a given buffer.
        window_buffer:
            Buffered window.
        """
        buffer_transform = rio.windows.transform(window_buffer, self.rio_ds.transform)
        window_transformed = rio.windows.from_bounds(
            *rio.windows.bounds(window, transform=self.rio_ds.transform),
            transform=buffer_transform
        )

        # row, col
        (
            window_buffer_slices_row,
            window_buffer_slices_col,
        ) = window_transformed.toslices()

        slice_col_start = int(round(window_buffer_slices_col.start))
        slice_row_start = int(round(window_buffer_slices_row.start))

        slice_col_stop = int(round(window_buffer_slices_col.stop))
        slice_row_stop = int(round(window_buffer_slices_row.stop))

        cropped_array = buffered_array[
            :, slice_row_start:slice_row_stop, slice_col_start:slice_col_stop
        ]
        return cropped_array
