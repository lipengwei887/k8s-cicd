#!/bin/sh
# Nginx 启动脚本 - 支持环境变量替换

# 设置默认值
export BACKEND_HOST=${BACKEND_HOST:-host.docker.internal}

# 替换环境变量到 nginx 配置
envsubst '$BACKEND_HOST' < /etc/nginx/conf.d/default.conf.template > /etc/nginx/conf.d/default.conf

echo "Backend host: $BACKEND_HOST"

# 执行传入的命令
exec "$@"
