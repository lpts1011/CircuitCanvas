import pytest

from circuitcanvas.ui.routing import (
    is_octilinear,
    normalized_octilinear_polyline,
    octilinear_route,
    project_to_octilinear,
    project_to_polyline,
)


def test_allowed_directions_and_free_point_projection() -> None:
    assert is_octilinear((0.0, 0.0), (20.0, 0.0))
    assert is_octilinear((0.0, 0.0), (0.0, -20.0))
    assert is_octilinear((0.0, 0.0), (20.0, 20.0))
    assert is_octilinear((0.0, 0.0), (-20.0, 20.0))
    assert not is_octilinear((0.0, 0.0), (20.0, 7.0))

    assert project_to_octilinear((0.0, 0.0), (20.0, 7.0)) == (20.0, 0.0)
    assert project_to_octilinear((0.0, 0.0), (8.0, 10.0)) == pytest.approx((9.0, 9.0))
    assert project_to_octilinear((0.0, 0.0), (-8.0, 10.0)) == pytest.approx((-9.0, 9.0))


def test_arbitrary_endpoints_get_only_octilinear_segments() -> None:
    start = (10.0, 10.0)
    end = (90.0, 45.0)
    points = (start, *octilinear_route(start, end), end)

    assert len(points) == 3
    assert all(is_octilinear(left, right) for left, right in zip(points, points[1:], strict=False))


def test_point_is_projected_to_nearest_position_on_polyline() -> None:
    polyline = ((0.0, 0.0), (100.0, 0.0), (100.0, 80.0))

    assert project_to_polyline((42.0, 19.0), polyline) == pytest.approx((42.0, 0.0))
    assert project_to_polyline((117.0, 51.0), polyline) == pytest.approx((100.0, 51.0))


def test_normalization_removes_duplicates_and_repairs_forbidden_angles() -> None:
    points = normalized_octilinear_polyline(((0.0, 0.0), (0.0, 0.0), (70.0, 25.0), (120.0, 60.0)))

    assert points[0] == (0.0, 0.0)
    assert points[-1] == (120.0, 60.0)
    assert len(points) == len(set(points))
    assert all(is_octilinear(left, right) for left, right in zip(points, points[1:], strict=False))
