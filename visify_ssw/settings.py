"""
Django settings for visify_ssw project.
"""
import os
from pathlib import Path
from decouple import config
from django.urls import reverse_lazy

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config('DJANGO_SECRET_KEY')
DEBUG = config('DJANGO_DEBUG', default=True, cast=bool)
ALLOWED_HOSTS_str = config('DJANGO_ALLOWED_HOSTS', default='localhost,127.0.0.1')
ALLOWED_HOSTS = [host.strip() for host in ALLOWED_HOSTS_str.split(',') if host.strip()]

INSTALLED_APPS = [
    'unfold',
    'unfold.contrib.forms',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'apps.media_assets.apps.MediaAssetsConfig',
    'apps.configuration.apps.ConfigurationConfig',
    'apps.workflow.apps.WorkflowConfig',
    'corsheaders',
    'solo',
    'crispy_forms',
    'crispy_tailwind',
]

AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
)

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'visify_ssw.urls'

# --- LOGGING CONFIGURATION ---
# This configuration makes INFO level logs visible in the console
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO', # Set the handler to process INFO level messages
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': { # Configure the root logger
        'handlers': ['console'],
        'level': 'INFO', # Set the logger to capture INFO level messages
    },
}

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'visify_ssw.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('POSTGRES_DB'),
        'USER': config('POSTGRES_USER'),
        'PASSWORD': config('POSTGRES_PASSWORD'),
        'HOST': 'db',
        'PORT': '5432',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True


#STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media_root'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

CELERY_BROKER_URL = config("CELERY_BROKER_URL", default="redis://redis:6379/0")
CELERY_RESULT_BACKEND = config("CELERY_BROKER_URL", default="redis://redis:6-379/0")
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_IMPORTS = (
    'apps.media_assets.tasks',
    'apps.workflow.transcoding.tasks',
    'apps.workflow.delivery.tasks',
    'apps.workflow.annotation.tasks',
    'apps.workflow.inference.tasks',
)

AWS_ACCESS_KEY_ID = config('AWS_ACCESS_KEY_ID', default='')
AWS_SECRET_ACCESS_KEY = config('AWS_SECRET_ACCESS_KEY', default='')
AWS_STORAGE_BUCKET_NAME = config('AWS_STORAGE_BUCKET_NAME', default='')
AWS_S3_REGION_NAME = config('AWS_S3_REGION_NAME', default='')
AWS_S3_CUSTOM_DOMAIN = config('AWS_S3_CUSTOM_DOMAIN', default='')
AWS_S3_PROCESSED_VIDEOS_PREFIX = config('AWS_S3_PROCESSED_VIDEOS_PREFIX', default='processed_videos/')
AWS_S3_SOURCE_SUBTITLES_PREFIX = config('AWS_S3_SOURCE_SUBTITLES_PREFIX', default='source_subtitles/')

CORS_ALLOWED_ORIGINS_str = config('CORS_ALLOWED_ORIGINS', default='http://localhost:3000,http://127.0.0.1:3000')
CORS_ALLOWED_ORIGINS = [origin.strip() for origin in CORS_ALLOWED_ORIGINS_str.split(',') if origin.strip()]
CORS_ALLOW_METHODS = ["DELETE", "GET", "OPTIONS", "PATCH", "POST", "PUT"]
CORS_ALLOW_HEADERS = ["accept", "authorization", "content-type", "user-agent", "x-csrftoken", "x-requested-with"]

SUBEDITOR_URL = config("SUBEDITOR_URL", default="http://subeditor:3000")
LABEL_STUDIO_URL = config('LABEL_STUDIO_INTERNAL_URL', default='http://label-studio:8080')
LOCAL_MEDIA_URL_BASE = config('LOCAL_MEDIA_URL_BASE', default='http://localhost:9999')
LABEL_STUDIO_PUBLIC_URL = config("LABEL_STUDIO_PUBLIC_URL", default="http://localhost:8081")
SUBEDITOR_PUBLIC_URL = config("SUBEDITOR_PUBLIC_URL", default="http://localhost:3000")
LABEL_STUDIO_ACCESS_TOKEN = config('LABEL_STUDIO_ACCESS_TOKEN', default='')

# --- 新增：Cloud API 设置 ---
CLOUD_API_BASE_URL = config('CLOUD_API_BASE_URL', default='')
CLOUD_INSTANCE_ID = config('CLOUD_INSTANCE_ID', default='')
CLOUD_API_KEY = config('CLOUD_API_KEY', default='')

STATIC_URL = f'{LOCAL_MEDIA_URL_BASE}/static/'

STORAGE_BACKEND = config('STORAGE_BACKEND', default='local')
FFMPEG_VIDEO_BITRATE = config('FFMPEG_VIDEO_BITRATE', default='2M')
FFMPEG_VIDEO_PRESET = config('FFMPEG_VIDEO_PRESET', default='fast')

UNFOLD = {
    "SITE_TITLE": "Visify Story Studio",
    "SIDEBAR": {
        "navigation": [
            # '工作台' 和 '媒资管理' 保持不变
            {'title': '工作台', 'items': [{'title': '仪表盘', 'icon': 'space_dashboard', 'link': reverse_lazy('admin:index')}]},
            {'title': '媒资管理', 'separator': True, 'items': [
                {'title': '内容资产', 'link': reverse_lazy('admin:media_assets_asset_changelist'), 'icon': 'video_library'},
                {'title': '媒体文件', 'link': reverse_lazy('admin:media_assets_media_changelist'), 'icon': 'movie'}
            ]},
            # 1. 创建“转码工作流”一级菜单
            {
                'title': '转码工作流',
                'separator': True,
                'items': [
                    {
                        'title': '转码项目',
                        'icon': 'movie_filter',
                        'link': reverse_lazy('admin:workflow_transcodingproject_changelist')
                    },
                    {
                        'title': '转码任务',
                        'icon': 'history',
                        'link': reverse_lazy('admin:workflow_transcodingjob_changelist')
                    },
                    {
                        'title': '转码配置', # 从“系统设置”移动到这里
                        'icon': 'tune',
                        'link': reverse_lazy('admin:configuration_encodingprofile_changelist')
                    },
                ]
            },
            # 2. 创建“标注工作流”一级菜单
            {
                'title': '建模工作流',  # <-- (来自你的澄清 1)
                'separator': True,
                'items': [
                    # [!!! 步骤 2.3: 更新二级菜单 !!!]
                    {
                        'title': '标注项目',  # <-- (来自你的澄清 2)
                        'icon': 'rate_review',
                        'link': reverse_lazy('admin:workflow_annotationproject_changelist')
                    },
                    {
                        'title': '推理项目',  # <-- (来自你的澄清 2)
                        'icon': 'insights',  # (新图标)
                        'link': reverse_lazy('admin:workflow_inferenceproject_changelist')  # (新 URL)
                    },
                ]
            },
            {
                'title': '创作工作流',
                'separator': True,
                'items': [
                    {
                        'title': '解说词项目',
                        'icon': 'send',  # 一个表示发送/分发的图标
                        'link': reverse_lazy('admin:workflow_deliveryjob_changelist')
                    },
                ]
            },
            # 4. 创建“分发工作流”一级菜单
            {
                'title': '分发工作流',
                'separator': True,
                'items': [
                    {
                        'title': '分发任务',
                        'icon': 'send',  # 一个表示发送/分发的图标
                        'link': reverse_lazy('admin:workflow_deliveryjob_changelist')
                    },
                ]
            },
            # 5. 更新“系统设置”菜单，移除“编码配置”
            {'title': '系统设置', 'separator': True, 'items': [
                {'title': '集成设置', 'link': reverse_lazy('admin:configuration_integrationsettings_changelist'), 'icon': 'hub'},
                {'title': '用户', 'link': reverse_lazy('admin:auth_user_changelist'), 'icon': 'group'},
                {'title': '用户组', 'link': reverse_lazy('admin:auth_group_changelist'), 'icon': 'groups'}
            ]}
        ],
    },
    "TABS": "apps.workflow.tabs.get_global_tabs"
}

# --- Crispy Forms Configuration ---
CRISPY_ALLOWED_TEMPLATE_PACKS = "tailwind"
CRISPY_TEMPLATE_PACK = "tailwind"