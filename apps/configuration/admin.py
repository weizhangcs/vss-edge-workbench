# 文件路径: apps/configuration/admin.py

from django.contrib import admin
from django.urls import path, reverse
from django.shortcuts import redirect
from django.contrib import messages

from solo.admin import SingletonModelAdmin
from unfold.admin import ModelAdmin
# 确保导入我们需要的组件
from apps.workflow.widgets import FileFieldWithActionButtonWidget
from .models import IntegrationSettings, EncodingProfile

@admin.register(IntegrationSettings)
class IntegrationSettingsAdmin(ModelAdmin, SingletonModelAdmin): # <-- 核心修正：多重继承
    fieldsets = (
        ("权限管理 (Authorization)", {
            'fields': ('superuser_emails',)
        }),
        # [新增 Fieldset] 外部服务认证 Token
        ("外部服务认证 (External Tokens)", {
            'fields': ('label_studio_access_token',)  # <-- [新增]
        }),
        # [NEW FIELDSET] Cloud Service Configuration
        ("云端服务配置 (Cloud Services)", {
            'fields': ('cloud_api_base_url', 'cloud_instance_id', 'cloud_api_key')
        }),
        # [NEW FIELDSET] 存储后端配置 (Storage Backend)
        ("存储后端配置 (Storage Backend)", {
            'fields': ('storage_backend', 'aws_access_key_id', 'aws_secret_access_key',
                       'aws_storage_bucket_name', 'aws_s3_region_name', 'aws_s3_custom_domain')
        }),
    )

    def get_urls(self):
        """注册 PAT 认证测试的自定义 URL"""
        urls = super().get_urls()
        info = self.model._meta.app_label, self.model._meta.model_name
        custom_urls = [
            path('test-pat-token/', self.admin_site.admin_view(self.test_pat_token_view),
                 name='%s_%s_test_pat_token' % info),
        ]
        return custom_urls + urls

    def test_pat_token_view(self, request):
        """执行 PAT 认证测试的视图逻辑"""
        # 确保只处理 POST 或 GET 请求
        if request.method not in ['POST', 'GET']:
            # 重定向回单例模型的编辑页面
            obj_id = IntegrationSettings.get_solo().pk
            return redirect('admin:configuration_integrationsettings_change', object_id=obj_id)

        # 1. 实例化新的 PAT 服务
        service = LabelStudioPatService()
        success, result = service.get_user_info()

        # 2. 处理结果并显示消息
        obj_id = IntegrationSettings.get_solo().pk

        if success:
            messages.success(request,
                             f"PAT 认证成功！用户信息已获取：用户ID: {result.get('id')}, 邮箱: {result.get('email')}")
        else:
            error_msg = result.get('error', '未知错误')
            messages.error(request, f"PAT 认证失败！错误信息: {error_msg}")

        # 3. 重定向回 Admin 页面
        return redirect('admin:configuration_integrationsettings_change', object_id=obj_id)

@admin.register(EncodingProfile)
class EncodingProfileAdmin(ModelAdmin):
    list_display = ('name', 'is_default', 'container', 'modified')
    list_filter = ('is_default',) # 顺便也加一个过滤器
    search_fields = ('name', 'description')