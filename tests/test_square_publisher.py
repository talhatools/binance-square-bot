"""Unit tests for Binance Square OpenAPI publisher logic."""
import pytest
from src.square_publisher import SquarePublisher, SquareAPIError


def test_publisher_dry_run():
    publisher = SquarePublisher(api_key="mock_key", dry_run=True)
    res = publisher.publish_post(
        text="$BTC Test post. Take trade now! 🚀",
        image_paths=[],
    )
    assert res["publishStatus"] == "dry_run"
    assert "id" in res
    assert "shareLink" in res


def test_publisher_image_limit():
    publisher = SquarePublisher(api_key="mock_key", dry_run=True)
    with pytest.raises(ValueError, match="maximum of 4 images"):
        publisher.publish_post(
            text="Too many images",
            image_paths=["1.png", "2.png", "3.png", "4.png", "5.png"],
        )


def test_square_api_error_attributes():
    err = SquareAPIError("220009", "Daily post limit hit")
    assert err.code == "220009"
    assert "220009" in str(err)
