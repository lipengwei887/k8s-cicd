import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.api.v1.clusters import build_service_model


def test_build_service_model_keeps_current_image_for_new_service():
    service = build_service_model(
        namespace_id=66,
        workload_info={
            "name": "vegetable-procurement-backend",
            "display_name": "vegetable-procurement-backend",
            "type": "deployment",
            "deploy_name": "vegetable-procurement-backend",
            "container_name": "vegetable-procurement-backend",
            "harbor_project": "test",
            "harbor_repo": "backend/vegetable-procurement-backend",
            "current_image": "test/backend/vegetable-procurement-backend:20260423",
            "port": 8080,
            "replicas": 1,
            "description": "from k8s",
        },
    )

    assert service.current_image == "test/backend/vegetable-procurement-backend:20260423"
