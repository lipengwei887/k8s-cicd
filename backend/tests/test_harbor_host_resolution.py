import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.api.v1.harbor import resolve_harbor_host_from_images


def test_resolve_harbor_host_from_images_uses_first_valid_registry():
    host = resolve_harbor_host_from_images(
        [
            "test/backend/vegetable-procurement-backend:20260423",
            "harbor.tongfuyouxuan.com/test/backend/fs-cloud-goods-center:latest",
        ]
    )

    assert host == "harbor.tongfuyouxuan.com"


def test_resolve_harbor_host_from_images_returns_none_without_registry_host():
    host = resolve_harbor_host_from_images(
        [
            "test/backend/vegetable-procurement-backend:20260423",
            "backend/vegetable-procurement-backend:20260423",
        ]
    )

    assert host is None
