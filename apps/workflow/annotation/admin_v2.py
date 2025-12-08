import uuid

from django.contrib import admin
from django.shortcuts import render
from django.urls import path, reverse
from django.utils.html import format_html
from unfold.admin import ModelAdmin
from unfold.decorators import display

# 引用代理模型
from apps.workflow.annotation.projects import AnnotationProjectV2

# 引用新定义的 Schema
from .schemas import DataOrigin, DialogueItem, MediaAnnotation, SceneItem, SceneMood


@admin.register(AnnotationProjectV2)
class AnnotationProjectAdminV2(ModelAdmin):
    """
    V2 版本的 Admin，完全独立于原 admin.py。
    专注于 Annotation Workbench 的集成测试。
    """

    # 1. 基础配置 (按需精简)
    list_display = ("name", "status", "created", "open_workbench_link")
    search_fields = ("name",)

    # 2. 自定义 URL (只挂载新功能的 View)
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "workbench-test/",
                self.admin_site.admin_view(self.workbench_test_view),
                name="workflow_annotationprojectv2_workbench_test",
            ),
        ]
        return custom_urls + urls

    # 3. 核心视图：Workbench 集成
    def workbench_test_view(self, request):
        # --- Mock 数据生成 (Schema 验证) ---
        # [修改点] 将 source_path 指向您刚才测试成功的真实 URL 路径
        # 注意：这里使用的是相对路径或绝对 URL 均可，取决于前端如何处理
        # 假设您的 Nginx 映射了 /media/ -> media_root

        # 使用您之前验证过的真实视频路径
        real_video_path = "http://localhost:9999/media/transcoding_outputs/5124d170-c299-4d58-8447-abdaac2af5aa/158.mp4"

        mock_annotation = MediaAnnotation(
            media_id=str(uuid.uuid4()),
            file_name="158.mp4",
            source_path=real_video_path,  # <--- [关键修复] 这里不再用假路径
            duration=120.0,
            scenes=[
                SceneItem(
                    id=str(uuid.uuid4()),
                    start=0.0,
                    end=10.0,
                    label="V2测试场景：开端",
                    mood=SceneMood.MYSTERIOUS,
                    origin=DataOrigin.HUMAN,
                )
            ],
            dialogues=[
                DialogueItem(id=str(uuid.uuid4()), start=1.0, end=5.0, text="这是 V2 Admin 的测试数据。", speaker="系统"),
                DialogueItem(
                    id=str(uuid.uuid4()),
                    start=5.5,
                    end=9.0,
                    text="数据通过 Pydantic Schema 生成。",
                    speaker="开发者",
                    origin=DataOrigin.AI_LLM,
                    ai_meta={"confidence": 0.99},
                ),
            ],
        )

        # 序列化
        server_data_json = mock_annotation.model_dump_json()

        context = {
            **self.admin_site.each_context(request),
            "title": "标注工作台 (V2 独立环境)",
            "server_data_json": server_data_json,
            # 如果需要返回按钮，可以加一个
            "opts": self.model._meta,
        }
        return render(request, "admin/workflow/project/annotation/workbench.html", context)

    # 4. 列表页快捷入口
    # [新增] 专门用于 list_display 的方法
    @display(description="操作", label="进入工作台")
    def open_workbench_link(self, obj):
        # 生成跳转链接
        url = reverse("admin:workflow_annotationprojectv2_workbench_test")
        # 渲染为按钮样式
        return format_html('<a href="{}" class="button" target="_blank">打开工作台</a>', url)
