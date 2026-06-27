from __future__ import annotations

from dataclasses import dataclass
import math

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage

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
    algorithm: ToleranceAlgorithm


class ToleranceMapService:
    def prepare_comparison(
        self,
        left: QImage,
        right: QImage,
        algorithm: ToleranceAlgorithm,
        max_size: tuple[int, int] | None = None,
    ) -> PreparedToleranceComparison:
        if left.format() != QImage.Format.Format_RGB32:
            left = left.convertToFormat(QImage.Format.Format_RGB32)
        if right.format() != QImage.Format.Format_RGB32:
            right = right.convertToFormat(QImage.Format.Format_RGB32)

        target_width = left.width()
        target_height = left.height()
        if max_size is not None:
            max_width, max_height = max_size
            width_ratio = max_width / max(1, left.width())
            height_ratio = max_height / max(1, left.height())
            scale = min(1.0, width_ratio, height_ratio)
            target_width = max(1, int(left.width() * scale))
            target_height = max(1, int(left.height() * scale))
            if target_width != left.width() or target_height != left.height():
                left = left.scaled(
                    target_width,
                    target_height,
                    Qt.AspectRatioMode.IgnoreAspectRatio,
                    Qt.TransformationMode.FastTransformation,
                )
        if right.size() != left.size():
            right = right.scaled(
                target_width,
                target_height,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
        elif right.width() != target_width or right.height() != target_height:
            right = right.scaled(
                target_width,
                target_height,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
        return PreparedToleranceComparison(left=left, right=right, algorithm=algorithm)

    def build_tolerance_map(
        self,
        left: QImage,
        right: QImage,
        tolerance: int,
        algorithm: ToleranceAlgorithm,
        max_size: tuple[int, int] | None = None,
    ) -> QImage:
        prepared = self.prepare_comparison(left, right, algorithm, max_size=max_size)
        result = QImage(prepared.left.size(), QImage.Format.Format_RGB32)
        for y in range(prepared.left.height()):
            for x in range(prepared.left.width()):
                difference = self._difference_at(prepared, x, y)
                if difference == 0:
                    color = QColor(128, 128, 128)
                elif difference > tolerance:
                    color = QColor(255, 0, 0)
                else:
                    color = QColor(0, 0, 255)
                result.setPixelColor(x, y, color)
        return result

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
