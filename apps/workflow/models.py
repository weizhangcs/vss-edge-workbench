# jobs/models.py

# --- 从新的 transcoding 子包导入 ---
from .transcoding.projects import TranscodingProject
from .transcoding.jobs import TranscodingJob

# --- 从 annotation 子包导入 ---
from .annotation.projects import AnnotationProject
from .annotation.jobs import AnnotationJob

# --- 从新的 delivery 子包导入 ---
from .delivery.jobs import DeliveryJob