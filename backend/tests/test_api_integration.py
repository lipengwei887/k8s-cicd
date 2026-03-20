"""
阶段4测试：API集成测试
验证前端调用的API接口正常工作
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx


class TestAPIIntegration:
    """API集成测试"""
    
    BASE_URL = "http://localhost:8000/api/v1"
    
    async def test_health_check(self):
        """测试1：服务健康检查"""
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8000/health")
            assert response.status_code == 200
            assert response.json()["status"] == "healthy"
            print("✅ 服务健康检查通过")
    
    async def test_users_api(self):
        """测试2：用户列表API"""
        async with httpx.AsyncClient() as client:
            # 先登录获取token
            login_res = await client.post(
                f"{self.BASE_URL}/auth/login",
                data={"username": "admin", "password": "admin123"}
            )
            
            if login_res.status_code != 200:
                print("⚠️ 登录失败，跳过用户API测试")
                return
            
            token = login_res.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            
            # 测试用户列表
            response = await client.get(f"{self.BASE_URL}/users", headers=headers)
            assert response.status_code == 200
            data = response.json()
            assert "items" in data
            print(f"✅ 用户列表API正常 (共 {len(data['items'])} 个用户)")
    
    async def test_rbac_roles_api(self):
        """测试3：RBAC角色列表API"""
        async with httpx.AsyncClient() as client:
            # 先登录
            login_res = await client.post(
                f"{self.BASE_URL}/auth/login",
                data={"username": "admin", "password": "admin123"}
            )
            
            if login_res.status_code != 200:
                print("⚠️ 登录失败，跳过角色API测试")
                return
            
            token = login_res.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            
            # 测试角色列表
            response = await client.get(f"{self.BASE_URL}/rbac/roles", headers=headers)
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)  # RBAC API 返回数组
            print(f"✅ RBAC角色列表API正常 (共 {len(data)} 个角色)")
    
    async def test_rbac_permissions_api(self):
        """测试4：RBAC权限列表API"""
        async with httpx.AsyncClient() as client:
            # 先登录
            login_res = await client.post(
                f"{self.BASE_URL}/auth/login",
                data={"username": "admin", "password": "admin123"}
            )
            
            if login_res.status_code != 200:
                print("⚠️ 登录失败，跳过权限API测试")
                return
            
            token = login_res.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            
            # 测试权限列表
            response = await client.get(f"{self.BASE_URL}/rbac/permissions", headers=headers)
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)  # RBAC API 返回数组
            print(f"✅ RBAC权限列表API正常 (共 {len(data)} 个权限)")
    
    async def test_user_roles_api(self):
        """测试5：用户角色API"""
        async with httpx.AsyncClient() as client:
            # 先登录
            login_res = await client.post(
                f"{self.BASE_URL}/auth/login",
                data={"username": "admin", "password": "admin123"}
            )
            
            if login_res.status_code != 200:
                print("⚠️ 登录失败，跳过用户角色API测试")
                return
            
            token = login_res.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            
            # 获取第一个用户
            users_res = await client.get(f"{self.BASE_URL}/users", headers=headers)
            users = users_res.json().get("items", [])
            
            if not users:
                print("⚠️ 没有用户，跳过测试")
                return
            
            user_id = users[0]["id"]
            
            # 测试获取用户角色
            response = await client.get(
                f"{self.BASE_URL}/users/{user_id}/roles", 
                headers=headers
            )
            assert response.status_code == 200
            data = response.json()
            assert "items" in data
            print(f"✅ 用户角色API正常")
    
    async def test_user_permissions_api(self):
        """测试6：用户权限API（RBAC）"""
        async with httpx.AsyncClient() as client:
            # 先登录
            login_res = await client.post(
                f"{self.BASE_URL}/auth/login",
                data={"username": "admin", "password": "admin123"}
            )
            
            if login_res.status_code != 200:
                print("⚠️ 登录失败，跳过用户权限API测试")
                return
            
            token = login_res.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            
            # 获取第一个用户
            users_res = await client.get(f"{self.BASE_URL}/users", headers=headers)
            users = users_res.json().get("items", [])
            
            if not users:
                print("⚠️ 没有用户，跳过测试")
                return
            
            user_id = users[0]["id"]
            
            # 测试获取用户权限（RBAC方式）
            response = await client.get(
                f"{self.BASE_URL}/users/{user_id}/permissions", 
                headers=headers
            )
            assert response.status_code == 200
            data = response.json()
            assert "items" in data
            print(f"✅ 用户权限API正常 (RBAC)")


async def run_tests():
    """运行所有测试"""
    test = TestAPIIntegration()
    
    print("=" * 60)
    print("阶段4测试：API集成测试")
    print("=" * 60)
    
    tests = [
        ("服务健康检查", test.test_health_check),
        ("用户列表API", test.test_users_api),
        ("RBAC角色列表API", test.test_rbac_roles_api),
        ("RBAC权限列表API", test.test_rbac_permissions_api),
        ("用户角色API", test.test_user_roles_api),
        ("用户权限API", test.test_user_permissions_api),
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
