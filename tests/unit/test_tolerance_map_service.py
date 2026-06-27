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


def test_tolerance_service_uses_gray_blue_red_difference_bands() -> None:
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

    assert gray_map.pixelColor(0, 0) == QColor(128, 128, 128)
    assert blue_map.pixelColor(0, 0) == QColor(0, 0, 255)
    assert red_map.pixelColor(0, 0) == QColor(255, 0, 0)


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
