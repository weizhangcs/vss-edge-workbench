# 文件路径: apps/media_assets/views.py

from pathlib import Path

from django.conf import settings
from django.contrib import admin, messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from .models import Asset
from .tasks import ingest_media_files


@login_required
def batch_file_upload_view(request, asset_id):
    if request.method == "POST":
        try:
            asset = Asset.objects.get(id=asset_id)
            upload_dir = Path(settings.MEDIA_ROOT) / "batch_uploads" / str(asset.id)
            upload_dir.mkdir(parents=True, exist_ok=True)
            uploaded_file = request.FILES.get("file")
            if not uploaded_file:
                return JsonResponse({"status": "error", "message": "No file provided"}, status=400)
            file_path = upload_dir / uploaded_file.name
            with open(file_path, "wb+") as fp:
                for chunk in uploaded_file.chunks():
                    fp.write(chunk)
            return JsonResponse({"status": "success", "message": f"File {uploaded_file.name} uploaded successfully"})
        except Asset.DoesNotExist:
            return JsonResponse({"status": "error", "message": "Asset not found"}, status=404)
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=500)
    return JsonResponse({"status": "error", "message": "Only POST method is allowed"}, status=405)


@login_required
def batch_upload_page_view(request, asset_id):
    try:
        asset = Asset.objects.get(id=asset_id)
        context = {
            # --- 核心修复：模板需要一个名为 'media' 的变量 ---
            "media": asset,
            "opts": Asset._meta,
            "site_header": admin.site.site_header,
            "site_title": admin.site.site_title,
            "show_save": False,
            "show_save_and_continue": False,
            "show_save_and_add_another": False,
            "show_delete": False,
            "has_permission": True,
        }
        return render(request, "admin/media_assets/media/batch_upload.html", context)
    except Asset.DoesNotExist:
        raise Http404("Asset not found")


@login_required
def trigger_ingest_task(request, asset_id):  # <-- 参数改为 asset_id
    """
    (V4 命名修正版)
    这个视图专门用于从前端接收信号，为指定的 Asset 启动批处理任务。
    """
    # --- 核心修复：使用 Asset 模型 ---
    asset = get_object_or_404(Asset, pk=asset_id)

    # 触发核心的 Celery 任务，并传递正确的 asset.id
    ingest_media_files.delay(str(asset.id))

    # 向用户显示成功消息
    messages.success(request, f"已成功为《{asset.title}》启动后台文件处理任务，请稍后刷新查看状态。")

    # [核心修复] 重定向回列表页，而不是详情页
    return redirect("admin:media_assets_asset_changelist")
