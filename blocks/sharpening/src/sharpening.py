from typing import List, Dict, Union
from pathlib import Path
from geojson import FeatureCollection, Feature

import numpy as np
import rasterio as rio
from skimage.filters import unsharp_mask

from helpers import (
    AOICLIPPED,
    set_capability,
    get_logger,
    save_metadata,
    load_params,
    load_metadata,
    ensure_data_directories_exist,
    WindowsUtil,
)

logger = get_logger(__name__)


class RasterSharpener:
    def __init__(self, strength: str = "medium"):
        """
        This class implements a high-pass image filtering method to sharpen a raster.

        :strength: Strength of the sharpening operation, one of "medium" (default),
            "light", "strong".
        """
        self.strength = strength

    @staticmethod
    def sharpen_array(in_array: np.ndarray, strength: str = "medium") -> np.ndarray:
        """
        Runs the sharpening operation on the input array, returns a sharpened output
        array.

        In the 'unsharpen' algorithm, the sharp details are identified as the
        difference between the original image and its blurred version. These details
        are then scaled, and added back to the original image.

        :strength: Strength of the sharpening operation, one of "medium" (default),
            "light", "strong".
        :return: Sharpened output 3d-array
        """
        if strength == "light":
            radius, amount = 1, 1
        elif strength == "medium":
            radius, amount = 2, 2
        elif strength == "strong":
            radius, amount = 3, 3

        sharpened = unsharp_mask(
            in_array.transpose((1, 2, 0)),
            radius=radius,  # size of the gaussian blur and sharpen kernel
            amount=amount,  # strength of the sharpening
            preserve_range=True,
            multichannel=True,
        )
        sharpened = sharpened.transpose((2, 0, 1))

        # Resolve potential array overflow by clipping to min/max values of the input
        # datatype.
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

                # Windowed read and write, buffered window by 4 pixels to enable correct 5x5 kernel operation.
                windows_util = WindowsUtil(src)

                for window, window_buffered in windows_util.windows_buffered(buffer=4):

                    img_array = np.stack(
                        list(src.read(range(1, band_count + 1), window=window_buffered))
                    )

                    sharpened = self.sharpen_array(img_array, strength=self.strength)

                    # Crop result to original window
                    sharpened = windows_util.crop_array_to_window(
                        sharpened, window, window_buffered
                    )

                    for i in range(band_count):
                        dst.write(sharpened[i, ...], i + 1, window=window)

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
        return RasterSharpener(strength=strength)

    @staticmethod
    def run():
        """
        This method is the main entry point for this processing block.
        """
        ensure_data_directories_exist()
        params: dict = load_params()
        input_metadata: FeatureCollection = load_metadata()
        rs = RasterSharpener.from_dict(params)

        logger.debug("Using sharpening strength: %s", rs.strength)

        result: FeatureCollection = rs.process(input_metadata)
        save_metadata(result)

        logger.debug("Result is %r", result)
        logger.debug("DONE!")
