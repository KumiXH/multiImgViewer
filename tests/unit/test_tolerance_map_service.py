from PySide6.QtGui import QColor, QImage

from remote_image_compare.domain.models import ToleranceAlgorithm
from remote_image_compare.services.tolerance_map_service import ToleranceMapService


def test_tolerance_algorithm_values_are_stable() -> None:
    assert ToleranceAlgorithm.MAX_CHANNEL.value == "max_channel"
    assert ToleranceAlgorithm.AVERAGE.value == "average"
    assert ToleranceAlgorithm.EUCLIDEAN.value == "euclidean"


def _filled_image(width: int, height: int, color: tuple[int, int, int]) -> QImage:
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(QColor(*color))
    return image


def test_tolerance_service_uses_grayscale_base_with_blue_red_overlays() -> None:
    service = ToleranceMapService()
    left = _filled_image(1, 1, (10, 10, 10))
    equal_right = _filled_image(1, 1, (10, 10, 10))
    close_right = _filled_image(1, 1, (20, 20, 20))

    gray_map = service.build_tolerance_map(
        left,
        equal_right,
        tolerance=15,
        algorithm=ToleranceAlgorithm.MAX_CHANNEL,
    )
    blue_map = service.build_tolerance_map(
        left,
        close_right,
        tolerance=15,
        algorithm=ToleranceAlgorithm.MAX_CHANNEL,
    )
    red_map = service.build_tolerance_map(
        left,
        tolerance=5,
        algorithm=ToleranceAlgorithm.MAX_CHANNEL,
        right=close_right,
    )

    assert gray_map.pixelColor(0, 0) == QColor(10, 10, 10)
    blue = blue_map.pixelColor(0, 0)
    red = red_map.pixelColor(0, 0)
    assert blue.blue() > blue.red()
    assert blue.blue() > blue.green()
    assert blue != QColor(0, 0, 255)
    assert red.red() > red.green()
    assert red.red() > red.blue()
    assert red != QColor(255, 0, 0)


def test_tolerance_service_resizes_images_to_common_size() -> None:
    service = ToleranceMapService()
    left = _filled_image(4, 4, (10, 10, 10))
    right = _filled_image(2, 2, (10, 10, 10))

    tolerance_map = service.build_tolerance_map(
        left,
        right,
        tolerance=0,
        algorithm=ToleranceAlgorithm.AVERAGE,
    )

    assert tolerance_map.size() == left.size()


def test_tolerance_service_samples_rgb_and_difference() -> None:
    service = ToleranceMapService()
    left = _filled_image(2, 2, (10, 20, 30))
    right = _filled_image(2, 2, (13, 22, 31))
    result = service.prepare_comparison(
        left,
        right,
        algorithm=ToleranceAlgorithm.MAX_CHANNEL,
    )

    sample = service.sample_at(result, 0.5, 0.5)

    assert sample.left_rgb == (10, 20, 30)
    assert sample.right_rgb == (13, 22, 31)
    assert sample.difference == 3


def test_tolerance_service_can_bound_comparison_size_for_preview() -> None:
    service = ToleranceMapService()
    left = _filled_image(3840, 2160, (10, 10, 10))
    right = _filled_image(3840, 2160, (20, 20, 20))

    prepared = service.prepare_comparison(
        left,
        right,
        algorithm=ToleranceAlgorithm.MAX_CHANNEL,
        max_size=(960, 540),
    )

    assert prepared.left.width() <= 960
    assert prepared.left.height() <= 540


def test_tolerance_service_can_prepare_roi_region() -> None:
    service = ToleranceMapService()
    left = _filled_image(100, 80, (10, 10, 10))
    right = _filled_image(100, 80, (20, 20, 20))

    prepared = service.prepare_comparison(
        left,
        right,
        algorithm=ToleranceAlgorithm.MAX_CHANNEL,
        roi=(25, 20, 50, 30),
    )

    assert prepared.left.width() == 50
    assert prepared.left.height() == 30
    assert prepared.right.width() == 50
    assert prepared.right.height() == 30


def test_tolerance_service_aligns_roi_for_different_image_sizes() -> None:
    service = ToleranceMapService()
    left = _filled_image(200, 100, (0, 0, 0))
    right = _filled_image(100, 50, (0, 0, 0))

    for x in range(50, 150):
        for y in range(25, 75):
            left.setPixelColor(x, y, QColor(255, 255, 255))
    for x in range(25, 75):
        for y in range(12, 37):
            right.setPixelColor(x, y, QColor(255, 255, 255))

    tolerance_map = service.build_tolerance_map(
        left,
        right,
        tolerance=0,
        algorithm=ToleranceAlgorithm.MAX_CHANNEL,
        roi=(50, 25, 100, 50),
    )

    assert tolerance_map.width() == 100
    assert tolerance_map.height() == 50
    assert tolerance_map.pixelColor(50, 25) == QColor(255, 255, 255)


def test_tolerance_service_uses_larger_image_as_grayscale_base() -> None:
    service = ToleranceMapService()
    left = _filled_image(8, 8, (30, 30, 30))
    right = _filled_image(4, 4, (220, 220, 220))

    tolerance_map = service.build_tolerance_map(
        left,
        right,
        tolerance=255,
        algorithm=ToleranceAlgorithm.MAX_CHANNEL,
    )

    pixel = tolerance_map.pixelColor(0, 0)
    assert pixel.blue() > pixel.red()
    assert pixel.blue() > pixel.green()
    assert pixel.red() < 170


def test_tolerance_service_keeps_overlay_aligned_with_grayscale_base_after_roi_scaling() -> None:
    service = ToleranceMapService()
    left = _filled_image(200, 100, (0, 0, 0))
    right = _filled_image(100, 50, (0, 0, 0))

    for x in range(50, 150):
        for y in range(25, 75):
            left.setPixelColor(x, y, QColor(240, 240, 240))
    for x in range(25, 75):
        for y in range(12, 37):
            right.setPixelColor(x, y, QColor(20, 20, 20))

    tolerance_map = service.build_tolerance_map(
        left,
        right,
        tolerance=0,
        algorithm=ToleranceAlgorithm.MAX_CHANNEL,
        roi=(50, 25, 100, 50),
        max_size=(50, 25),
    )

    center = tolerance_map.pixelColor(tolerance_map.width() // 2, tolerance_map.height() // 2)
    assert center.red() > center.green()
    assert center.red() > center.blue()


def test_tolerance_service_uses_same_alignment_for_base_and_difference_layers() -> None:
    service = ToleranceMapService()
    left = _filled_image(200, 100, (0, 0, 0))
    right = _filled_image(100, 50, (0, 0, 0))

    for x in range(140, 180):
        for y in range(70, 90):
            left.setPixelColor(x, y, QColor(255, 255, 255))
    for x in range(70, 90):
        for y in range(35, 45):
            right.setPixelColor(x, y, QColor(255, 255, 255))

    prepared = service.prepare_comparison(
        left,
        right,
        algorithm=ToleranceAlgorithm.MAX_CHANNEL,
        roi=(100, 50, 100, 50),
        max_size=(50, 25),
    )

    assert prepared.base.pixelColor(30, 15) == QColor(255, 255, 255)
