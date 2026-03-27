#!/bin/bash
# K8s Release Platform 后端启动脚本
# 使用方式: ./start.sh [dev|prod]
#   dev  - 开发模式（热重载）
#   prod - 生产模式

set -e

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"

# 检查后端目录是否存在
if [ ! -d "$BACKEND_DIR" ]; then
    echo "错误: 找不到后端目录 $BACKEND_DIR"
    exit 1
fi

cd "$BACKEND_DIR"

# 使用虚拟环境中的 Python
PYTHON_CMD="$BACKEND_DIR/venv/bin/python"

# 检查虚拟环境是否存在
if [ ! -f "$PYTHON_CMD" ]; then
    echo "错误: 未找到虚拟环境 $PYTHON_CMD"
    echo "请先创建虚拟环境: python3 -m venv venv"
    exit 1
fi

echo "使用 Python: $PYTHON_CMD"
$PYTHON_CMD --version

# 检查依赖是否安装
echo "检查依赖..."
$PYTHON_CMD -c "import fastapi" 2>/dev/null || {
    echo "安装依赖..."
    $PYTHON_CMD -m pip install -r requirements.txt
}

# 检查 .env 文件
if [ ! -f ".env" ]; then
    echo "警告: 未找到 .env 文件，使用默认配置"
fi

# 获取运行模式
MODE="${1:-dev}"

# 日志文件
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/backend.log"

# 根据模式启动
case "$MODE" in
    dev)
        echo "启动后端服务 (开发模式)..."
        echo "访问地址: http://localhost:8000"
        echo "API 文档: http://localhost:8000/docs"
        echo "日志文件: $LOG_FILE"
        echo "按 Ctrl+C 停止服务"
        echo ""
        exec $PYTHON_CMD -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload 2>&1 | tee -a "$LOG_FILE"
        ;;
    prod)
        echo "启动后端服务 (生产模式)..."
        echo "访问地址: http://localhost:8000"
        echo "日志文件: $LOG_FILE"
        echo "按 Ctrl+C 停止服务"
        echo ""
        # 生产模式: 多个 worker，禁用热重载，后台运行
        nohup $PYTHON_CMD -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4 > "$LOG_FILE" 2>&1 &
        echo "后端服务已后台启动，PID: $!"
        echo "查看日志: tail -f $LOG_FILE"
        ;;
    logs)
        # 查看日志
        if [ -f "$LOG_FILE" ]; then
            tail -f "$LOG_FILE"
        else
            echo "日志文件不存在: $LOG_FILE"
            exit 1
        fi
        ;;
    stop)
        # 停止服务
        echo "停止后端服务..."
        pkill -f "uvicorn app.main:app" 2>/dev/null && echo "已停止" || echo "服务未运行"
        ;;
    *)
        echo "用法: $0 [dev|prod|logs|stop]"
        echo "  dev   - 开发模式（热重载，前台运行）"
        echo "  prod  - 生产模式（后台运行）"
        echo "  logs  - 查看日志"
        echo "  stop  - 停止服务"
        exit 1
        ;;
esac
