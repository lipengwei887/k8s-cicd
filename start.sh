#!/bin/bash

# K8s 发版平台启动脚本
# 用法: ./start.sh [all|backend|frontend|stop|status|logs]

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 项目目录
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"

# 日志文件
BACKEND_LOG="$PROJECT_DIR/logs/backend.log"
FRONTEND_LOG="$PROJECT_DIR/logs/frontend.log"

# 创建日志目录
mkdir -p "$PROJECT_DIR/logs"

# 检查虚拟环境是否存在
check_venv() {
    if [ ! -d "$BACKEND_DIR/venv" ]; then
        echo -e "${RED}错误: 后端虚拟环境不存在${NC}"
        echo "请先创建虚拟环境并安装依赖:"
        echo "  cd backend && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
        exit 1
    fi
}

# 启动 MySQL 和 Redis
start_infra() {
    echo -e "${YELLOW}启动 MySQL 和 Redis...${NC}"
    cd "$PROJECT_DIR"
    docker-compose up -d mysql redis
    
    # 等待数据库就绪
    echo -e "${YELLOW}等待数据库就绪...${NC}"
    sleep 5
    
    # 检查 MySQL 是否就绪
    until docker-compose exec -T mysql mysql -uroot -prootpass -e "SELECT 1" >/dev/null 2>&1; do
        echo -e "${YELLOW}等待 MySQL 就绪...${NC}"
        sleep 2
    done
    
    echo -e "${GREEN}MySQL 和 Redis 已启动${NC}"
}

# 停止 MySQL 和 Redis
stop_infra() {
    echo -e "${YELLOW}停止 MySQL 和 Redis...${NC}"
    cd "$PROJECT_DIR"
    docker-compose stop mysql redis
    echo -e "${GREEN}MySQL 和 Redis 已停止${NC}"
}

# 启动后端
start_backend() {
    check_venv
    
    # 检查是否已在运行
    if pgrep -f "uvicorn app.main:app" > /dev/null; then
        echo -e "${YELLOW}后端服务已在运行${NC}"
        return
    fi
    
    echo -e "${YELLOW}启动后端服务...${NC}"
    cd "$BACKEND_DIR"
    
    # 使用 nohup 启动后端，输出到日志文件
    nohup venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4 > "$BACKEND_LOG" 2>&1 &
    
    # 等待后端启动
    sleep 3
    
    # 检查是否启动成功
    if curl -s http://localhost:8000/api/v1/clusters >/dev/null 2>&1; then
        echo -e "${GREEN}后端服务已启动: http://localhost:8000${NC}"
    else
        echo -e "${RED}后端服务启动失败，请检查日志: $BACKEND_LOG${NC}"
        exit 1
    fi
}

# 停止后端
stop_backend() {
    echo -e "${YELLOW}停止后端服务...${NC}"
    pkill -f "uvicorn app.main:app" 2>/dev/null || true
    echo -e "${GREEN}后端服务已停止${NC}"
}

# 启动前端
start_frontend() {
    # 检查是否已在运行
    if docker-compose ps | grep -q "k8s-platform-frontend.*Up"; then
        echo -e "${YELLOW}前端服务已在运行${NC}"
        return
    fi
    
    echo -e "${YELLOW}启动前端服务...${NC}"
    cd "$PROJECT_DIR"
    docker-compose up -d frontend
    
    # 等待前端启动
    sleep 3
    
    # 检查是否启动成功
    if curl -s http://localhost:3000 >/dev/null 2>&1; then
        echo -e "${GREEN}前端服务已启动: http://localhost:3000${NC}"
    else
        echo -e "${RED}前端服务启动失败${NC}"
        exit 1
    fi
}

# 停止前端
stop_frontend() {
    echo -e "${YELLOW}停止前端服务...${NC}"
    cd "$PROJECT_DIR"
    docker-compose stop frontend 2>/dev/null || true
    echo -e "${GREEN}前端服务已停止${NC}"
}

# 启动全部服务
start_all() {
    start_infra
    start_backend
    start_frontend
    
    echo ""
    echo -e "${GREEN}================================${NC}"
    echo -e "${GREEN}所有服务已启动${NC}"
    echo -e "${GREEN}================================${NC}"
    echo -e "前端: http://localhost:3000"
    echo -e "后端: http://localhost:8000"
    echo -e "默认账号: admin / admin123"
    echo ""
    echo "查看日志:"
    echo "  后端: tail -f logs/backend.log"
    echo "  前端: docker-compose logs -f frontend"
}

# 停止全部服务
stop_all() {
    stop_frontend
    stop_backend
    stop_infra
    
    echo ""
    echo -e "${GREEN}所有服务已停止${NC}"
}

# 查看状态
status() {
    echo -e "${YELLOW}服务状态:${NC}"
    echo ""
    
    # MySQL 和 Redis
    echo -e "${YELLOW}基础设施 (Docker):${NC}"
    cd "$PROJECT_DIR"
    docker-compose ps mysql redis 2>/dev/null || echo "  未运行"
    
    echo ""
    
    # 后端
    echo -e "${YELLOW}后端服务:${NC}"
    if pgrep -f "uvicorn app.main:app" > /dev/null; then
        echo -e "  ${GREEN}运行中${NC} - http://localhost:8000"
        echo "  日志: $BACKEND_LOG"
    else
        echo -e "  ${RED}未运行${NC}"
    fi
    
    echo ""
    
    # 前端
    echo -e "${YELLOW}前端服务 (Docker):${NC}"
    if docker-compose ps | grep -q "k8s-platform-frontend.*Up"; then
        echo -e "  ${GREEN}运行中${NC} - http://localhost:3000"
    else
        echo -e "  ${RED}未运行${NC}"
    fi
}

# 查看日志
logs() {
    case "$1" in
        backend)
            echo -e "${YELLOW}后端日志 (按 Ctrl+C 退出):${NC}"
            tail -f "$BACKEND_LOG"
            ;;
        frontend)
            echo -e "${YELLOW}前端日志 (按 Ctrl+C 退出):${NC}"
            cd "$PROJECT_DIR"
            docker-compose logs -f frontend
            ;;
        mysql)
            echo -e "${YELLOW}MySQL 日志 (按 Ctrl+C 退出):${NC}"
            cd "$PROJECT_DIR"
            docker-compose logs -f mysql
            ;;
        redis)
            echo -e "${YELLOW}Redis 日志 (按 Ctrl+C 退出):${NC}"
            cd "$PROJECT_DIR"
            docker-compose logs -f redis
            ;;
        *)
            echo "用法: ./start.sh logs [backend|frontend|mysql|redis]"
            exit 1
            ;;
    esac
}

# 主命令处理
case "$1" in
    all)
        start_all
        ;;
    backend)
        start_infra
        start_backend
        ;;
    frontend)
        start_frontend
        ;;
    stop)
        stop_all
        ;;
    status)
        status
        ;;
    logs)
        logs "$2"
        ;;
    *)
        echo "K8s 发版平台启动脚本"
        echo ""
        echo "用法: ./start.sh [命令]"
        echo ""
        echo "命令:"
        echo "  all              启动所有服务 (MySQL + Redis + 后端 + 前端)"
        echo "  backend          启动基础设施和后端服务"
        echo "  frontend         启动前端服务"
        echo "  stop             停止所有服务"
        echo "  status           查看服务状态"
        echo "  logs [服务]      查看日志 (backend|frontend|mysql|redis)"
        echo ""
        echo "示例:"
        echo "  ./start.sh all                    # 启动所有服务"
        echo "  ./start.sh backend                # 只启动后端"
        echo "  ./start.sh logs backend           # 查看后端日志"
        exit 1
        ;;
esac
