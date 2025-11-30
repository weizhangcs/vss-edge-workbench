#!/bin/bash
# init.sh: Single-entry initialization and deployment script for VSS Edge.
# 修正版V9：最终健壮版，增加所有关键配置文件和目录的存在性检查。

# 严格退出 on error
set -e

# --- Phase 1: Configuration Generation & Global Logging ---

# 定义日志文件和时间戳
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

# Docker Compose 文件
BASE_COMPOSE_FILE="docker-compose.base.yml"
DEPLOY_COMPOSE_FILE="docker-compose.dev.yml"

# Nginx 配置文件 (必须存在，用于卷挂载)
NGINX_MEDIA_CONF="configs/nginx/vss-media-server.conf"
NGINX_LS_CONF="configs/nginx/nginx-ls.conf"

# 必需的 volumes 目录
REQUIRED_DIRS=("media_root" "staticfiles" "configs/nginx")

# --- Helper Functions ---
generate_secret() {
    openssl rand -hex 32
}

# --- 关键前置检查函数 ---
check_file_exists() {
    FILE=$1
    if [ ! -f "$FILE" ]; then
        echo "❌ 错误: 关键文件 '$FILE' 未找到。请确保该文件位于正确位置。"
        exit 1
    fi
}

# --- Configuration Main Logic ---
echo "Visify Story Studio - Deployment Initializer"
echo "------------------------------------------------"

# 1. 检查所有必需的配置文件
check_file_exists "$ENV_TEMPLATE_FILE"
check_file_exists "$BASE_COMPOSE_FILE"
check_file_exists "$DEPLOY_COMPOSE_FILE"
check_file_exists "$NGINX_MEDIA_CONF"
check_file_exists "$NGINX_LS_CONF"

# 2. 处理 .env 文件
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

# [新增] Cloud API 交互配置模块
echo
echo "--- Cloud API Configuration (VSS-Cloud) ---"
echo "Please enter the connection details for the Cloud Orchestrator."
read -p "Cloud API Base URL (e.g., http://cloud.example.com:8000): " CLOUD_API_BASE_URL
read -p "Cloud Instance ID (Your Edge unique ID): " CLOUD_INSTANCE_ID
read -p "Cloud API Key: " CLOUD_API_KEY
echo

# [配置移至 DB]: LABEL_STUDIO_ACCESS_TOKEN 移至 DB，在此处将其值设为空
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
# 创建 volumes 和 configs/nginx 目录
for dir in "${REQUIRED_DIRS[@]}"; do
    mkdir -p "$dir"
    chmod -R 777 "$dir" # 确保挂载目录权限开放
done

echo "✅ Configuration successful. Starting deployment..."

# --- Phase 2: Deployment and Application Execution (基于声明式架构) ---

# Define file configuration
COMPOSE_FILES="-f $BASE_COMPOSE_FILE -f $DEPLOY_COMPOSE_FILE"
WEB_SERVICE="web"
DB_SERVICE="db"
PROJECT_NAME="visify-edge" # <-- 锁定项目名称
COLLECTSTATIC_LOG_FILE="exec_tmp.log" # 用于捕获 exec 过程中的临时日志

# 1. 启动所有服务 (Launch all services)
echo "1. Bringing up all Docker services..."
# Nginx 配置均通过卷挂载解决，无需特殊处理。
docker compose -p $PROJECT_NAME $COMPOSE_FILES up -d

# Check if services started successfully
if [ $? -ne 0 ]; then
    echo "❌ 错误: Docker Compose 启动服务失败。请检查 compose 文件和 Docker 状态。"
    exit 1
fi

# 1.1 复制配置文件到运行中的容器 (已清除)
echo "1.1 配置文件已通过卷挂载实现，跳过运行时配置操作。"

# 1.2 重启 Nginx 服务以加载新配置... (已清除)
echo "1.2 Nginx 服务已通过卷挂载加载配置，跳过运行时重启操作。"

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

# --- [步骤 3.1: 自动化获取 Legacy API Token (简洁修复版)] ---
echo "3.1 正在等待 Label Studio 启动并尝试获取 Legacy API Token..."
LS_SERVICE_NAME="label_studio"
MAX_LS_RETRIES=10
LS_RETRY_COUNT=0
# [修正] 直接使用 LABEL_STUDIO_ACCESS_TOKEN 变量
LABEL_STUDIO_ACCESS_TOKEN=""

# 循环条件：当 LABEL_STUDIO_ACCESS_TOKEN 非空时跳出
until [ -n "$LABEL_STUDIO_ACCESS_TOKEN" ] || [ $LS_RETRY_COUNT -ge $MAX_LS_RETRIES ]
do
    sleep 5

    # 步骤 1: 尝试执行 'label-studio user' 命令，并使用 '|| true' 压制 exec 的退出代码
    # 注意：我们必须使用一个临时的 SHELL 变量来接收命令输出，防止解析失败导致主变量污染
    # 注意：容器命名 label_studio 命令行 label-studio
    LS_OUTPUT=$(docker compose -p $PROJECT_NAME $COMPOSE_FILES exec $LS_SERVICE_NAME sh -c "label-studio user --username \"$DJANGO_SUPERUSER_EMAIL\"" 2>/dev/null | tail -n 1) || true

    # 步骤 2: [核心修正] 将解析结果直接赋值给主变量
    TEMP_TOKEN_RESULT=$(echo "$LS_OUTPUT" | sed -n "s/.*'token': '\([^']*\)'.*/\1/p")
    LABEL_STUDIO_ACCESS_TOKEN=${TEMP_TOKEN_RESULT}

    if [ -z "$LABEL_STUDIO_ACCESS_TOKEN" ]; then
        LS_RETRY_COUNT=$((LS_RETRY_COUNT+1))
        echo "   Token 尚未获取 (重试 $LS_RETRY_COUNT/$MAX_LS_RETRIES)..."
    fi
done

if [ -z "$LABEL_STUDIO_ACCESS_TOKEN" ]; then
    echo "❌ 错误: 无法在规定时间内获取 Label Studio API Token。将使用 'Manual_Setup_Required' 占位符。"
    LABEL_STUDIO_ACCESS_TOKEN="Manual_Setup_Required"
fi

if [ "$LABEL_STUDIO_ACCESS_TOKEN" != "Manual_SETUP_REQUIRED" ]; then
    echo "✅ 成功获取 Legacy API Token (前10位): ${LABEL_STUDIO_ACCESS_TOKEN:0:10}..."
fi
# --- [步骤 3.1 结束] ---

# 4. 执行自动化配置 (setup_instance)
echo "4. 执行自动化配置 (setup_instance)..."
# [核心修改] 将 Token 作为命令行参数 --ls-token 传递

# 注意：我们使用 LABEL_STUDIO_ACCESS_TOKEN 变量（您之前修正的变量名）
docker compose -p $PROJECT_NAME $COMPOSE_FILES exec $WEB_SERVICE python manage.py setup_instance \
    --ls-token="$LABEL_STUDIO_ACCESS_TOKEN" \
    --cloud-url="$CLOUD_API_BASE_URL" \
    --cloud-id="$CLOUD_INSTANCE_ID" \
    --cloud-key="$CLOUD_API_KEY" > "$COLLECTSTATIC_LOG_FILE" 2>&1
SETUP_INSTANCE_EXIT_CODE=$?

# 无论成功或失败，先显示 DEBUG 日志
cat "$COLLECTSTATIC_LOG_FILE"

if [ $SETUP_INSTANCE_EXIT_CODE -ne 0 ]; then
    # 失败路径
    echo "❌ 错误: setup_instance 失败！请查看上方的 CRASH ERROR 日志。"
    exit 1
fi
# 成功路径
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
echo "1. 访问 Django Admin 页面 (例如: http://${HOSTNAME}:8000/admin/)."
echo "2. 导航至 [系统设置] -> [集成设置] 页面，配置 Label Studio Token。"
echo "================================================"