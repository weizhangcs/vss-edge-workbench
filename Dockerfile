#FROM python:3.12-slim 官方Python精简镜像
#FROM docker.xuanyuan.run/library/python:3.12-slim 轩辕镜像的代理加速地址
#国内阿里云的镜像仓库（避免配置docker desktop的registry）
FROM crpi-34v4qt829vtet2cy.cn-hangzhou.personal.cr.aliyuncs.com/vss_base/python:3.12-slim

# 声明构建参数（可配置镜像源）
ARG APT_MIRROR=mirrors.aliyun.com
ARG PIP_MIRROR_URL=https://pypi.tuna.tsinghua.edu.cn/simple/

# 环境变量配置
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# 配置系统APT源（使用阿里云镜像）
RUN sed -i "s|deb.debian.org|$APT_MIRROR|g" /etc/apt/sources.list.d/debian.sources && \
    sed -i "s|security.debian.org|$APT_MIRROR|g" /etc/apt/sources.list.d/debian.sources

# 安装系统依赖（带清理）
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        gcc \
        libpq-dev \
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 先单独复制依赖文件（利用Docker缓存层）
COPY requirements.txt .

# 配置pip镜像并安装依赖
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -i ${PIP_MIRROR_URL} -r requirements.txt

# 复制应用代码
COPY . .

# 安全最佳实践（非root用户运行）
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# 健康检查（根据应用调整）
HEALTHCHECK --interval=30s --timeout=3s \
  CMD python -c "import requests; requests.get('http://localhost:8000/health')" || exit 1

# 应用入口点
EXPOSE 8000
CMD ["python", "app.py"]
