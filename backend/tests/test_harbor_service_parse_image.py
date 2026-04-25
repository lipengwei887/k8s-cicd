import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.harbor_service import HarborService


def test_parse_image_url_treats_short_prefix_as_project():
    service = HarborService("https://harbor.example.com")

    harbor_host, project, repository = service.parse_image_url(
        "test/backend/vegetable-procurement-backend:20260423"
    )

    assert harbor_host is None
    assert project == "test"
    assert repository == "backend/vegetable-procurement-backend"


def test_parse_image_url_keeps_fqdn_host():
    service = HarborService("https://harbor.example.com")

    harbor_host, project, repository = service.parse_image_url(
        "harbor.tongfuyouxuan.com/test/backend/vegetable-procurement-backend:20260423"
    )

    assert harbor_host == "harbor.tongfuyouxuan.com"
    assert project == "test"
    assert repository == "backend/vegetable-procurement-backend"
