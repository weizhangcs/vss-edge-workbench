# 1. 定义变量
REGISTRY="crpi-34v4qt829vtet2cy.cn-hangzhou.personal.cr.aliyuncs.com"
NAMESPACE="vss_edge"
TARGET_PREFIX="${REGISTRY}/${NAMESPACE}"

# 2. 登录阿里云 (如果尚未登录)
#docker login "${REGISTRY}"

# 3. 搬运 Postgres
docker pull postgres:16
docker tag postgres:16 "${TARGET_PREFIX}/postgres:16"
docker push "${TARGET_PREFIX}/postgres:16"

# 4. 搬运 Redis
docker pull redis:7-alpine
docker tag redis:7-alpine "${TARGET_PREFIX}/redis:7-alpine"
docker push "${TARGET_PREFIX}/redis:7-alpine"

# 5. 搬运 Nginx
docker pull nginx:1.25-alpine
docker tag nginx:1.25-alpine "${TARGET_PREFIX}/nginx:1.25-alpine"
docker push "${TARGET_PREFIX}/nginx:1.25-alpine"

# 6. 搬运 Label Studio
docker pull heartexlabs/label-studio:latest
docker tag heartexlabs/label-studio:latest "${TARGET_PREFIX}/label-studio:latest"
docker push "${TARGET_PREFIX}/label-studio:latest"