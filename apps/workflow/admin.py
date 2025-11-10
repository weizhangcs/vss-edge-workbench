# -----------------------------------------------------------------------------
# [WORKFLOW ADMIN REGISTRY]
# -----------------------------------------------------------------------------
# This file acts as a central registry for all admin interfaces related to
# the workflow app. It ensures that Django's admin autodiscover mechanism
# finds and registers all separated admin classes.
#
# To add a new admin module, simply import it here.
# -----------------------------------------------------------------------------

# 文件路径: apps/workflow/admin.py

# --- 从新的 transcoding 子包导入 ---
from .transcoding.admin import *

# --- 从新的 annotation 子包导入 ---
from .annotation.admin import *

# --- 从新的 delivery 子包导入 ---
from .delivery.admin import *

# --- 从新的 inference 子包导入 ---
from .inference.admin import *