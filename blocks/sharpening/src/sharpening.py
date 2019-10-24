from typing import List, Dict, Union
from pathlib import Path
from geojson import FeatureCollection, Feature

import numpy as np
import rasterio as rio
from scipy import ndimage

from helpers import (
    AOICLIPPED,
    set_capability,
    get_logger,
    save_metadata,
    load_params,
    load_metadata,
    ensure_data_directories_exist,
    WindowsUtil
)

logger = get_logger(__name__)


class RasterSharpener:
    def __init__(self, strength: str = "medium", filter_method: str = "kernel"):
        """
        This class implements a high-pass image filtering method to sharpen a raster.

        :strength: Strength of the sharpening operation, one of "medium" (default),
            "light", "strong".
        :filter_method: Used high-pass image filter, "gaussian" (default) or "kernel".
        """
        self.strength = strength
        self.filter_method = filter_method

    @staticmethod
    def gaussian_filter(in_array: np.ndarray, alpha: int = 15) -> np.ndarray:
        """
        This gaussian highpass filter works by sharpening a blurred image, then
        increasing the weight of the edges by adding an approximation of the Laplacian.

        :in_array: Input 2d-array
        :param alpha: Alpha value to highlight edges
        :return: Sharpened output 2d-array
        """
        blurred = ndimage.gaussian_filter(in_array, sigma=3)
        filter_blurred = ndimage.gaussian_filter(blurred, sigma=1)
        noise = blurred - filter_blurred
        sharpened = in_array - alpha * noise
        return sharpened

    def sharpen_array(
        self,
        in_array: np.ndarray,
        strength: str = "medium",
        filter_method: str = "kernel",
    ) -> np.ndarray:
        """
        Runs the sharpening operation on the input array, returns a sharpened output
            array.

        :param in_array: Input 3d-array
        :param strength: Strength of the sharpening operation, one of "medium"
            (default), "light", "strong".
        :param filter_method: Used high-pass image filter, "kernel" (default) or
            "gaussian".
        :return: Sharpened output 3d-array
        """
        if strength == "light":
            alpha = 5
            kernel = np.array([[0, -1 / 8, 0], [-1 / 8, 3, -1 / 8], [0, -1 / 8, 0]])
        elif strength == "medium":
            alpha = 15
            kernel = np.array([[0, -1 / 4, 0], [-1 / 4, 2, -1 / 4], [0, -1 / 4, 0]])
        elif strength == "strong":
            alpha = 22
            kernel = np.array([[0, -1 / 4, 0], [-1 / 4, 7 / 4, -1 / 4], [0, -1 / 4, 0]])

        if filter_method == "kernel":
            # TODO: Exclude alpha band from convolution by sensor bands definition / capabilities.
            sharpened = np.array(
                [
                    ndimage.convolve(band_ar, kernel)
                    for band_ar in in_array.astype(kernel.dtype)
                ]
            )
        elif filter_method == "gaussian":
            sharpened = np.array(
                [
                    self.gaussian_filter(band_ar, alpha=alpha)
                    for band_ar in in_array.astype(kernel.dtype)
                ]
            )
        # Resolve potential array overflow by clipping to min/max values of input datatype.
        sharpened = np.clip(
            sharpened,
            np.iinfo(in_array.dtype).min,
            np.iinfo(in_array.dtype).max,
            out=sharpened,
        )
        sharpened = sharpened.astype(in_array.dtype)

        return sharpened

    def sharpen_raster(
        self, input_file_path: Union[str, Path], output_file_path: Union[str, Path]
    ) -> None:
        """
        Reads the input geotiff raster file, runs the sharpening operation on the array
        and writes the sharpened array back to the output geotiff raster.

        :param input_file_path: The location of the input file on the file system
        :param output_file_path: The location of the output file on the file system
        """

        with rio.open(str(input_file_path), "r") as src:
            logger.info("src.meta: %s", src.meta)
            out_profile = src.profile.copy()
            band_count = src.meta["count"]

            with rio.open(str(output_file_path), "w", **out_profile) as dst:

                if self.filter_method == 'kernel':
                    # Windowed read and write, buffered window by 2 pixels to enable correct 3x3 kernel operation.
                    windows_util = WindowsUtil(src)

                    for window, window_buffered in windows_util.windows_buffered(buffer=2):

                        img_array = np.stack(list(src.read(range(1, band_count + 1), window=window_buffered)))

                        sharpened = self.sharpen_array(
                            img_array, strength=self.strength, filter_method=self.filter_method
                        )

                        # Crop result to original window
                        sharpened = windows_util.crop_array_to_window(sharpened,
                                                                          window,
                                                                          window_buffered)

                        for i in range(band_count):
                            dst.write(sharpened[i, ...], i + 1, window=window)

                elif self.filter_method == 'gaussian':
                    # TODO: Gaussian filter is not compatible with windowed read/write
                    # TODO: (regardless of window buffer size) as
                    # TODO: ndimage.gaussian_filter apparently uses image normalization.
                    img_array = np.stack(list(src.read(range(1, band_count + 1))))

                    sharpened = self.sharpen_array(
                        img_array, strength=self.strength, filter_method=self.filter_method
                    )

                    for i in range(band_count):
                        dst.write(sharpened[i, ...], i + 1)

    def process(self, metadata: FeatureCollection) -> FeatureCollection:
        """
        Given the necessary parameters and a feature collection describing the input
        datasets, runs raster sharpening on each input dataset and creates an output
        feature collection.

        :param metadata: A GeoJSON FeatureCollection describing all input datasets
        :return: A GeoJSON FeatureCollection describing all output datasets
        """
        logger.debug("Sharpening started...")

        results: List[Feature] = []
        for in_feature in metadata.features:
            process_dir = Path("/tmp")
            input_dir = process_dir / "input"
            out_dir = process_dir / "output"
            ensure_data_directories_exist()

            in_feature_name = in_feature["properties"][AOICLIPPED]
            in_feature_path = input_dir / in_feature_name
            logger.debug("Input file: %s", str(in_feature_name))

            out_feature_dir = Path(out_dir / in_feature_name)
            out_feature_dir = out_feature_dir.with_name(
                out_feature_dir.stem + "_sharpened.tif"
            )
            out_feature_dir.parent.mkdir(parents=True, exist_ok=True)
            out_feature_name = str(Path(*out_feature_dir.parts[-2:]))
            logger.debug("Output file: %s", out_feature_name)

            self.sharpen_raster(in_feature_path, out_feature_dir)

            out_feature = Feature(
                geometry=in_feature["geometry"], bbox=in_feature["bbox"]
            )
            out_feature["properties"] = self.get_metadata(in_feature)
            set_capability(out_feature, AOICLIPPED, out_feature_name)
            results.append(out_feature)
            logger.debug("File %s was sharpened.", out_feature_name)

        return FeatureCollection(results)

    @classmethod
    def get_metadata(cls, feature: Feature) -> dict:
        """
        Extracts metadata elements that need to be propagated to the output tif
        """
        prop_dict = feature["properties"]
        meta_dict = {
            k: v
            for k, v in prop_dict.items()
            if not (k.startswith("up42.") or k.startswith("custom."))
        }
        return meta_dict

    @classmethod
    def from_dict(cls, params_dict: Dict):
        """
        Reads the parameters of the processing block from a provided dictionary.

        :param params_dict: The parameters of the sharpening operation
        :return: Instance of RasterSharpener class configured with the given parameters
        """
        strength: str = params_dict.get("strength", "medium") or "medium"
        filter_method: str = params_dict.get("filter_method", "kernel") or "kernel"
        return RasterSharpener(strength=strength, filter_method=filter_method)

    @staticmethod
    def run():
        """
        This method is the main entry point for this processing block.
        """
        # pylint: disable=E1121
        ensure_data_directories_exist()
        params: dict = load_params()
        input_metadata: FeatureCollection = load_metadata()
        rs = RasterSharpener.from_dict(params)

        logger.debug("Using sharpening strenth: %s", rs.strength)
        logger.debug("Using filter method: %s", rs.filter_method)

        result: FeatureCollection = rs.process(input_metadata)
        save_metadata(result)

        logger.debug("Result is %r", result)
        logger.debug("DONE!")
