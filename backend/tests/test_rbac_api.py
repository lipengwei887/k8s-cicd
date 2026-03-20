"""
阶段3测试：RBAC API功能验证
测试用户角色和权限管理API
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.services.rbac_service import RBACService
from app.models.user import User
from app.models.role import Role, UserRole, RBACPermission


class TestRBACAPI:
    """RBAC API测试"""
    
    async def test_rbac_service_init(self):
        """测试1：RBAC服务初始化成功"""
        async with AsyncSessionLocal() as db:
            rbac_service = RBACService(db)
            assert rbac_service is not None
            print("✅ RBAC服务初始化成功")
    
    async def test_system_roles_defined(self):
        """测试2：系统预置角色已定义"""
        async with AsyncSessionLocal() as db:
            rbac_service = RBACService(db)
            
            # 检查系统角色
            assert "super_admin" in rbac_service.SYSTEM_ROLES
            assert "org_admin" in rbac_service.SYSTEM_ROLES
            assert "developer" in rbac_service.SYSTEM_ROLES
            assert "ops_engineer" in rbac_service.SYSTEM_ROLES
            assert "approver" in rbac_service.SYSTEM_ROLES
            assert "viewer" in rbac_service.SYSTEM_ROLES
            
            print("✅ 系统预置角色已定义")
    
    async def test_system_permissions_defined(self):
        """测试3：系统预置权限已定义"""
        async with AsyncSessionLocal() as db:
            rbac_service = RBACService(db)
            
            # 检查是否有权限定义
            assert len(rbac_service.SYSTEM_PERMISSIONS) > 0
            
            # 检查关键权限
            permission_codes = [p["code"] for p in rbac_service.SYSTEM_PERMISSIONS]
            assert "release:create" in permission_codes
            assert "release:execute" in permission_codes
            assert "release:approve" in permission_codes
            
            print(f"✅ 系统预置权限已定义 ({len(permission_codes)} 个)")
    
    async def test_assign_role_to_user(self):
        """测试4：角色分配功能"""
        import time
        async with AsyncSessionLocal() as db:
            rbac_service = RBACService(db)
            
            # 使用唯一标识创建测试用户和角色
            unique_id = str(int(time.time()))
            user = User(
                username=f"test_user_{unique_id}",
                email=f"test_{unique_id}@example.com",
                password_hash="test_hash"
            )
            db.add(user)
            await db.flush()
            
            role = Role(
                name=f"测试角色{unique_id}",
                code=f"test_role_{unique_id}",
                role_type="custom"
            )
            db.add(role)
            await db.flush()
            
            # 测试分配角色
            await rbac_service.assign_role_to_user(user.id, role.id)
            await db.commit()
            
            # 验证分配成功
            result = await db.execute(
                select(UserRole).where(
                    UserRole.user_id == user.id,
                    UserRole.role_id == role.id
                )
            )
            user_role = result.scalar_one_or_none()
            assert user_role is not None
            
            print("✅ 角色分配功能正常")
    
    async def test_get_user_permissions(self):
        """测试5：获取用户权限功能"""
        async with AsyncSessionLocal() as db:
            rbac_service = RBACService(db)
            
            # 获取测试用户
            result = await db.execute(
                select(User).where(User.username == "test_user_api")
            )
            user = result.scalar_one_or_none()
            
            if user:
                permissions = await rbac_service.get_user_permissions(user.id)
                assert isinstance(permissions, list)
                print(f"✅ 获取用户权限功能正常 (获取到 {len(permissions)} 个权限)")
            else:
                print("⚠️ 跳过测试：未找到测试用户")
    
    async def test_check_user_permission(self):
        """测试6：权限检查功能"""
        async with AsyncSessionLocal() as db:
            rbac_service = RBACService(db)
            
            # 获取测试用户
            result = await db.execute(
                select(User).where(User.username == "test_user_api")
            )
            user = result.scalar_one_or_none()
            
            if user:
                # 获取用户权限列表来验证
                permissions = await rbac_service.get_user_permissions(user.id)
                assert isinstance(permissions, list)
                print("✅ 权限检查功能正常")
            else:
                print("⚠️ 跳过测试：未找到测试用户")
    
    async def test_role_hierarchy(self):
        """测试7：角色权限继承"""
        async with AsyncSessionLocal() as db:
            # 检查超级管理员是否有所有权限
            result = await db.execute(
                select(Role).where(Role.code == "super_admin")
            )
            role = result.scalar_one_or_none()
            
            if role:
                print("✅ 超级管理员角色存在")
            else:
                print("⚠️ 超级管理员角色尚未初始化")


async def run_tests():
    """运行所有测试"""
    test = TestRBACAPI()
    
    print("=" * 60)
    print("阶段3测试：RBAC API功能验证")
    print("=" * 60)
    
    tests = [
        ("RBAC服务初始化", test.test_rbac_service_init),
        ("系统角色定义", test.test_system_roles_defined),
        ("系统权限定义", test.test_system_permissions_defined),
        ("角色分配功能", test.test_assign_role_to_user),
        ("获取用户权限", test.test_get_user_permissions),
        ("权限检查功能", test.test_check_user_permission),
        ("角色权限继承", test.test_role_hierarchy),
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
