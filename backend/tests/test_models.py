"""
阶段2测试：模型层验证
验证RBAC模型导入和关系正确性
"""
import asyncio
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import inspect
from app.database import Base, engine


class TestModels:
    """模型层测试"""
    
    async def test_import_all_models(self):
        """测试1：所有模型可以正常导入"""
        try:
            from app.models import (
                User, Cluster, Namespace, Service, ReleaseRecord, AuditLog,
                Role, RoleGroup, UserRole, RBACPermission, RolePermission,
                Organization, RoleGroupService, RoleGroupNamespace, UserRoleGroup
            )
            print("✅ 所有模型导入成功")
        except ImportError as e:
            raise AssertionError(f"模型导入失败: {e}")
    
    async def test_permission_model_removed(self):
        """测试2：旧Permission模型已移除"""
        try:
            from app.models import Permission
            raise AssertionError("Permission模型应该已被移除")
        except ImportError:
            print("✅ Permission模型已正确移除")
    
    async def test_user_model_relations(self):
        """测试3：User模型关系正确"""
        from app.models import User
        
        # 检查relationships
        rel_names = [rel.key for rel in User.__mapper__.relationships]
        
        # 应该有的关系
        assert 'releases' in rel_names, "User应该有releases关系"
        assert 'user_roles' in rel_names, "User应该有user_roles关系"
        assert 'role_groups' in rel_names, "User应该有role_groups关系"
        assert 'organization' in rel_names, "User应该有organization关系"
        
        # 不应该有的关系
        assert 'permissions' not in rel_names, "User不应该再有permissions关系"
        
        print("✅ User模型关系正确")
    
    async def test_role_model_relations(self):
        """测试4：Role模型关系正确"""
        from app.models import Role
        
        rel_names = [rel.key for rel in Role.__mapper__.relationships]
        
        assert 'permissions' in rel_names, "Role应该有permissions关系"
        assert 'users' in rel_names, "Role应该有users关系"
        
        print("✅ Role模型关系正确")
    
    async def test_user_role_model_relations(self):
        """测试5：UserRole模型关系正确"""
        from app.models import UserRole
        
        rel_names = [rel.key for rel in UserRole.__mapper__.relationships]
        
        assert 'user' in rel_names, "UserRole应该有user关系"
        assert 'role' in rel_names, "UserRole应该有role关系"
        
        print("✅ UserRole模型关系正确")
    
    async def test_rbac_permission_model(self):
        """测试6：RBACPermission模型正确"""
        from app.models import RBACPermission
        
        # 检查字段
        columns = [col.name for col in RBACPermission.__table__.columns]
        required = ['id', 'name', 'code', 'permission_type', 'resource_type', 'action', 'status']
        
        for col in required:
            assert col in columns, f"RBACPermission应该有{col}字段"
        
        # 检查关系
        rel_names = [rel.key for rel in RBACPermission.__mapper__.relationships]
        assert 'roles' in rel_names, "RBACPermission应该有roles关系"
        
        print("✅ RBACPermission模型正确")
    
    async def test_role_group_model(self):
        """测试7：RoleGroup模型正确"""
        from app.models import RoleGroup
        
        rel_names = [rel.key for rel in RoleGroup.__mapper__.relationships]
        
        assert 'services' in rel_names, "RoleGroup应该有services关系"
        assert 'namespaces' in rel_names, "RoleGroup应该有namespaces关系"
        assert 'users' in rel_names, "RoleGroup应该有users关系"
        
        print("✅ RoleGroup模型正确")
    
    async def test_table_names(self):
        """测试8：模型对应的表名正确"""
        from app.models import (
            User, Role, UserRole, RBACPermission, RolePermission,
            RoleGroup, Organization
        )
        
        assert User.__tablename__ == 'users'
        assert Role.__tablename__ == 'roles'
        assert UserRole.__tablename__ == 'user_roles'
        assert RBACPermission.__tablename__ == 'rbac_permissions'
        assert RolePermission.__tablename__ == 'role_permissions'
        assert RoleGroup.__tablename__ == 'role_groups'
        assert Organization.__tablename__ == 'organizations'
        
        print("✅ 模型表名正确")


# 运行测试
async def run_tests():
    """运行所有测试"""
    test = TestModels()
    
    print("=" * 60)
    print("阶段2测试：模型层验证")
    print("=" * 60)
    
    tests = [
        ("模型导入", test.test_import_all_models),
        ("Permission模型移除", test.test_permission_model_removed),
        ("User模型关系", test.test_user_model_relations),
        ("Role模型关系", test.test_role_model_relations),
        ("UserRole模型关系", test.test_user_role_model_relations),
        ("RBACPermission模型", test.test_rbac_permission_model),
        ("RoleGroup模型", test.test_role_group_model),
        ("模型表名", test.test_table_names),
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
