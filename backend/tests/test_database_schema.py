"""
阶段1测试：数据库结构验证
验证RBAC权限系统表结构正确性
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import inspect, text
from app.database import engine, Base


class TestDatabaseSchema:
    """数据库结构测试"""
    
    async def test_rbac_tables_exist(self):
        """测试1：RBAC相关表必须存在"""
        async with engine.connect() as conn:
            result = await conn.execute(text("""
                SELECT TABLE_NAME 
                FROM information_schema.TABLES 
                WHERE TABLE_SCHEMA = DATABASE()
            """))
            tables = [row[0] for row in result.fetchall()]
            
            required_tables = [
                'users', 'roles', 'user_roles', 
                'rbac_permissions', 'role_permissions',
                'role_groups', 'user_role_groups',
                'role_group_services', 'role_group_namespaces',
                'organizations'
            ]
            
            for table in required_tables:
                assert table in tables, f"缺少必要表: {table}"
            
            # 验证旧permissions表已删除
            assert 'permissions' not in tables, "旧permissions表应该已被删除"
    
    async def test_users_table_structure(self):
        """测试2：users表结构正确"""
        async with engine.connect() as conn:
            result = await conn.execute(text("""
                SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_DEFAULT
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'users'
            """))
            columns = {row[0]: row for row in result.fetchall()}
            
            # 必要字段
            required_columns = ['id', 'username', 'password_hash', 'email', 'role', 'status']
            for col in required_columns:
                assert col in columns, f"users表缺少字段: {col}"
            
            # password_hash 应该可为NULL（支持LDAP）
            assert columns['password_hash'][2] == 'YES', "password_hash应该可为NULL"
            
            # username 应该有唯一索引
            result = await conn.execute(text("""
                SELECT INDEX_NAME, COLUMN_NAME, NON_UNIQUE
                FROM information_schema.STATISTICS
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'users' AND COLUMN_NAME = 'username'
            """))
            indexes = result.fetchall()
            unique_indexes = [idx for idx in indexes if idx[2] == 0]
            assert len(unique_indexes) > 0, "username应该有唯一索引"
    
    async def test_roles_table_structure(self):
        """测试3：roles表结构正确"""
        async with engine.connect() as conn:
            result = await conn.execute(text("""
                SELECT COLUMN_NAME, DATA_TYPE
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'roles'
            """))
            columns = {row[0]: row[1] for row in result.fetchall()}
            
            required_columns = ['id', 'name', 'code', 'role_type', 'status']
            for col in required_columns:
                assert col in columns, f"roles表缺少字段: {col}"
            
            # code应该有唯一约束
            result = await conn.execute(text("""
                SELECT CONSTRAINT_NAME
                FROM information_schema.TABLE_CONSTRAINTS
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'roles' AND CONSTRAINT_TYPE = 'UNIQUE'
            """))
            constraints = [row[0] for row in result.fetchall()]
            assert any('code' in c.lower() for c in constraints), "code字段应该有唯一约束"
    
    async def test_user_roles_foreign_keys(self):
        """测试4：user_roles外键关系正确"""
        async with engine.connect() as conn:
            result = await conn.execute(text("""
                SELECT COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
                FROM information_schema.KEY_COLUMN_USAGE
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'user_roles'
                AND REFERENCED_TABLE_NAME IS NOT NULL
            """))
            fks = {row[0]: (row[1], row[2]) for row in result.fetchall()}
            
            assert 'user_id' in fks, "user_roles缺少user_id外键"
            assert fks['user_id'][0] == 'users', "user_id应该外键关联users表"
            
            assert 'role_id' in fks, "user_roles缺少role_id外键"
            assert fks['role_id'][0] == 'roles', "role_id应该外键关联roles表"
    
    async def test_rbac_permissions_structure(self):
        """测试5：rbac_permissions表结构正确"""
        async with engine.connect() as conn:
            result = await conn.execute(text("""
                SELECT COLUMN_NAME, DATA_TYPE
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'rbac_permissions'
            """))
            columns = {row[0]: row[1] for row in result.fetchall()}
            
            required_columns = ['id', 'name', 'code', 'permission_type', 'resource_type', 'action', 'status']
            for col in required_columns:
                assert col in columns, f"rbac_permissions表缺少字段: {col}"
    
    async def test_role_permissions_foreign_keys(self):
        """测试6：role_permissions外键关系正确"""
        async with engine.connect() as conn:
            result = await conn.execute(text("""
                SELECT COLUMN_NAME, REFERENCED_TABLE_NAME
                FROM information_schema.KEY_COLUMN_USAGE
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'role_permissions'
                AND REFERENCED_TABLE_NAME IS NOT NULL
            """))
            fks = {row[0]: row[1] for row in result.fetchall()}
            
            assert fks.get('role_id') == 'roles', "role_id应该外键关联roles表"
            assert fks.get('permission_id') == 'rbac_permissions', "permission_id应该外键关联rbac_permissions表"
    
    async def test_unique_constraints(self):
        """测试7：唯一约束正确"""
        async with engine.connect() as conn:
            # user_roles 联合唯一
            result = await conn.execute(text("""
                SELECT INDEX_NAME, COLUMN_NAME
                FROM information_schema.STATISTICS
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'user_roles' AND NON_UNIQUE = 0
            """))
            unique_indexes = result.fetchall()
            assert len(unique_indexes) > 0, "user_roles应该有联合唯一索引"
            
            # role_permissions 联合唯一
            result = await conn.execute(text("""
                SELECT INDEX_NAME, COLUMN_NAME
                FROM information_schema.STATISTICS
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'role_permissions' AND NON_UNIQUE = 0
            """))
            unique_indexes = result.fetchall()
            assert len(unique_indexes) > 0, "role_permissions应该有联合唯一索引"


# 运行测试的辅助函数
async def run_tests():
    """运行所有测试"""
    test = TestDatabaseSchema()
    
    print("=" * 60)
    print("阶段1测试：数据库结构验证")
    print("=" * 60)
    
    tests = [
        ("RBAC表存在性", test.test_rbac_tables_exist),
        ("users表结构", test.test_users_table_structure),
        ("roles表结构", test.test_roles_table_structure),
        ("user_roles外键", test.test_user_roles_foreign_keys),
        ("rbac_permissions结构", test.test_rbac_permissions_structure),
        ("role_permissions外键", test.test_role_permissions_foreign_keys),
        ("唯一约束", test.test_unique_constraints),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            await test_func()
            print(f"✅ {name}: 通过")
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
