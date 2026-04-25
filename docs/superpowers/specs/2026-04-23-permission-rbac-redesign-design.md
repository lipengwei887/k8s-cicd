# 权限系统重设计方案（RBAC 唯一鉴权）

日期：2026-04-23  
范围：`frontend + backend + mysql + redis(localhost)`  
状态：设计已确认，待实施计划

## 1. 目标与边界

### 1.1 目标
- 统一权限口径：后端只以 RBAC 表为鉴权事实来源。
- 前后端一致：菜单可见、路由可进、按钮可点、接口可执行保持一致。
- 全面精简：删除无用按钮，收敛重复权限模块入口。

### 1.2 明确边界
- 本文只做设计与规划，不做代码改动。
- 兼容策略已确认：`users.role`、`users.is_superuser` 保留字段，仅用于展示或历史兼容，不参与授权判定。

## 2. 当前模型与问题

### 2.1 当前可用 RBAC 数据模型（MySQL）
- `roles`
- `rbac_permissions`
- `role_permissions`
- `user_roles`
- `role_groups`
- `user_role_groups`
- `role_group_services`
- `role_group_namespaces`
- 兼容字段：`users.role`、`users.is_superuser`

### 2.2 现存问题
- 鉴权来源混合（RBAC 与旧字段逻辑并存风险）。
- 前端菜单层已有权限判断，但页面内按钮权限粒度不一致。
- 存在无行为按钮与重复入口，造成使用噪音与维护成本。

## 3. 方案对比与选型

### 3.1 方案 A（推荐）：领域化 RBAC 重构
- 统一授权引擎与单一决策入口。
- 前端统一权限门控组件，覆盖菜单/路由/按钮三层。
- 渐进迁移，风险可控。

### 3.2 方案 B：轻量补丁式
- 局部修补，改动小。
- 但长期会继续累积分叉逻辑。

### 3.3 方案 C：外部策略引擎化
- 可扩展性强。
- 当前项目投入产出比偏低。

结论：采用方案 A，按阶段推进，并保留灰度与回滚开关。

## 4. 目标架构设计

### 4.1 后端统一鉴权架构
- `AuthContext Builder`：聚合用户有效权限与资源范围。
- `Authorization Engine`：统一判定 `allow(user, permission_code, resource_context)`。
- `Policy Surface`：API 仅调用统一入口，不允许分散实现。

判定顺序：
1. 能力判定：用户是否拥有 `permission_code`。
2. 资源判定：服务/命名空间是否在角色组授权范围。
3. 业务补充：owner 规则（如发布单操作者）等场景约束。

### 4.2 前端统一门控架构
- `MenuGate`：菜单可见性。
- `RouteGuard`：路由访问控制。
- `ActionGate`：按钮与关键操作控制。

三层都消费同一权限快照来源，避免“看得到但点不了”。

## 5. 模块拆分与收敛

### 5.1 模块拆分
- `Auth Context 模块`：输出权限码集合与资源范围。
- `Authorization Engine 模块`：统一鉴权决策。
- `Permission Snapshot API`：返回 `permissions + resource_scope`。
- `Frontend Permission Gate`：统一 UI 侧权限判断。

### 5.2 页面与入口收敛策略
- 保留：`ClusterManager`、`UserManager`、`RoleManager`、`UserRoleManager`、`RoleGroupManager`。
- 收敛建议：下线 `PermissionManager`（与 `UserRoleManager` 功能重复），删除其菜单与路由入口。
- 删除无行为按钮：如 `UserManager` 中仅 TODO 的“权限”按钮。

## 6. 按钮治理规则（全站标准）

- `Delete`：无行为、废弃逻辑、重复入口按钮。
- `Merge`：重复功能入口合并到唯一主入口。
- `Hide`：无权限用户不展示按钮。
- `Disable`：仅在需要解释“暂不可用”时使用，并提供原因。
- `Keep`：保留高价值、权限明确、流程闭环的按钮。

## 7. 数据库映射规则

### 7.1 鉴权事实来源
- 能力：`roles -> role_permissions -> rbac_permissions(code)`
- 资源：`user_role_groups -> role_group_services/role_group_namespaces`
- 时效：`user_roles.valid_from/valid_until`

### 7.2 兼容字段策略
- `users.role`、`users.is_superuser` 不参与权限计算。
- 仅用于展示、历史数据兼容或迁移过渡审计。

## 8. 迁移计划（Phase 0~3）

### Phase 0：基线盘点
- 输出权限码字典。
- 输出按钮-权限矩阵。
- 输出 API-权限矩阵。

### Phase 1：后端鉴权收口
- 所有 API 统一走授权引擎。
- 统一拒绝原因模型（deny reason）。

### Phase 2：前端三层一致化
- 菜单/路由/按钮全部接入统一 Gate。
- 删除无用按钮与重复入口。

### Phase 3：旧字段退役
- 从鉴权路径完全移除 `users.role/is_superuser`。
- 保留字段，待后续单独治理决策。

## 9. 灰度与回滚

建议开关：
- `AUTHZ_ENGINE_V2`
- `FRONTEND_PERMISSION_GATES_V2`

策略：每个 Phase 都可独立回滚，不跨阶段绑定。

## 10. Redis 与 MySQL 角色定位

- MySQL：权限事实来源（source of truth）。
- Redis：可选 `AuthContext` 短 TTL 缓存（建议 60~120s）。
- 缓存失效触发：
  - 用户角色变更
  - 角色权限变更
  - 角色组服务/命名空间变更

## 11. 交付物清单

1. 权限域模型说明（架构与决策顺序）
2. 按钮-权限矩阵（页面级到按钮级）
3. API-权限矩阵（接口到权限码）
4. 页面收敛清单（下线/合并项）
5. 迁移执行 Runbook（Phase 0~3）
6. 本地联调验证清单（多角色全链路）

## 12. 验收标准

- 前端可见性与后端可执行性一致。
- 无无用按钮、无重复权限入口、无死链路由。
- 同账号同场景下鉴权结果唯一且可解释。
- 角色/权限变更后在预期时延内生效。

## 13. 风险与缓解

- 风险：历史逻辑隐式依赖 `users.role/is_superuser`。
  - 缓解：Phase 1 增加审计日志，灰度观察后再切换。
- 风险：前端页面按钮权限散落导致漏改。
  - 缓解：先产出按钮矩阵，再按矩阵逐页迁移。
- 风险：重复模块下线影响使用习惯。
  - 缓解：先并行提示，再删除入口。

---

本设计已完成用户确认：
1) 目标架构确认  
2) 模块拆分与按钮治理确认  
3) DB 映射与迁移计划确认  
4) 最终交付清单确认
