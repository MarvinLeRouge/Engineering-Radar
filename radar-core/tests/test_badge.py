import pytest
from radar_core.badge import BadgeResponse, badge_color


@pytest.mark.parametrize(
    ("score", "color"),
    [
        (10.0, "brightgreen"),
        (8.0, "brightgreen"),
        (7.9, "green"),
        (6.0, "green"),
        (4.0, "yellow"),
        (2.0, "orange"),
        (1.9, "red"),
        (0.0, "red"),
    ],
)
def test_badge_color_follows_the_score_bands(score, color):
    assert badge_color(score) == color


def test_badge_serializes_to_the_shields_io_endpoint_shape():
    badge = BadgeResponse(label="quality", message="7.4/10", color="green")

    assert badge.model_dump(by_alias=True) == {
        "schemaVersion": 1,
        "label": "quality",
        "message": "7.4/10",
        "color": "green",
    }
