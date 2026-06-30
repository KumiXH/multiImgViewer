from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage

from remote_image_compare.domain.models import ToleranceAlgorithm


@dataclass(frozen=True)
class ToleranceSample:
    left_rgb: tuple[int, int, int]
    right_rgb: tuple[int, int, int]
    difference: int


@dataclass(frozen=True)
class PreparedToleranceComparison:
    left: QImage
    right: QImage
    base: QImage
    algorithm: ToleranceAlgorithm


class ToleranceMapService:
    def prepare_comparison(
        self,
        left: QImage,
        right: QImage,
        algorithm: ToleranceAlgorithm,
        max_size: tuple[int, int] | None = None,
        roi: tuple[int, int, int, int] | None = None,
    ) -> PreparedToleranceComparison:
        left = self._ensure_rgb32(left)
        right = self._ensure_rgb32(right)
        original_left = left
        original_right = right

        comparison_size = (
            max(left.width(), right.width()),
            max(left.height(), right.height()),
        )
        if roi is None:
            roi = (0, 0, comparison_size[0], comparison_size[1])
        else:
            roi = self._clamp_roi(roi, comparison_size)

        target_width = roi[2]
        target_height = roi[3]
        left = self._extract_aligned_region(left, roi, comparison_size)
        right = self._extract_aligned_region(right, roi, comparison_size)
        if max_size is not None:
            max_width, max_height = max_size
            width_ratio = max_width / max(1, target_width)
            height_ratio = max_height / max(1, target_height)
            scale = min(1.0, width_ratio, height_ratio)
            target_width = max(1, int(target_width * scale))
            target_height = max(1, int(target_height * scale))
        if left.width() != target_width or left.height() != target_height:
            left = left.scaled(
                target_width,
                target_height,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
        if right.width() != target_width or right.height() != target_height:
            right = right.scaled(
                target_width,
                target_height,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
        base_source = (
            original_left
            if original_left.width() * original_left.height()
            >= original_right.width() * original_right.height()
            else original_right
        )
        base = self._extract_aligned_region(base_source, roi, comparison_size)
        if base.width() != target_width or base.height() != target_height:
            base = base.scaled(
                target_width,
                target_height,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
        return PreparedToleranceComparison(left=left, right=right, base=base, algorithm=algorithm)

    def build_tolerance_map(
        self,
        left: QImage,
        right: QImage,
        tolerance: int,
        algorithm: ToleranceAlgorithm,
        max_size: tuple[int, int] | None = None,
        roi: tuple[int, int, int, int] | None = None,
    ) -> QImage:
        prepared = self.prepare_comparison(
            left,
            right,
            algorithm,
            max_size=max_size,
            roi=roi,
        )
        left_array = self._image_to_rgb_array(prepared.left)
        right_array = self._image_to_rgb_array(prepared.right)
        differences = self._difference_array(left_array, right_array, prepared.algorithm)

        base_array = self._image_to_rgb_array(prepared.base)
        result = self._build_overlay_array(base_array, differences, tolerance)
        return self._rgb_array_to_image(result)

    def sample_at(
        self,
        prepared: PreparedToleranceComparison,
        normalized_x: float,
        normalized_y: float,
    ) -> ToleranceSample:
        x = min(prepared.left.width() - 1, max(0, int(normalized_x * prepared.left.width())))
        y = min(prepared.left.height() - 1, max(0, int(normalized_y * prepared.left.height())))
        left_color = prepared.left.pixelColor(x, y)
        right_color = prepared.right.pixelColor(x, y)
        return ToleranceSample(
            left_rgb=(left_color.red(), left_color.green(), left_color.blue()),
            right_rgb=(right_color.red(), right_color.green(), right_color.blue()),
            difference=self._difference_at(prepared, x, y),
        )

    def _difference_at(self, prepared: PreparedToleranceComparison, x: int, y: int) -> int:
        left = prepared.left.pixelColor(x, y)
        right = prepared.right.pixelColor(x, y)
        dr = abs(left.red() - right.red())
        dg = abs(left.green() - right.green())
        db = abs(left.blue() - right.blue())
        if prepared.algorithm is ToleranceAlgorithm.MAX_CHANNEL:
            return max(dr, dg, db)
        if prepared.algorithm is ToleranceAlgorithm.AVERAGE:
            return round((dr + dg + db) / 3)
        return round(math.sqrt(dr * dr + dg * dg + db * db))

    def _difference_array(
        self,
        left: np.ndarray,
        right: np.ndarray,
        algorithm: ToleranceAlgorithm,
    ) -> np.ndarray:
        diff = np.abs(left.astype(np.int16) - right.astype(np.int16))
        if algorithm is ToleranceAlgorithm.MAX_CHANNEL:
            return diff.max(axis=2).astype(np.uint8)
        if algorithm is ToleranceAlgorithm.AVERAGE:
            return np.rint(diff.mean(axis=2)).astype(np.uint8)
        squared = np.square(diff, dtype=np.int32).sum(axis=2)
        return np.rint(np.sqrt(squared)).astype(np.uint8)

    def _build_overlay_array(
        self,
        base: np.ndarray,
        differences: np.ndarray,
        tolerance: int,
    ) -> np.ndarray:
        grayscale = np.rint(
            0.299 * base[:, :, 0] + 0.587 * base[:, :, 1] + 0.114 * base[:, :, 2]
        ).astype(np.uint8)
        result = np.repeat(grayscale[:, :, np.newaxis], 3, axis=2)

        blue_mask = (differences > 0) & (differences <= tolerance)
        red_mask = differences > tolerance
        if np.any(blue_mask):
            result[blue_mask] = self._blend_overlay(result[blue_mask], np.array([0, 102, 255]))
        if np.any(red_mask):
            result[red_mask] = self._blend_overlay(result[red_mask], np.array([255, 64, 64]))
        return result

    def _blend_overlay(self, base_pixels: np.ndarray, overlay_rgb: np.ndarray) -> np.ndarray:
        alpha = 0.58
        return np.rint(base_pixels * (1.0 - alpha) + overlay_rgb * alpha).astype(np.uint8)

    def _ensure_rgb32(self, image: QImage) -> QImage:
        if image.format() == QImage.Format.Format_RGB32:
            return image
        return image.convertToFormat(QImage.Format.Format_RGB32)

    def _crop_roi(self, image: QImage, roi: tuple[int, int, int, int]) -> QImage:
        x, y, width, height = roi
        x = max(0, min(image.width() - 1, x))
        y = max(0, min(image.height() - 1, y))
        width = max(1, min(image.width() - x, width))
        height = max(1, min(image.height() - y, height))
        return image.copy(x, y, width, height)

    def _clamp_roi(
        self,
        roi: tuple[int, int, int, int],
        comparison_size: tuple[int, int],
    ) -> tuple[int, int, int, int]:
        x, y, width, height = roi
        max_width, max_height = comparison_size
        x = max(0, min(max_width - 1, x))
        y = max(0, min(max_height - 1, y))
        width = max(1, min(max_width - x, width))
        height = max(1, min(max_height - y, height))
        return (x, y, width, height)

    def _extract_aligned_region(
        self,
        image: QImage,
        roi: tuple[int, int, int, int],
        comparison_size: tuple[int, int],
    ) -> QImage:
        source_roi = self._map_roi_to_image(roi, image, comparison_size)
        region = self._crop_roi(image, source_roi)
        if region.width() == roi[2] and region.height() == roi[3]:
            return region
        return region.scaled(
            roi[2],
            roi[3],
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )

    def _map_roi_to_image(
        self,
        roi: tuple[int, int, int, int],
        image: QImage,
        comparison_size: tuple[int, int],
    ) -> tuple[int, int, int, int]:
        comparison_width = max(1, comparison_size[0])
        comparison_height = max(1, comparison_size[1])
        x, y, width, height = roi
        left = int(x * image.width() / comparison_width)
        top = int(y * image.height() / comparison_height)
        right = math.ceil((x + width) * image.width() / comparison_width)
        bottom = math.ceil((y + height) * image.height() / comparison_height)
        mapped_width = max(1, right - left)
        mapped_height = max(1, bottom - top)
        return (
            max(0, min(image.width() - 1, left)),
            max(0, min(image.height() - 1, top)),
            mapped_width,
            mapped_height,
        )

    def _image_to_rgb_array(self, image: QImage) -> np.ndarray:
        converted = self._ensure_rgb32(image)
        ptr = converted.bits()
        array = np.frombuffer(ptr, dtype=np.uint8)
        array = array.reshape((converted.height(), converted.bytesPerLine() // 4, 4))
        return array[: converted.height(), : converted.width(), :3].copy()

    def _rgb_array_to_image(self, array: np.ndarray) -> QImage:
        height, width, _channels = array.shape
        bgra = np.empty((height, width, 4), dtype=np.uint8)
        bgra[:, :, 0] = array[:, :, 2]
        bgra[:, :, 1] = array[:, :, 1]
        bgra[:, :, 2] = array[:, :, 0]
        bgra[:, :, 3] = 255
        image = QImage(bgra.data, width, height, width * 4, QImage.Format.Format_RGB32)
        return image.copy()
