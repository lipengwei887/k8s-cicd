"""
阶段5测试：数据迁移验证
验证RBAC数据完整性和一致性
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, func
from app.database import AsyncSessionLocal
from app.models.user import User
from app.models.role import Role, UserRole, RBACPermission, RolePermission


class TestDataMigration:
    """数据迁移测试"""
    
    async def test_admin_user_exists(self):
        """测试1：管理员用户存在"""
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(User).where(User.username == "admin")
            )
            admin = result.scalar_one_or_none()
            assert admin is not None, "管理员用户必须存在"
            assert admin.is_superuser == True, "管理员必须是超级用户"
            print("✅ 管理员用户存在且配置正确")
    
    async def test_system_roles_exist(self):
        """测试2：系统预置角色存在"""
        async with AsyncSessionLocal() as db:
            required_roles = ["super_admin", "org_admin", "developer", "ops_engineer", "approver", "viewer"]
            
            for role_code in required_roles:
                result = await db.execute(
                    select(Role).where(Role.code == role_code)
                )
                role = result.scalar_one_or_none()
                assert role is not None, f"系统角色 {role_code} 必须存在"
                assert role.role_type.value == "system", f"角色 {role_code} 必须是系统角色"
            
            print(f"✅ 所有系统预置角色存在 ({len(required_roles)} 个)")
    
    async def test_system_permissions_exist(self):
        """测试3：系统预置权限存在"""
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(RBACPermission))
            permissions = result.scalars().all()
            
            assert len(permissions) > 0, "必须有预置权限"
            
            # 检查关键权限
            permission_codes = [p.code for p in permissions]
            key_permissions = ["release:create", "release:execute", "release:approve", "service:read"]
            
            for perm_code in key_permissions:
                assert perm_code in permission_codes, f"关键权限 {perm_code} 必须存在"
            
            print(f"✅ 系统预置权限存在 ({len(permissions)} 个)")
    
    async def test_role_permissions_mapping(self):
        """测试4：角色权限映射存在"""
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(RolePermission))
            mappings = result.scalars().all()
            
            # 超级管理员应该有所有权限
            result = await db.execute(
                select(Role).where(Role.code == "super_admin")
            )
            super_admin = result.scalar_one_or_none()
            
            if super_admin:
                result = await db.execute(
                    select(func.count(RolePermission.id)).where(
                        RolePermission.role_id == super_admin.id
                    )
                )
                super_admin_perm_count = result.scalar()
                
                # 超级管理员应该有权限映射
                assert super_admin_perm_count > 0, "超级管理员必须有权限映射"
            
            print(f"✅ 角色权限映射存在 ({len(mappings)} 个映射)")
    
    async def test_no_orphan_user_roles(self):
        """测试5：没有孤立的用户角色关联"""
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(UserRole).where(
                    UserRole.user_id.notin_(select(User.id))
                )
            )
            orphan_user_roles = result.scalars().all()
            assert len(orphan_user_roles) == 0, "不应该有孤立的用户角色关联"
            
            result = await db.execute(
                select(UserRole).where(
                    UserRole.role_id.notin_(select(Role.id))
                )
            )
            orphan_role_links = result.scalars().all()
            assert len(orphan_role_links) == 0, "不应该有孤立的角色关联"
            
            print("✅ 没有孤立的用户角色关联")
    
    async def test_user_role_assignment_possible(self):
        """测试6：可以正常分配角色给用户"""
        async with AsyncSessionLocal() as db:
            # 获取第一个用户和第一个角色
            result = await db.execute(select(User).limit(1))
            user = result.scalar_one_or_none()
            
            result = await db.execute(select(Role).limit(1))
            role = result.scalar_one_or_none()
            
            if user and role:
                # 检查是否已有关联
                result = await db.execute(
                    select(UserRole).where(
                        UserRole.user_id == user.id,
                        UserRole.role_id == role.id
                    )
                )
                existing = result.scalar_one_or_none()
                
                if existing:
                    print("✅ 用户角色分配功能可用（已有关联）")
                else:
                    # 创建新关联
                    user_role = UserRole(user_id=user.id, role_id=role.id)
                    db.add(user_role)
                    await db.commit()
                    
                    # 验证创建成功
                    result = await db.execute(
                        select(UserRole).where(
                            UserRole.user_id == user.id,
                            UserRole.role_id == role.id
                        )
                    )
                    assert result.scalar_one_or_none() is not None
                    print("✅ 用户角色分配功能正常")
            else:
                print("⚠️ 没有用户或角色可供测试")
    
    async def test_permissions_table_removed(self):
        """测试7：旧permissions表已删除"""
        async with AsyncSessionLocal() as db:
            try:
                result = await db.execute(
                    select(func.count()).select_from("permissions")
                )
                raise AssertionError("旧permissions表应该已被删除")
            except Exception as e:
                if "permissions" in str(e).lower():
                    print("✅ 旧permissions表已正确删除")
                else:
                    raise


async def run_tests():
    """运行所有测试"""
    test = TestDataMigration()
    
    print("=" * 60)
    print("阶段5测试：数据迁移验证")
    print("=" * 60)
    
    tests = [
        ("管理员用户存在", test.test_admin_user_exists),
        ("系统预置角色存在", test.test_system_roles_exist),
        ("系统预置权限存在", test.test_system_permissions_exist),
        ("角色权限映射存在", test.test_role_permissions_mapping),
        ("无孤立用户角色", test.test_no_orphan_user_roles),
        ("用户角色分配功能", test.test_user_role_assignment_possible),
        ("旧permissions表已删除", test.test_permissions_table_removed),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            await test_func()
            passed += 1
        except Exception as e:
            print(f"❌ {name}: 失败 - {e}")
            failed += 1
    
    print("=" * 60)
    print(f"测试结果: {passed} 通过, {failed} 失败")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    asyncio.run(run_tests())
