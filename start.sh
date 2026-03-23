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

# 检查 Python3 是否安装
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 python3，请先安装 Python 3.9+"
    exit 1
fi

# 检查虚拟环境
if [ -d "$SCRIPT_DIR/.venv" ]; then
    echo "使用虚拟环境: $SCRIPT_DIR/.venv"
    source "$SCRIPT_DIR/.venv/bin/activate"
elif [ -d "venv" ]; then
    echo "使用虚拟环境: $BACKEND_DIR/venv"
    source venv/bin/activate
elif [ -d ".venv" ]; then
    echo "使用虚拟环境: $BACKEND_DIR/.venv"
    source .venv/bin/activate
fi

# 检查依赖是否安装
echo "检查依赖..."
python3 -c "import fastapi" 2>/dev/null || {
    echo "安装依赖..."
    pip3 install -r requirements.txt
}

# 检查 .env 文件
if [ ! -f ".env" ]; then
    echo "警告: 未找到 .env 文件，使用默认配置"
fi

# 获取运行模式
MODE="${1:-dev}"

# 根据模式启动
case "$MODE" in
    dev)
        echo "启动后端服务 (开发模式)..."
        echo "访问地址: http://localhost:8000"
        echo "API 文档: http://localhost:8000/docs"
        echo "按 Ctrl+C 停止服务"
        echo ""
        exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
        ;;
    prod)
        echo "启动后端服务 (生产模式)..."
        echo "访问地址: http://localhost:8000"
        echo "按 Ctrl+C 停止服务"
        echo ""
        # 生产模式: 多个 worker，禁用热重载
        exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
        ;;
    *)
        echo "用法: $0 [dev|prod]"
        echo "  dev  - 开发模式（热重载）"
        echo "  prod - 生产模式"
        exit 1
        ;;
esac
