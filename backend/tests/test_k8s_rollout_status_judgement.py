import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock
from datetime import datetime, timedelta

import pytest

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.k8s_client import K8sService


def _make_deployment_status(
    replicas: int,
    ready_replicas: int = None,
    available_replicas: int = None,
    observed_generation: int = 2,
    conditions=None,
):
    if ready_replicas is None:
        ready_replicas = replicas
    if available_replicas is None:
        available_replicas = ready_replicas
    status = SimpleNamespace(
        updated_replicas=replicas,
        ready_replicas=ready_replicas,
        available_replicas=available_replicas,
        unavailable_replicas=max(replicas - available_replicas, 0),
        observed_generation=observed_generation,
        conditions=conditions or [],
    )
    spec = SimpleNamespace(replicas=replicas)
    return SimpleNamespace(status=status, spec=spec)


def _make_probe(initial_delay: int, period: int, failures: int):
    return SimpleNamespace(
        initial_delay_seconds=initial_delay,
        period_seconds=period,
        failure_threshold=failures,
    )


def _iso(ts: datetime) -> str:
    return ts.isoformat()


@pytest.mark.asyncio
async def test_transient_failed_pod_should_not_fail_rollout(monkeypatch):
    service = K8sService(cluster_id=1, api_server="http://example", token="token")

    statuses = [
        _make_deployment_status(replicas=2),
        _make_deployment_status(replicas=2),
    ]

    class FakeAppsV1:
        def read_namespaced_deployment_status(self, name, namespace):
            return statuses.pop(0)

    fake_client = SimpleNamespace(apps_v1=FakeAppsV1(), core_v1=SimpleNamespace())

    async def fake_get_client():
        return fake_client

    loop_times = [0.0, 3.0, 6.0]

    class FakeLoop:
        def time(self):
            return loop_times.pop(0)

    pod_snapshots = [
        [
            {"name": "pod-a", "status": "CrashLoopBackOff", "ready": False},
            {"name": "pod-b", "status": "Running", "ready": True},
        ],
        [
            {"name": "pod-a", "status": "Running", "ready": True},
            {"name": "pod-b", "status": "Running", "ready": True},
        ],
    ]

    async def fake_get_pods_status(namespace, deployment_name, expected_image=None):
        return pod_snapshots.pop(0)

    async def fake_to_thread(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    async def fake_sleep(_seconds):
        return None

    monkeypatch.setattr(service, "_get_client", fake_get_client)
    monkeypatch.setattr(service, "_get_pods_status", fake_get_pods_status)
    monkeypatch.setattr(service, "_get_failure_reason", AsyncMock(return_value="transient"))
    monkeypatch.setattr(service, "_get_failed_pods_logs", AsyncMock(return_value="logs"))
    monkeypatch.setattr(service, "_get_pods_logs", AsyncMock(return_value="ok logs"))

    from app.core import k8s_client as k8s_client_module

    monkeypatch.setattr(k8s_client_module.asyncio, "to_thread", fake_to_thread)
    monkeypatch.setattr(k8s_client_module.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(k8s_client_module.asyncio, "get_event_loop", lambda: FakeLoop())

    result = await service._wait_for_rolling_update(
        namespace="default",
        deployment_name="demo",
        timeout=60,
        expected_generation=2,
        progress_callback=None,
        new_image="repo/demo:v2",
    )

    assert result["success"] is True


@pytest.mark.asyncio
async def test_transient_progress_deadline_exceeded_should_not_fail_immediately(monkeypatch):
    service = K8sService(cluster_id=1, api_server="http://example", token="token")

    progress_deadline = SimpleNamespace(type="Progressing", reason="ProgressDeadlineExceeded")
    statuses = [
        _make_deployment_status(replicas=1, conditions=[progress_deadline]),
        _make_deployment_status(replicas=1, conditions=[]),
    ]

    class FakeAppsV1:
        def read_namespaced_deployment_status(self, name, namespace):
            return statuses.pop(0)

    fake_client = SimpleNamespace(apps_v1=FakeAppsV1(), core_v1=SimpleNamespace())

    async def fake_get_client():
        return fake_client

    loop_times = [0.0, 3.0, 6.0]

    class FakeLoop:
        def time(self):
            return loop_times.pop(0)

    async def fake_get_pods_status(namespace, deployment_name, expected_image=None):
        return [{"name": "pod-a", "status": "Running", "ready": True}]

    async def fake_to_thread(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    async def fake_sleep(_seconds):
        return None

    monkeypatch.setattr(service, "_get_client", fake_get_client)
    monkeypatch.setattr(service, "_get_pods_status", fake_get_pods_status)
    monkeypatch.setattr(service, "_get_failure_reason", AsyncMock(return_value="transient deadline"))
    monkeypatch.setattr(service, "_get_failed_pods_logs", AsyncMock(return_value="deadline logs"))
    monkeypatch.setattr(service, "_get_pods_logs", AsyncMock(return_value="ok logs"))

    from app.core import k8s_client as k8s_client_module

    monkeypatch.setattr(k8s_client_module.asyncio, "to_thread", fake_to_thread)
    monkeypatch.setattr(k8s_client_module.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(k8s_client_module.asyncio, "get_event_loop", lambda: FakeLoop())

    result = await service._wait_for_rolling_update(
        namespace="default",
        deployment_name="demo",
        timeout=60,
        expected_generation=2,
        progress_callback=None,
        new_image="repo/demo:v2",
    )

    assert result["success"] is True


@pytest.mark.asyncio
async def test_not_ready_should_wait_probe_grace_window(monkeypatch):
    service = K8sService(cluster_id=1, api_server="http://example", token="token")

    statuses = [
        _make_deployment_status(replicas=5, ready_replicas=4, available_replicas=4),
        _make_deployment_status(replicas=5, ready_replicas=4, available_replicas=4),
        _make_deployment_status(replicas=5, ready_replicas=4, available_replicas=4),
        _make_deployment_status(replicas=5, ready_replicas=4, available_replicas=4),
        _make_deployment_status(replicas=5, ready_replicas=4, available_replicas=4),
        _make_deployment_status(replicas=5, ready_replicas=5, available_replicas=5),
    ]

    deployment_with_probes = SimpleNamespace(
        spec=SimpleNamespace(
            template=SimpleNamespace(
                spec=SimpleNamespace(
                    containers=[
                        SimpleNamespace(
                            startup_probe=_make_probe(initial_delay=180, period=10, failures=3),
                            readiness_probe=_make_probe(initial_delay=180, period=10, failures=3),
                        )
                    ]
                )
            )
        )
    )

    class FakeAppsV1:
        def read_namespaced_deployment_status(self, name, namespace):
            return statuses.pop(0)

        def read_namespaced_deployment(self, name, namespace):
            return deployment_with_probes

    fake_client = SimpleNamespace(apps_v1=FakeAppsV1(), core_v1=SimpleNamespace())

    async def fake_get_client():
        return fake_client

    loop_times = [0.0, 31.0, 34.0, 37.0, 220.0, 223.0, 226.0]

    class FakeLoop:
        def time(self):
            return loop_times.pop(0)

    pod_snapshots = [
        [
            {"name": "pod-1", "status": "Running", "ready": True},
            {"name": "pod-2", "status": "Running", "ready": True},
            {"name": "pod-3", "status": "Running", "ready": True},
            {"name": "pod-4", "status": "Running", "ready": True},
            {"name": "pod-5", "status": "Running", "ready": False},
        ],
        [
            {"name": "pod-1", "status": "Running", "ready": True},
            {"name": "pod-2", "status": "Running", "ready": True},
            {"name": "pod-3", "status": "Running", "ready": True},
            {"name": "pod-4", "status": "Running", "ready": True},
            {"name": "pod-5", "status": "Running", "ready": False},
        ],
        [
            {"name": "pod-1", "status": "Running", "ready": True},
            {"name": "pod-2", "status": "Running", "ready": True},
            {"name": "pod-3", "status": "Running", "ready": True},
            {"name": "pod-4", "status": "Running", "ready": True},
            {"name": "pod-5", "status": "Running", "ready": False},
        ],
        [
            {"name": "pod-1", "status": "Running", "ready": True},
            {"name": "pod-2", "status": "Running", "ready": True},
            {"name": "pod-3", "status": "Running", "ready": True},
            {"name": "pod-4", "status": "Running", "ready": True},
            {"name": "pod-5", "status": "Running", "ready": False},
        ],
        [
            {"name": "pod-1", "status": "Running", "ready": True},
            {"name": "pod-2", "status": "Running", "ready": True},
            {"name": "pod-3", "status": "Running", "ready": True},
            {"name": "pod-4", "status": "Running", "ready": True},
            {"name": "pod-5", "status": "Running", "ready": False},
        ],
        [
            {"name": "pod-1", "status": "Running", "ready": True},
            {"name": "pod-2", "status": "Running", "ready": True},
            {"name": "pod-3", "status": "Running", "ready": True},
            {"name": "pod-4", "status": "Running", "ready": True},
            {"name": "pod-5", "status": "Running", "ready": True},
        ],
    ]

    async def fake_get_pods_status(namespace, deployment_name, expected_image=None):
        return pod_snapshots.pop(0)

    async def fake_to_thread(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    async def fake_sleep(_seconds):
        return None

    monkeypatch.setattr(service, "_get_client", fake_get_client)
    monkeypatch.setattr(service, "_get_pods_status", fake_get_pods_status)
    monkeypatch.setattr(service, "_get_failure_reason", AsyncMock(return_value="pods not ready"))
    monkeypatch.setattr(service, "_get_failed_pods_logs", AsyncMock(return_value="logs"))
    monkeypatch.setattr(service, "_get_pods_logs", AsyncMock(return_value="ok logs"))

    from app.core import k8s_client as k8s_client_module

    monkeypatch.setattr(k8s_client_module.asyncio, "to_thread", fake_to_thread)
    monkeypatch.setattr(k8s_client_module.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(k8s_client_module.asyncio, "get_event_loop", lambda: FakeLoop())

    result = await service._wait_for_rolling_update(
        namespace="default",
        deployment_name="demo",
        timeout=600,
        expected_generation=2,
        progress_callback=None,
        new_image="repo/demo:v2",
    )

    assert result["success"] is True


@pytest.mark.asyncio
async def test_new_not_ready_pods_should_not_fail_even_if_elapsed_is_large(monkeypatch):
    service = K8sService(cluster_id=1, api_server="http://example", token="token")

    statuses = [
        _make_deployment_status(replicas=5, ready_replicas=4, available_replicas=4),
        _make_deployment_status(replicas=5, ready_replicas=4, available_replicas=4),
        _make_deployment_status(replicas=5, ready_replicas=4, available_replicas=4),
        _make_deployment_status(replicas=5, ready_replicas=4, available_replicas=4),
        _make_deployment_status(replicas=5, ready_replicas=5, available_replicas=5),
    ]

    deployment_with_probes = SimpleNamespace(
        spec=SimpleNamespace(
            template=SimpleNamespace(
                spec=SimpleNamespace(
                    containers=[
                        SimpleNamespace(
                            startup_probe=_make_probe(initial_delay=180, period=10, failures=3),
                            readiness_probe=_make_probe(initial_delay=180, period=10, failures=3),
                        )
                    ]
                )
            )
        )
    )

    class FakeAppsV1:
        def read_namespaced_deployment_status(self, name, namespace):
            return statuses.pop(0)

        def read_namespaced_deployment(self, name, namespace):
            return deployment_with_probes

    fake_client = SimpleNamespace(apps_v1=FakeAppsV1(), core_v1=SimpleNamespace())

    async def fake_get_client():
        return fake_client

    loop_times = [0.0, 250.0, 253.0, 256.0, 259.0, 262.0]

    class FakeLoop:
        def time(self):
            return loop_times.pop(0)

    now = datetime.utcnow()
    pod_snapshots = [
        [
            {"name": "pod-1", "status": "Running", "ready": True, "age": _iso(now - timedelta(seconds=300))},
            {"name": "pod-2", "status": "Running", "ready": True, "age": _iso(now - timedelta(seconds=300))},
            {"name": "pod-3", "status": "Running", "ready": True, "age": _iso(now - timedelta(seconds=300))},
            {"name": "pod-4", "status": "Running", "ready": True, "age": _iso(now - timedelta(seconds=300))},
            {"name": "pod-5", "status": "Running", "ready": False, "age": _iso(now - timedelta(seconds=20))},
        ],
        [
            {"name": "pod-1", "status": "Running", "ready": True, "age": _iso(now - timedelta(seconds=303))},
            {"name": "pod-2", "status": "Running", "ready": True, "age": _iso(now - timedelta(seconds=303))},
            {"name": "pod-3", "status": "Running", "ready": True, "age": _iso(now - timedelta(seconds=303))},
            {"name": "pod-4", "status": "Running", "ready": True, "age": _iso(now - timedelta(seconds=303))},
            {"name": "pod-5", "status": "Running", "ready": False, "age": _iso(now - timedelta(seconds=23))},
        ],
        [
            {"name": "pod-1", "status": "Running", "ready": True, "age": _iso(now - timedelta(seconds=306))},
            {"name": "pod-2", "status": "Running", "ready": True, "age": _iso(now - timedelta(seconds=306))},
            {"name": "pod-3", "status": "Running", "ready": True, "age": _iso(now - timedelta(seconds=306))},
            {"name": "pod-4", "status": "Running", "ready": True, "age": _iso(now - timedelta(seconds=306))},
            {"name": "pod-5", "status": "Running", "ready": False, "age": _iso(now - timedelta(seconds=26))},
        ],
        [
            {"name": "pod-1", "status": "Running", "ready": True, "age": _iso(now - timedelta(seconds=309))},
            {"name": "pod-2", "status": "Running", "ready": True, "age": _iso(now - timedelta(seconds=309))},
            {"name": "pod-3", "status": "Running", "ready": True, "age": _iso(now - timedelta(seconds=309))},
            {"name": "pod-4", "status": "Running", "ready": True, "age": _iso(now - timedelta(seconds=309))},
            {"name": "pod-5", "status": "Running", "ready": True, "age": _iso(now - timedelta(seconds=29))},
        ],
        [
            {"name": "pod-1", "status": "Running", "ready": True, "age": _iso(now - timedelta(seconds=312))},
            {"name": "pod-2", "status": "Running", "ready": True, "age": _iso(now - timedelta(seconds=312))},
            {"name": "pod-3", "status": "Running", "ready": True, "age": _iso(now - timedelta(seconds=312))},
            {"name": "pod-4", "status": "Running", "ready": True, "age": _iso(now - timedelta(seconds=312))},
            {"name": "pod-5", "status": "Running", "ready": True, "age": _iso(now - timedelta(seconds=32))},
        ],
    ]

    async def fake_get_pods_status(namespace, deployment_name, expected_image=None):
        return pod_snapshots.pop(0)

    async def fake_to_thread(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    async def fake_sleep(_seconds):
        return None

    monkeypatch.setattr(service, "_get_client", fake_get_client)
    monkeypatch.setattr(service, "_get_pods_status", fake_get_pods_status)
    monkeypatch.setattr(service, "_get_failure_reason", AsyncMock(return_value="pods not ready"))
    monkeypatch.setattr(service, "_get_failed_pods_logs", AsyncMock(return_value="logs"))
    monkeypatch.setattr(service, "_get_pods_logs", AsyncMock(return_value="ok logs"))

    from app.core import k8s_client as k8s_client_module

    monkeypatch.setattr(k8s_client_module.asyncio, "to_thread", fake_to_thread)
    monkeypatch.setattr(k8s_client_module.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(k8s_client_module.asyncio, "get_event_loop", lambda: FakeLoop())

    result = await service._wait_for_rolling_update(
        namespace="default",
        deployment_name="demo",
        timeout=600,
        expected_generation=2,
        progress_callback=None,
        new_image="repo/demo:v2",
    )

    assert result["success"] is True


@pytest.mark.asyncio
async def test_failure_reason_should_ignore_old_image_and_old_events(monkeypatch):
    service = K8sService(cluster_id=1, api_server="http://example", token="token")

    pod_old = SimpleNamespace(
        metadata=SimpleNamespace(name="pod-old", deletion_timestamp=None),
        spec=SimpleNamespace(containers=[SimpleNamespace(image="repo/demo:v1")]),
        status=SimpleNamespace(container_statuses=[]),
    )
    pod_new = SimpleNamespace(
        metadata=SimpleNamespace(name="pod-new", deletion_timestamp=None),
        spec=SimpleNamespace(containers=[SimpleNamespace(image="repo/demo:v2")]),
        status=SimpleNamespace(container_statuses=[]),
    )

    deployment = SimpleNamespace(spec=SimpleNamespace(selector=SimpleNamespace(match_labels={"app": "demo"})))
    release_started_at = datetime(2026, 4, 23, 1, 25, 37)

    old_event = SimpleNamespace(
        type="Warning",
        reason="Unhealthy",
        message="old warning",
        last_timestamp=datetime(2026, 4, 23, 1, 5, 1),
        event_time=None,
        first_timestamp=None,
        metadata=SimpleNamespace(creation_timestamp=datetime(2026, 4, 23, 1, 5, 1)),
    )
    new_event = SimpleNamespace(
        type="Warning",
        reason="Unhealthy",
        message="new warning",
        last_timestamp=datetime(2026, 4, 23, 1, 28, 38),
        event_time=None,
        first_timestamp=None,
        metadata=SimpleNamespace(creation_timestamp=datetime(2026, 4, 23, 1, 28, 38)),
    )

    class FakeAppsV1:
        def read_namespaced_deployment(self, name, namespace):
            return deployment

    class FakeCoreV1:
        def list_namespaced_pod(self, namespace, label_selector):
            return SimpleNamespace(items=[pod_old, pod_new])

        def list_namespaced_event(self, namespace, field_selector):
            if field_selector.endswith("pod-old"):
                return SimpleNamespace(items=[old_event])
            return SimpleNamespace(items=[new_event])

    fake_client = SimpleNamespace(apps_v1=FakeAppsV1(), core_v1=FakeCoreV1())

    async def fake_get_client():
        return fake_client

    async def fake_to_thread(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    monkeypatch.setattr(service, "_get_client", fake_get_client)
    from app.core import k8s_client as k8s_client_module
    monkeypatch.setattr(k8s_client_module.asyncio, "to_thread", fake_to_thread)

    reason = await service._get_failure_reason(
        namespace="default",
        deployment_name="demo",
        release_started_at=release_started_at,
        expected_image="repo/demo:v2",
    )

    assert "new warning" in reason
    assert "old warning" not in reason
    assert "pod-old" not in reason
