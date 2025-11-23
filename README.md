
## README.md: Visify Story Studio (Edge) 
 
本项目是 Visify Story Studio 的边缘端工作台（Edge Workbench）。作为一个本地优先的“生产与合成中心”，它负责管理大规模视频媒资、执行人机协同标注（HITL），并利用本地算力完成最终的视频渲染与合成。 
 
### 1. 架构概览 
 
在 VSS 的“云-边”协同架构中，Edge 端承担着重资产和交互密集的任务： 
 
* 边缘端 (本项目)： 
 * 媒资管理 (MAM)：本地存储和管理原始视频素材（Source Video），无需上传至云端，保护隐私并节省带宽。 
 * 人机协同 (Human-in-the-loop)：集成 Subeditor (字幕/台词校对) 和 Label Studio (场景/语义标注)，提供流畅的标注体验。 
 * 视频合成 (Synthesis)：接收云端的“指令集”，利用本地 FFmpeg 结合原始高清素材，渲染最终成片。 
* 协同模式：Edge 端仅向 Cloud 端发送轻量级的结构化数据（如 JSON 蓝图、压缩后的参考音频），并从 Cloud 端接收生成好的脚本和配音素材。 
 
核心技术栈：Django 4.2 / Celery / Redis / PostgreSQL / Docker / FFmpeg。 
集成组件：Label Studio (语义标注), VSS Subeditor (字幕校对)。 
 
--- 
 
### 2. 环境配置与编排 
 
本项目采用分层配置策略，通过 docker-compose 覆盖机制适应不同环境： 
 
| 场景 | 组合命令 | 描述 | 
| :--- | :--- | :--- | 
| 本地开发 | -f base.yml -f dev.yml | 挂载本地源码，开启 Debug 模式，暴露所有端口。 | 
| 局域网测试 | -f base.yml -f test.yml | 拉取 dev 分支镜像，模拟真实部署，用于团队内部联调。 | 
| 生产部署 | -f base.yml -f prod.yml | 拉取 release 镜像，生产级配置，稳定性优先。 | 
 
--- 
 
### 3. 本地开发环境工作指南 
 
本项目提供了自动化脚本 init.sh 来处理复杂的初始化流程（包括密钥生成、目录权限、Nginx 配置等）。 
 
#### 3.1. 首次启动 (Initialization) 
 
适用于刚刚 Clone 项目或重置环境后的第一次运行。 
 
1. 运行引导脚本： 
```bash 
    chmod +x init.sh 
    ./init.sh # 脚本将交互式引导配置 
``` 
 > 提示：脚本会自动检查 media_root 权限，生成 .env 文件，并尝试自动获取 Label Studio 的 API Token。 
 
2. 配置 Cloud API： 
 启动后，需访问 Django Admin -> 系统设置 -> 集成设置，填入 Cloud 端的 Base URL、Instance ID 和 API Key，以打通云边协同链路。 
 
#### 3.2. 日常操作 (Daily Routine) 
 
日常开发请使用 Docker Compose 命令： 
 
* 启动服务： 
```bash 
  docker compose -f docker-compose.base.yml -f docker-compose.dev.yml up -d 
```

* 查看日志 (推荐监控 Web 和 Worker)： 
```bash  
  docker compose -f docker-compose.base.yml -f docker-compose.dev.yml logs -f web celery_worker 
```

* 执行迁移： 
```bash 
  # 先在本地生成迁移文件 (如果修改了 models) 
  docker compose -f docker-compose.base.yml -f docker-compose.dev.yml run --rm web python manage.py makemigrations 
  # 执行迁移 
  docker compose -f docker-compose.base.yml -f docker-compose.dev.yml run --rm web python manage.py migrate 
``` 
 
#### 3.3. 服务访问入口 
 
* VSS Workbench (管理后台): http://localhost:8000/admin/ 
* Label Studio (标注系统): http://localhost:8081 
* Subeditor (字幕工具): http://localhost:3000 
* Local Media Server (Nginx): http://localhost:9999 (提供静态资源和流媒体服务) 
 
--- 
 
### 4. 生产环境部署指南 
 
生产环境通常部署在高性能工作站或 GPU 服务器上。 
 
#### 4.1. 部署与升级 
 
1. 拉取最新镜像： 
```bash 
  docker compose -f docker-compose.base.yml -f docker-compose.prod.yml pull 
``` 
 
2. 应用数据库变更： 
```bash 
  docker compose -f docker-compose.base.yml -f docker-compose.prod.yml run --rm web python manage.py migrate 
``` 
 
3. 收集静态文件： 
```bash  
  docker compose -f docker-compose.base.yml -f docker-compose.prod.yml run --rm web python manage.py collectstatic --noinput 
``` 
 
4. 启动/重启服务： 
```bash 
  docker compose -f docker-compose.base.yml -f docker-compose.prod.yml up -d 
``` 
 
#### 4.2. 故障排查 (Troubleshooting) 
 
* Label Studio 无法加载资源：检查 .env 中的 LOCAL_MEDIA_URL_BASE 是否正确指向了 Nginx 服务的地址（如局域网 IP）。 
* 转码/合成失败：检查 media_root 的磁盘空间，或查看 celery_worker 日志中的 FFmpeg 报错信息。 
* Cloud API 404：检查集成设置中的 Cloud API Base URL 末尾是否多余了斜杠，或者 Cloud 端服务是否正常。 
 
--- 
 
### 5. 核心工作流 (Core Workflows) 
 
Edge 端主要包含四条核心流水线，由 Django Admin 驱动： 
 
1. 摄取 (Ingestion)： 
 * 将视频/字幕文件放入 media_root/batch_uploads/{asset_id}/。 
 * 系统自动识别、归档并创建 Media 对象。 
2. 转码 (Transcoding)： 
 * 将高码率原始素材转码为适合 Web 播放的代理视频 (Proxy Video)。 
 * 自动分发至 Nginx 或 S3 供标注工具使用。 
3. 标注与推理 (Annotation & Inference)： 
 * L1: 使用 Subeditor 校对字幕与台词。 
 * L2: 使用 Label Studio 进行场景切分与高光标记。 
 * L3: 上传蓝图至 Cloud，触发角色分析与 RAG 知识库构建。 
4. 创作与合成 (Creative & Synthesis)： 
 * L4: 配置参数 -> 触发 Cloud 生成解说词与配音 -> 下载资源 -> 本地 FFmpeg 合成最终视频。