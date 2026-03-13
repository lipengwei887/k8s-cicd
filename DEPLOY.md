# K8s 发版平台部署指南

## 1. 项目结构

```
k8sfabu/
├── backend/              # 后端服务 (FastAPI)
│   ├── app/              # 应用代码
│   ├── venv/             # Python 虚拟环境
│   ├── requirements.txt  # Python 依赖
│   └── .env              # 后端环境变量
├── frontend/             # 前端服务 (React + Vite)
│   ├── src/              # 前端源码
│   ├── dist/             # 构建输出
│   └── package.json      # Node 依赖
├── init.sql              # 数据库初始化脚本
└── start.sh              # 启动脚本
```

## 2. 配置文件位置

### 2.1 后端配置

**环境变量文件**: `/backend/.env`

```bash
# 数据库配置
DATABASE_URL=mysql+aiomysql://user:password@localhost:3306/k8s_release

# JWT 密钥
SECRET_KEY=your-secret-key-here

# Harbor 配置（可选，支持从 K8s Secret 自动获取）
HARBOR_URL=https://harbor.example.com
HARBOR_USERNAME=admin
HARBOR_PASSWORD=password
```

**依赖文件**: `/backend/requirements.txt`

### 2.2 前端配置

**API 配置**: `/frontend/src/api/index.ts`
- 默认使用相对路径 `/api/v1` 访问后端
- 生产环境通过 Nginx 反向代理到后端

**构建配置**: `/frontend/vite.config.ts`
- 开发服务器代理配置
- 生产构建输出到 `dist/` 目录

### 2.3 Nginx 配置

**配置文件**: `/frontend/nginx.conf`

```nginx
server {
    listen 80;
    server_name localhost;
    
    # 前端静态文件
    location / {
        root /usr/share/nginx/html;
        index index.html;
        try_files $uri $uri/ /index.html;
    }
    
    # 后端 API 代理
    location /api/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 3. 部署步骤

### 3.1 数据库初始化

```bash
# 1. 创建数据库
mysql -u root -p -e "CREATE DATABASE k8s_release DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# 2. 执行初始化脚本
mysql -u root -p k8s_release < init.sql
```

### 3.2 后端部署

```bash
cd backend

# 1. 创建虚拟环境
python3 -m venv venv

# 2. 激活虚拟环境
source venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
vim .env

# 5. 启动服务
./start.sh backend
# 或使用: venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 3.3 前端部署

```bash
cd frontend

# 1. 安装依赖
npm install

# 2. 构建生产版本
npm run build

# 3. 使用 Nginx 部署
# 将 dist/ 目录复制到 Nginx 根目录
cp -r dist/* /usr/share/nginx/html/
```

### 3.4 Docker 部署（推荐）

```bash
# 使用 docker-compose
docker-compose up -d
```

## 4. 生产环境注意事项

### 4.1 安全配置

1. **修改默认密码**: 登录后修改 admin 用户密码
2. **JWT 密钥**: 生产环境必须修改 `SECRET_KEY`
3. **数据库密码**: 使用强密码
4. **HTTPS**: 配置 SSL 证书

### 4.2 K8s 集群配置

1. **kubeconfig**: 在"集群管理"页面上传 kubeconfig
2. **权限**: 确保 kubeconfig 有权限操作 Deployment
3. **Harbor**: 配置镜像仓库访问权限

### 4.3 监控与日志

1. **日志文件**: 
   - 后端: `backend/backend.log`
   - 前端: `frontend/frontend.log`
2. **系统监控**: 建议配置 Prometheus + Grafana

## 5. 常用命令

```bash
# 启动服务
./start.sh all        # 启动前后端
./start.sh backend    # 只启动后端
./start.sh frontend   # 只启动前端

# 查看状态
./start.sh status

# 查看日志
./start.sh logs backend
./start.sh logs frontend

# 停止服务
./start.sh stop
```

## 6. 默认账号

- **用户名**: admin
- **密码**: admin123

## 7. 问题排查

### 7.1 后端启动失败

1. 检查数据库连接
2. 检查端口 8000 是否被占用
3. 查看日志: `tail -f backend/backend.log`

### 7.2 前端构建失败

1. 检查 Node 版本 (建议 16+)
2. 删除 node_modules 重新安装
3. 检查 TypeScript 错误

### 7.3 发布失败 (403 Forbidden)

1. 检查 kubeconfig 权限
2. 确认 ServiceAccount 有更新 Deployment 权限
3. 检查证书是否过期
