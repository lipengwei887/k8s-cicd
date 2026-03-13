#!/bin/bash

# K8s 发版平台启动脚本
# 用法: ./start.sh [frontend|backend|all]

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

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查端口是否被占用
check_port() {
    local port=$1
    if lsof -ti:$port > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# 杀死占用端口的进程
kill_port() {
    local port=$1
    if check_port $port; then
        log_warn "Port $port is occupied, killing process..."
        lsof -ti:$port | xargs kill -9 2>/dev/null || true
        sleep 1
    fi
}

# 启动后端
start_backend() {
    log_info "Starting backend service..."
    
    # 检查虚拟环境
    if [ ! -d "$BACKEND_DIR/venv" ]; then
        log_error "Virtual environment not found. Please run: cd backend && python -m venv venv"
        exit 1
    fi
    
    # 杀死占用 8000 端口的进程
    kill_port 8000
    
    # 启动后端服务
    cd "$BACKEND_DIR"
    source venv/bin/activate
    
    log_info "Backend starting on http://localhost:8000"
    nohup venv/bin/uvicorn app.main:app --reload --port 8000 --log-level info > backend.log 2>&1 &
    
    # 等待服务启动
    sleep 3
    
    if check_port 8000; then
        log_info "Backend started successfully!"
    else
        log_error "Backend failed to start. Check backend.log for details."
        exit 1
    fi
}

# 启动前端
start_frontend() {
    log_info "Starting frontend service..."
    
    # 检查 node_modules
    if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
        log_warn "node_modules not found. Installing dependencies..."
        cd "$FRONTEND_DIR"
        npm install
    fi
    
    # 杀死占用 3000 端口的进程
    kill_port 3000
    
    # 启动前端服务
    cd "$FRONTEND_DIR"
    
    log_info "Frontend starting on http://localhost:3000"
    nohup npm run dev > frontend.log 2>&1 &
    
    # 等待服务启动
    sleep 5
    
    if check_port 3000; then
        log_info "Frontend started successfully!"
    else
        log_error "Frontend failed to start. Check frontend.log for details."
        exit 1
    fi
}

# 停止所有服务
stop_all() {
    log_info "Stopping all services..."
    kill_port 8000
    kill_port 3000
    log_info "All services stopped."
}

# 查看状态
status() {
    log_info "Service status:"
    
    if check_port 8000; then
        echo "  Backend:  ${GREEN}Running${NC} (http://localhost:8000)"
    else
        echo "  Backend:  ${RED}Stopped${NC}"
    fi
    
    if check_port 3000; then
        echo "  Frontend: ${GREEN}Running${NC} (http://localhost:3000)"
    else
        echo "  Frontend: ${RED}Stopped${NC}"
    fi
}

# 查看日志
logs() {
    local service=$1
    case $service in
        backend)
            tail -f "$BACKEND_DIR/backend.log"
            ;;
        frontend)
            tail -f "$FRONTEND_DIR/frontend.log"
            ;;
        *)
            log_error "Usage: ./start.sh logs [backend|frontend]"
            exit 1
            ;;
    esac
}

# 主函数
main() {
    case "${1:-all}" in
        backend)
            start_backend
            ;;
        frontend)
            start_frontend
            ;;
        all)
            start_backend
            start_frontend
            log_info ""
            log_info "=================================="
            log_info "All services started successfully!"
            log_info "=================================="
            log_info "Backend:  http://localhost:8000"
            log_info "Frontend: http://localhost:3000"
            log_info ""
            log_info "Commands:"
            log_info "  ./start.sh stop     - Stop all services"
            log_info "  ./start.sh status   - Check service status"
            log_info "  ./start.sh logs backend  - View backend logs"
            log_info "  ./start.sh logs frontend - View frontend logs"
            ;;
        stop)
            stop_all
            ;;
        status)
            status
            ;;
        logs)
            logs $2
            ;;
        *)
            echo "Usage: ./start.sh [backend|frontend|all|stop|status|logs]"
            echo ""
            echo "Commands:"
            echo "  backend  - Start backend service only"
            echo "  frontend - Start frontend service only"
            echo "  all      - Start both services (default)"
            echo "  stop     - Stop all services"
            echo "  status   - Check service status"
            echo "  logs     - View service logs"
            exit 1
            ;;
    esac
}

main "$@"
