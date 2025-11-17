#!/bin/bash
# start_up.sh: Fully automates the application launch, migration, and configuration steps.

echo "--- VSS Application Startup Script ---"

# 定义文件配置 (请根据您使用的部署文件名称进行调整)
BASE_COMPOSE_FILE="docker-compose.base.yml"
DEPLOY_COMPOSE_FILE="docker-compose.local.yml"
COMPOSE_FILES="-f $BASE_COMPOSE_FILE -f $DEPLOY_COMPOSE_FILE"
WEB_SERVICE="web"

# 1. 启动所有服务 (Launch all services)
echo "1. Bringing up all Docker services..."
docker compose $COMPOSE_FILES up -d

# 检查服务是否启动成功
if [ $? -ne 0 ]; then
    echo "❌ 错误: Docker Compose 启动服务失败。退出。"
    exit 1
fi

# 2. 等待数据库和 Web 服务就绪 (Wait for DB and Web service readiness)
echo "2. 等待服务就绪..."
sleep 15 # 给予时间启动数据库、Web 和 Celery

# 3. 执行数据库迁移 (Run database migrations - 幂等操作，安全)
echo "3. 执行数据库迁移 (Migrate)..."
docker compose $COMPOSE_FILES exec $WEB_SERVICE python manage.py migrate --noinput

# 4. 执行自动化配置 (创建超级用户, 默认编码配置等)
echo "4. 执行自动化配置 (setup_instance)..."
docker compose $COMPOSE_FILES exec $WEB_SERVICE python manage.py setup_instance

# 5. 自动收集静态文件 (Collect static files for Nginx)
echo "5. 收集静态文件 (collectstatic)..."
docker compose $COMPOSE_FILES exec $WEB_SERVICE python manage.py collectstatic --noinput

echo "--- ✅ 部署完成 ---"

# --- 后续操作提示 ---
echo "下一步操作 (首次安装):"
echo "1. 访问 Django Admin 页面 (例如: http://your-ip:8000/admin/)."
echo "2. 导航至 [系统设置] -> [集成设置] 页面。"
echo "3. 填写并保存 [Label Studio API Token] (Token 需从 Label Studio 页面获取)。"
echo "4. 完成配置后，应用将自动启用标注功能，无需重启。"