#!/bin/bash
# init.sh: Single-entry initialization and deployment script for VSS Edge.
# 修正版：解决了 $COMPOSE_FILES 缺失和 Windows 路径问题

# 严格退出 on error
set -e

# --- Phase 1: Configuration Generation & Global Logging ---

# [新增日志配置] 定义日志文件和时间戳
LOG_TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
GLOBAL_LOG_FILE="deployment_log_${LOG_TIMESTAMP}.log"

# 将后续所有输出重定向到日志文件，并同时输出到终端 (tee)
exec > >(tee -a "$GLOBAL_LOG_FILE") 2>&1

echo "================================================"
echo "Visify Story Studio - Initialization and Deployment"
echo "Log file: $GLOBAL_LOG_FILE"
echo "================================================"

# --- Configuration Variables ---
ENV_TEMPLATE_FILE=".env.template"
ENV_FILE=".env"
REQUIRED_DIRS=("media_root" "staticfiles")

# [CRITICAL FIX] 确保 PROJECT_ROOT 是 docker cp 能够识别的绝对路径
# [FIXED] 恢复了 init_setup.sh 中对 Windows 路径的检查
PROJECT_ROOT=$(pwd)
if [[ "$PROJECT_ROOT" == *":"* ]]; then
    echo "Warning: Detected potential Windows path. Setting PROJECT_ROOT for compatibility."
    # 尝试使用 MSYS/MinGW 的 'pwd -W' 模式，确保路径以 / 开头，用于 docker cp
    PROJECT_ROOT=$(pwd -W)
fi
# -----

# --- Helper Functions (From init_setup.sh) ---
generate_secret() {
    openssl rand -hex 32
}

# --- Configuration Main Logic (来自 init_setup.sh) ---
echo "Visify Story Studio - Deployment Initializer"
echo "------------------------------------------------"

if [ ! -f "$ENV_TEMPLATE_FILE" ]; then
    echo "Error: Template file '$ENV_TEMPLATE_FILE' not found."
    exit 1
fi

if [ -f "$ENV_FILE" ]; then
    read -p "Warning: '$ENV_FILE' already exists. Do you want to overwrite it? [y/N]: " confirm
    if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
        echo "Aborted."
        exit 0
    fi
fi

echo "Generating new '$ENV_FILE' from template..."
cp "$ENV_TEMPLATE_FILE" "$ENV_FILE"

echo "Generating secure keys..."
DJANGO_SECRET_KEY=$(generate_secret)
POSTGRES_PASSWORD=$(generate_secret)

sed -i.bak "s|DJANGO_SECRET_KEY=.*|DJANGO_SECRET_KEY=${DJANGO_SECRET_KEY}|" "$ENV_FILE"
sed -i.bak "s|POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${POSTGRES_PASSWORD}|" "$ENV_FILE"

echo "Please provide initial settings for the instance:"

# --- Prompt for the Public Endpoint ---
read -p "Enter the Public Endpoint URL (e.g., http://your_server_ip or https://your_domain): " PUBLIC_ENDPOINT
sed -i.bak "s|PUBLIC_ENDPOINT=.*|PUBLIC_ENDPOINT=${PUBLIC_ENDPOINT}|" "$ENV_FILE"

# --- Other prompts ---
read -p "Enter the initial Django superuser email: " DJANGO_SUPERUSER_EMAIL
read -s -p "Enter the initial Django superuser password: " DJANGO_SUPERUSER_PASSWORD
echo

# [CRITICAL FIX]: LABEL_STUDIO_ACCESS_TOKEN 移至 DB，在此处将其值设为空
LABEL_STUDIO_ACCESS_TOKEN=""

# Improved: Suggest default based on Public Endpoint
HOSTNAME=$(echo "$PUBLIC_ENDPOINT" | sed -e 's|http://||' -e 's|https://||' -e 's|:[0-9]*$||')
DEFAULT_ALLOWED_HOSTS="localhost,127.0.0.1,${HOSTNAME}"
read -p "Enter comma-separated Allowed Hosts [${DEFAULT_ALLOWED_HOSTS}]: " DJANGO_ALLOWED_HOSTS
DJANGO_ALLOWED_HOSTS=${DJANGO_ALLOWED_HOSTS:-$DEFAULT_ALLOWED_HOSTS}

# Use sed to replace placeholders
sed -i.bak "s|DJANGO_SUPERUSER_EMAIL=.*|DJANGO_SUPERUSER_EMAIL=\"${DJANGO_SUPERUSER_EMAIL}\"|" "$ENV_FILE"
sed -i.bak "s|DJANGO_SUPERUSER_PASSWORD=.*|DJANGO_SUPERUSER_PASSWORD=\"${DJANGO_SUPERUSER_PASSWORD}\"|" "$ENV_FILE"
sed -i.bak "s|LABEL_STUDIO_ACCESS_TOKEN=.*|LABEL_STUDIO_ACCESS_TOKEN=\"${LABEL_STUDIO_ACCESS_TOKEN}\"|" "$ENV_FILE"
sed -i.bak "s|DJANGO_ALLOWED_HOSTS=.*|DJANGO_ALLOWED_HOSTS=\"${DJANGO_ALLOWED_HOSTS}\"|" "$ENV_FILE"

rm -f "${ENV_FILE}.bak"
chmod 600 "$ENV_FILE"

echo "Creating necessary directories..."
for dir in "${REQUIRED_DIRS[@]}"; do
    mkdir -p "$dir"
    chmod -R 777 "$dir"
done

echo "✅ Configuration successful. Starting deployment..."

# --- Phase 2: Deployment and Application Execution (来自 start_up.sh 并修复) ---

# Define file configuration
BASE_COMPOSE_FILE="docker-compose.base.yml"
DEPLOY_COMPOSE_FILE="docker-compose.local.yml"
# [FIXED] 确保 COMPOSE_FILES 变量在所有命令中都被使用
COMPOSE_FILES="-f $BASE_COMPOSE_FILE -f $DEPLOY_COMPOSE_FILE"
WEB_SERVICE="web"
DB_SERVICE="db"
PROJECT_NAME="visify-ssw" # <-- 锁定项目名称
COLLECTSTATIC_LOG_FILE="exec_tmp.log" # 用于捕获 exec 过程中的临时日志

# 1. 启动所有服务 (Launch all services)
echo "1. Bringing up all Docker services..."
# [FIXED] 确保 $COMPOSE_FILES 被使用
docker compose -p $PROJECT_NAME $COMPOSE_FILES up -d

# Check if services started successfully
if [ $? -ne 0 ]; then
    echo "❌ 错误: Docker Compose 启动服务失败。请检查 compose 文件和 Docker 状态。"
    exit 1
fi

# 1.1 复制配置文件到运行中的容器 (使用主机作为源)
echo "1.1 复制配置文件到容器内部 (使用主机作为源)..."
# 使用 $PROJECT_ROOT (已修复 Windows 路径)
docker cp ${PROJECT_ROOT}/configs/nginx/vss-media-server.conf vss-nginx-media:/etc/nginx/conf.d/default.conf
docker cp ${PROJECT_ROOT}/configs/nginx/nginx-ls.conf vss-label-studio:/etc/nginx/nginx.conf

# 1.2 重启 Nginx 服务以加载新配置...
echo "1.2 重启 Nginx 服务以加载新配置..."
# [FIXED] 此处必须添加 $COMPOSE_FILES
#docker compose -p $PROJECT_NAME $COMPOSE_FILES up -d --no-deps --force-recreate vss-nginx-media vss-label-studio
docker restart vss-nginx-media vss-label-studio

# 2. 等待数据库就绪 (强制健康检查)
echo "2. 等待服务就绪..."
sleep 5 # 初始等待
MAX_RETRIES=10
RETRY_COUNT=0

echo "2.1 正在等待 PostgreSQL 数据库容器 ($DB_SERVICE) 就绪..."
until [ $RETRY_COUNT -ge $MAX_RETRIES ]
do
    # [FIXED] 此处必须添加 $COMPOSE_FILES
    if docker compose -p $PROJECT_NAME $COMPOSE_FILES exec $DB_SERVICE pg_isready -q; then
        echo "✅ 数据库已就绪！"
        break
    fi

    RETRY_COUNT=$((RETRY_COUNT+1))
    echo "   数据库未就绪，重试 $RETRY_COUNT/$MAX_RETRIES..."
    sleep 5
done

if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
    echo "❌ 错误: 数据库未在规定时间内就绪，终止部署。"
    exit 1
fi
# --- 数据库健康检查结束 ---

# 3. 执行数据库迁移 (Migrate)
echo "3. 执行数据库迁移 (Migrate)..."
# [FIXED] 此处必须添加 $COMPOSE_FILES
if ! docker compose -p $PROJECT_NAME $COMPOSE_FILES exec $WEB_SERVICE python manage.py migrate --noinput > "$COLLECTSTATIC_LOG_FILE" 2>&1; then
    echo "❌ 错误: 数据库迁移失败！请查看日志 $GLOBAL_LOG_FILE 中引用的 $COLLECTSTATIC_LOG_FILE。"
    cat "$COLLECTSTATIC_LOG_FILE"
    exit 1
fi
echo "✅ 迁移成功完成。"

# 4. 执行自动化配置 (setup_instance)
echo "4. 执行自动化配置 (setup_instance)..."
# [FIXED] 此处必须添加 $COMPOSE_FILES
if ! docker compose -p $PROJECT_NAME $COMPOSE_FILES exec $WEB_SERVICE python manage.py setup_instance > "$COLLECTSTATIC_LOG_FILE" 2>&1; then
    echo "❌ 错误: setup_instance 失败！请查看日志 $GLOBAL_LOG_FILE 中引用的 $COLLECTSTATIC_LOG_FILE。"
    cat "$COLLECTSTATIC_LOG_FILE"
    exit 1
fi
echo "✅ 自动化配置成功完成。"


# 5. 自动收集静态文件 (Collect static files for Nginx)
echo "5. 收集静态文件 (collectstatic)..."
# [FIXED] 此处必须添加 $COMPOSE_FILES
if ! docker compose -p $PROJECT_NAME $COMPOSE_FILES exec $WEB_SERVICE python manage.py collectstatic --noinput > "$COLLECTSTATIC_LOG_FILE" 2>&1; then
    echo "❌ 错误: collectstatic 失败！请查看日志 $GLOBAL_LOG_FILE 中引用的 $COLLECTSTATIC_LOG_FILE。"
    cat "$COLLECTSTATIC_LOG_FILE"
    exit 1
fi
echo "✅ 静态文件收集成功完成。"
# 清理临时日志文件
rm "$COLLECTSTATIC_LOG_FILE" 2>/dev/null


echo "================================================"
echo "--- ✅ 部署完成 ---"
echo "日志文件已保存到 $GLOBAL_LOG_FILE"
echo "下一步操作 (首次安装):"
echo "1. 访问 Django Admin 页面 (例如: ${PUBLIC_ENDPOINT}/admin/)." # 假设 Nginx 代理 8000 端口
echo "2. 导航至 [系统设置] -> [集成设置] 页面，配置 Label Studio Token。"
echo "================================================"