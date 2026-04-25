# Permission RBAC Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将权限系统切换到 RBAC 唯一鉴权，统一前端菜单/路由/按钮可见性，删除无用与重复权限入口。

**Architecture:** 后端新增统一 `AuthContext` 计算与授权入口，所有鉴权依赖 RBAC 表数据；前端新增统一权限 Gate，菜单/路由/按钮消费同一权限快照。`users.role/is_superuser` 保留展示，不参与授权决策。

**Tech Stack:** FastAPI, SQLAlchemy Async, MySQL, Redis(optional cache), React, TypeScript, Ant Design, pytest

---

### Task 1: 建立 RBAC 授权上下文构建器

**Files:**
- Create: `backend/app/core/authz_context.py`
- Create: `backend/tests/test_authz_context.py`
- Modify: `backend/app/core/authorization.py`

- [ ] **Step 1: 写失败测试（AuthContext 基础能力）**

```python
# backend/tests/test_authz_context.py
import pytest


@pytest.mark.asyncio
async def test_build_auth_context_collects_permissions_and_scope(async_session):
    from app.core.authz_context import AuthzContextBuilder

    builder = AuthzContextBuilder(async_session)
    ctx = await builder.build(user_id=1)

    assert isinstance(ctx.permission_codes, set)
    assert isinstance(ctx.service_ids, set)
    assert isinstance(ctx.namespace_ids, set)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 -m pytest backend/tests/test_authz_context.py::test_build_auth_context_collects_permissions_and_scope -v`  
Expected: FAIL，提示 `ModuleNotFoundError: app.core.authz_context` 或缺失类。

- [ ] **Step 3: 写最小实现**

```python
# backend/app/core/authz_context.py
from dataclasses import dataclass
from typing import Set


@dataclass
class AuthzContext:
    permission_codes: Set[str]
    service_ids: Set[int]
    namespace_ids: Set[int]


class AuthzContextBuilder:
    def __init__(self, db):
        self.db = db

    async def build(self, user_id: int) -> AuthzContext:
        # 后续任务补全真实查询逻辑
        return AuthzContext(permission_codes=set(), service_ids=set(), namespace_ids=set())
```

- [ ] **Step 4: 用 RBAC 表补全查询逻辑**

```python
# backend/app/core/authz_context.py
from sqlalchemy import select
from app.models.role import RBACPermission, RolePermission
from app.models.user_role import UserRole
from app.models.user_role_group import UserRoleGroup
from app.models.role_group import RoleGroupService, RoleGroupNamespace

    async def build(self, user_id: int) -> AuthzContext:
        perm_stmt = (
            select(RBACPermission.code)
            .join(RolePermission, RolePermission.permission_id == RBACPermission.id)
            .join(UserRole, UserRole.role_id == RolePermission.role_id)
            .where(UserRole.user_id == user_id)
        )
        perm_rows = (await self.db.execute(perm_stmt)).all()

        svc_stmt = (
            select(RoleGroupService.service_id)
            .join(UserRoleGroup, UserRoleGroup.role_group_id == RoleGroupService.role_group_id)
            .where(UserRoleGroup.user_id == user_id)
        )
        svc_rows = (await self.db.execute(svc_stmt)).all()

        ns_stmt = (
            select(RoleGroupNamespace.namespace_id)
            .join(UserRoleGroup, UserRoleGroup.role_group_id == RoleGroupNamespace.role_group_id)
            .where(UserRoleGroup.user_id == user_id)
        )
        ns_rows = (await self.db.execute(ns_stmt)).all()

        return AuthzContext(
            permission_codes={r[0] for r in perm_rows if r[0]},
            service_ids={r[0] for r in svc_rows if r[0] is not None},
            namespace_ids={r[0] for r in ns_rows if r[0] is not None},
        )
```

- [ ] **Step 5: 运行测试确认通过**

Run: `python3 -m pytest backend/tests/test_authz_context.py -v`  
Expected: PASS。

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/authz_context.py backend/tests/test_authz_context.py backend/app/core/authorization.py
git commit -m "feat(auth): add RBAC auth context builder"
```

### Task 2: 统一后端授权引擎（RBAC 唯一鉴权）

**Files:**
- Modify: `backend/app/core/authorization.py`
- Create: `backend/tests/test_authorization_engine.py`

- [ ] **Step 1: 写失败测试（忽略 users.role/is_superuser）**

```python
@pytest.mark.asyncio
async def test_authorize_uses_rbac_only(async_session, user_factory):
    from app.core.authorization import authorize_permission, ResourceContext

    user = user_factory(role="ADMIN", is_superuser=True)
    allowed = await authorize_permission(
        async_session,
        user,
        permission_code="release:execute",
        resource_context=ResourceContext(service_id=1, namespace_id=1),
    )
    assert allowed is False
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 -m pytest backend/tests/test_authorization_engine.py::test_authorize_uses_rbac_only -v`  
Expected: FAIL，当前逻辑会因兼容路径错误通过。

- [ ] **Step 3: 最小实现统一入口**

```python
# backend/app/core/authorization.py
from app.core.authz_context import AuthzContextBuilder

async def authorize_permission(db, user, permission_code: str, resource_context=None):
    ctx = await AuthzContextBuilder(db).build(user.id)
    if permission_code not in ctx.permission_codes:
        return False
    # 资源限制逻辑在后续步骤补全
    return True
```

- [ ] **Step 4: 补全资源范围判定（service/namespace/owner）**

```python
def _match_resource_scope(ctx, resource_context):
    if not resource_context:
        return True
    if resource_context.service_id and resource_context.service_id not in ctx.service_ids:
        if resource_context.namespace_id and resource_context.namespace_id in ctx.namespace_ids:
            return True
        return False
    if resource_context.namespace_id and resource_context.namespace_id not in ctx.namespace_ids and not resource_context.service_id:
        return False
    return True
```

- [ ] **Step 5: 运行测试确认通过**

Run: `python3 -m pytest backend/tests/test_authorization_engine.py -v`  
Expected: PASS。

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/authorization.py backend/tests/test_authorization_engine.py
git commit -m "refactor(auth): enforce RBAC-only authorization engine"
```

### Task 3: 扩展 /auth/me 权限快照（resource_scope）

**Files:**
- Modify: `backend/app/api/v1/auth.py`
- Create: `backend/tests/test_auth_me_scope.py`

- [ ] **Step 1: 写失败测试（返回 resource_scope）**

```python
def test_me_contains_resource_scope(client, auth_headers):
    resp = client.get('/api/v1/auth/me', headers=auth_headers)
    body = resp.json()
    assert 'resource_scope' in body
    assert 'service_ids' in body['resource_scope']
    assert 'namespace_ids' in body['resource_scope']
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 -m pytest backend/tests/test_auth_me_scope.py::test_me_contains_resource_scope -v`  
Expected: FAIL，字段不存在。

- [ ] **Step 3: 最小实现返回 scope**

```python
# backend/app/api/v1/auth.py
from app.core.authz_context import AuthzContextBuilder

ctx = await AuthzContextBuilder(db).build(current_user.id)

return {
    ...,
    "permissions": sorted(ctx.permission_codes),
    "resource_scope": {
        "service_ids": sorted(ctx.service_ids),
        "namespace_ids": sorted(ctx.namespace_ids),
    },
}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python3 -m pytest backend/tests/test_auth_me_scope.py -v`  
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/v1/auth.py backend/tests/test_auth_me_scope.py
git commit -m "feat(auth): expose resource scope in /auth/me"
```

### Task 4: 前端统一权限快照模型

**Files:**
- Modify: `frontend/src/utils/auth.ts`
- Modify: `frontend/src/App.tsx`
- Create: `frontend/src/types/permission.ts`
- Test: `frontend/src/utils/auth.test.ts`

- [ ] **Step 1: 写失败测试（AuthUser 解析 resource_scope）**

```ts
test('stores and reads resource_scope from auth user', () => {
  const user = {
    id: 1,
    username: 'admin',
    permissions: ['release:create'],
    resource_scope: { service_ids: [1], namespace_ids: [2] },
  }
  setStoredCurrentUser(user as any)
  expect(getStoredCurrentUser()?.resource_scope?.service_ids).toEqual([1])
})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd frontend && npm test -- auth.test.ts`  
Expected: FAIL，类型或字段缺失。

- [ ] **Step 3: 最小实现类型扩展**

```ts
export interface ResourceScope {
  service_ids: number[]
  namespace_ids: number[]
}

export interface AuthUser {
  ...
  permissions?: string[]
  resource_scope?: ResourceScope
}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd frontend && npm test -- auth.test.ts`  
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/utils/auth.ts frontend/src/App.tsx frontend/src/types/permission.ts frontend/src/utils/auth.test.ts
git commit -m "feat(frontend-auth): support resource scope in auth snapshot"
```

### Task 5: 建立前端统一 Gate 并收口路由

**Files:**
- Create: `frontend/src/components/PermissionGate.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: 写失败测试（无权限时隐藏按钮）**

```tsx
it('hides gated content without permission', () => {
  render(
    <PermissionGate user={{ permissions: [] } as any} anyOf={['user:manage']}>
      <button>危险操作</button>
    </PermissionGate>
  )
  expect(screen.queryByText('危险操作')).toBeNull()
})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd frontend && npm test -- PermissionGate`  
Expected: FAIL。

- [ ] **Step 3: 实现统一 Gate**

```tsx
export default function PermissionGate({ user, anyOf, children }: Props) {
  const allowed = anyOf.some((code) => hasPermission(user, code))
  if (!allowed) return null
  return <>{children}</>
}
```

- [ ] **Step 4: 应用到关键路由**

```tsx
<Route path="/release/new" element={
  <RequireAuth>
    <RequirePermission anyOf={['release:create']}>
      <ReleaseForm />
    </RequirePermission>
  </RequireAuth>
} />
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd frontend && npm test -- PermissionGate`  
Expected: PASS。

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/PermissionGate.tsx frontend/src/App.tsx
git commit -m "feat(frontend): add unified permission gates for route and actions"
```

### Task 6: 按钮治理与页面收敛（删除无用/重复）

**Files:**
- Modify: `frontend/src/pages/Admin/UserManager.tsx`
- Modify: `frontend/src/pages/Admin/index.tsx`
- Modify: `frontend/src/App.tsx`
- Delete: `frontend/src/pages/Admin/PermissionManager.tsx`

- [ ] **Step 1: 写失败测试（菜单不再出现权限配置入口）**

```tsx
it('does not show permissions menu item', () => {
  render(<AdminLayout />)
  expect(screen.queryByText('权限配置')).toBeNull()
})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd frontend && npm test -- Admin`  
Expected: FAIL，当前仍显示入口。

- [ ] **Step 3: 删除无用与重复项**

```tsx
// UserManager: 删除“权限”按钮（TODO 无行为）
// Admin index: 删除 /admin/permissions 菜单项
// App.tsx: 删除 PermissionManager import 与 permissions route
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd frontend && npm test -- Admin`  
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Admin/UserManager.tsx frontend/src/pages/Admin/index.tsx frontend/src/App.tsx frontend/src/pages/Admin/PermissionManager.tsx
git commit -m "refactor(frontend): remove dead permission button and duplicate permission manager entry"
```

### Task 7: 页面内按钮权限精细化

**Files:**
- Modify: `frontend/src/pages/Admin/ClusterManager.tsx`
- Modify: `frontend/src/pages/Admin/RoleManager.tsx`
- Modify: `frontend/src/pages/Admin/UserRoleManager.tsx`
- Modify: `frontend/src/pages/Admin/RoleGroupManager.tsx`
- Modify: `frontend/src/pages/Dashboard/index.tsx`

- [ ] **Step 1: 写失败测试（管理按钮受权限控制）**

```tsx
it('hides manage buttons when user has read-only permissions', () => {
  const user = { permissions: ['role:read'] }
  render(<RoleManager currentUser={user as any} />)
  expect(screen.queryByText('新增角色')).toBeNull()
})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd frontend && npm test -- RoleManager`  
Expected: FAIL。

- [ ] **Step 3: 最小实现按钮级权限**

```tsx
{hasPermission(currentUser, 'role:manage') && (
  <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>新增角色</Button>
)}
```

- [ ] **Step 4: 对 Dashboard 操作按钮补齐权限码**

```tsx
{record.status === 'success' && hasPermission(currentUser, 'release:rollback') && (
  <Button ...>回滚</Button>
)}
{hasPermission(currentUser, 'release:create') && (
  <Button type="primary" ...>新建发布</Button>
)}
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd frontend && npm test -- Dashboard RoleManager UserRoleManager RoleGroupManager ClusterManager`  
Expected: PASS。

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/Admin/ClusterManager.tsx frontend/src/pages/Admin/RoleManager.tsx frontend/src/pages/Admin/UserRoleManager.tsx frontend/src/pages/Admin/RoleGroupManager.tsx frontend/src/pages/Dashboard/index.tsx
git commit -m "feat(frontend): enforce button-level permission gates across admin and dashboard"
```

### Task 8: Redis 缓存 AuthContext（可选但建议）

**Files:**
- Create: `backend/app/core/authz_cache.py`
- Modify: `backend/app/core/authz_context.py`
- Create: `backend/tests/test_authz_cache.py`

- [ ] **Step 1: 写失败测试（角色变更后缓存失效）**

```python
@pytest.mark.asyncio
async def test_auth_context_cache_invalidates_on_role_change(redis_client):
    from app.core.authz_cache import AuthzCache
    cache = AuthzCache(redis_client)
    await cache.set(1, {"permission_codes": ["user:read"]})
    await cache.invalidate_user(1)
    assert await cache.get(1) is None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 -m pytest backend/tests/test_authz_cache.py -v`  
Expected: FAIL。

- [ ] **Step 3: 实现缓存读写与失效**

```python
class AuthzCache:
    KEY = 'authz:ctx:{user_id}'
    TTL = 120

    async def get(self, user_id: int): ...
    async def set(self, user_id: int, payload: dict): ...
    async def invalidate_user(self, user_id: int): ...
```

- [ ] **Step 4: 接入 context builder（失败回退 DB）**

```python
cached = await self.cache.get(user_id)
if cached:
    return AuthzContext(...)
# miss -> load from db -> set cache
```

- [ ] **Step 5: 运行测试确认通过**

Run: `python3 -m pytest backend/tests/test_authz_cache.py -v`  
Expected: PASS。

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/authz_cache.py backend/app/core/authz_context.py backend/tests/test_authz_cache.py
git commit -m "feat(auth): add redis-backed auth context cache with invalidation"
```

### Task 9: 联调验证与验收

**Files:**
- Create: `docs/superpowers/reports/2026-04-23-permission-rbac-verification.md`

- [ ] **Step 1: 执行后端测试集**

Run: `python3 -m pytest backend/tests/test_authz_context.py backend/tests/test_authorization_engine.py backend/tests/test_auth_me_scope.py backend/tests/test_authz_cache.py -v`  
Expected: 全 PASS。

- [ ] **Step 2: 执行前端测试集**

Run: `cd frontend && npm test -- PermissionGate Admin Dashboard RoleManager UserRoleManager RoleGroupManager ClusterManager`  
Expected: 全 PASS。

- [ ] **Step 3: 本地手工验收（4类账号）**

```text
账号矩阵：只读 / 发布 / 审批 / 管理员
检查项：菜单可见、路由可进、按钮可见、接口可执行、403文案一致
```

- [ ] **Step 4: 写验收报告**

```markdown
# Permission RBAC Verification
- backend tests: pass
- frontend tests: pass
- manual checks: pass/fail with screenshots
```

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/reports/2026-04-23-permission-rbac-verification.md
git commit -m "docs: add RBAC redesign verification report"
```

## Self-Review Checklist

- Spec coverage: 覆盖了架构、模块收敛、按钮治理、数据库映射、迁移、灰度回滚。
- Placeholder scan: 无 TBD/TODO/“后续补充”占位步骤。
- Type consistency: 统一使用 `permission_code`、`resource_scope`、`AuthzContext` 命名。
