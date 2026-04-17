import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.authorization import ResourceContext, authorize_permission


@pytest.mark.asyncio
async def test_authorize_permission_accepts_global_scope():
    user = SimpleNamespace(id=1, is_superuser=False, org_id=1)

    with patch("app.core.authorization.RBACService") as rbac_service_cls:
        service = rbac_service_cls.return_value
        service.get_user_permissions = AsyncMock(
            return_value=[
                {
                    "permission_code": "role:manage",
                    "scope_type": "all",
                    "resource_type": "role",
                    "action": "*",
                }
            ]
        )

        allowed = await authorize_permission(object(), user, "role:manage")

    assert allowed is True


@pytest.mark.asyncio
async def test_authorize_permission_accepts_self_scope_for_owner():
    user = SimpleNamespace(id=7, is_superuser=False, org_id=1)

    with patch("app.core.authorization.RBACService") as rbac_service_cls:
        service = rbac_service_cls.return_value
        service.get_user_permissions = AsyncMock(
            return_value=[
                {
                    "permission_code": "release:read",
                    "scope_type": "self",
                    "resource_type": "release",
                    "action": "read",
                }
            ]
        )

        allowed = await authorize_permission(
            object(),
            user,
            "release:read",
            ResourceContext(owner_user_id=7, service_id=12),
        )

    assert allowed is True


@pytest.mark.asyncio
async def test_authorize_permission_checks_resource_group_scope():
    user = SimpleNamespace(id=9, is_superuser=False, org_id=1)

    with patch("app.core.authorization.RBACService") as rbac_service_cls:
        service = rbac_service_cls.return_value
        service.get_user_permissions = AsyncMock(
            return_value=[
                {
                    "permission_code": "release:execute",
                    "scope_type": "assigned",
                    "resource_type": "release",
                    "action": "execute",
                }
            ]
        )
        service.check_user_role_group_access = AsyncMock(return_value=True)

        allowed = await authorize_permission(
            object(),
            user,
            "release:execute",
            ResourceContext(service_id=42, namespace_id=8),
        )

    assert allowed is True
    service.check_user_role_group_access.assert_awaited_once_with(
        9,
        service_id=42,
        namespace_id=8,
    )
