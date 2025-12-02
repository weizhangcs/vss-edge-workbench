# apps/workflow/creative/views.py

import json
import logging
import time

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt

from .models import CreativeProject
from .services.orchestrator import CreativeOrchestrator

logger = logging.getLogger(__name__)


# [入口 1] 导演模式配置页
def launch_director_view(request, project_id):
    project = get_object_or_404(CreativeProject, id=project_id)

    assets = {
        "source_language": project.asset.language if project.asset else "zh-CN",
        "narration": {"exists": bool(project.narration_script_file), "name": str(project.narration_script_file)},
        "localize": {"exists": bool(project.localized_script_file), "name": str(project.localized_script_file)},
        "audio": {"exists": bool(project.dubbing_script_file), "name": str(project.dubbing_script_file)},
    }

    context = {
        "title": f"导演驾驶舱 - {project.name}",
        "server_data_json": json.dumps(
            {
                "project_id": str(project.id),
                "project_name": project.name,
                "assets": assets,
                "initial_config": project.auto_config or {},
            },
            ensure_ascii=False,
        ),
    }
    return render(request, "admin/workflow/creative/director.html", context)


# [入口 2] 提交接口 (Renamed: submit_pipeline_view)
@csrf_exempt
def submit_pipeline_view(request, project_id):
    project = get_object_or_404(CreativeProject, id=project_id)
    try:
        data = json.loads(request.body)
        strategy_config = data.get("config")

        if not project.inference_project:
            return JsonResponse({"status": "error", "message": "关联的推理项目不存在"}, status=400)

        orchestrator = CreativeOrchestrator(str(project.inference_project.id))

        # 3. 调用编排
        new_project = orchestrator.create_pipeline_from_strategy(  # [修改] 返回值变了
            count=1, strategy=strategy_config, source_creative_project_id=str(project.id)
        )

        # 智能跳转到 Monitor
        redirect_url = reverse("admin:workflow_creativeproject_tab_monitor", args=[new_project.id])

        return JsonResponse(
            {
                "status": "success",
                "message": "管线任务已启动",
                "redirect_url": redirect_url,
            }
        )

    except Exception as e:
        logger.exception("Pipeline Submit Error")
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


# [入口 3] Debug 接口 (Renamed: debug_pipeline_view)
@csrf_exempt
def debug_pipeline_view(request, project_id):
    project = get_object_or_404(CreativeProject, id=project_id)
    try:
        data = json.loads(request.body)
        strategy_config = data.get("config")

        orchestrator = CreativeOrchestrator(str(project.inference_project.id))

        # [调用] preview_pipeline_creation
        debug_results = orchestrator.preview_pipeline_creation(count=1, strategy=strategy_config)

        # 生成临时文件
        timestamp = int(time.time())
        file_name = f"debug/pipeline_preview_{project.id}_{timestamp}.json"
        file_content = json.dumps(debug_results, indent=2, ensure_ascii=False)
        saved_path = default_storage.save(file_name, ContentFile(file_content.encode("utf-8")))
        file_url = default_storage.url(saved_path)

        return JsonResponse(
            {
                "status": "success",
                "message": "Debug 完成！",
                "debug_data": debug_results,
                "download_url": file_url,
            }
        )

    except Exception as e:
        logger.exception("Pipeline Debug Error")
        return JsonResponse({"status": "error", "message": str(e)}, status=500)
