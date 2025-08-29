# -----------------------------------------------------------------------------
# [WORKFLOW ADMIN REGISTRY]
# -----------------------------------------------------------------------------
# This file acts as a central registry for all admin interfaces related to
# the workflow app. It ensures that Django's admin autodiscover mechanism
# finds and registers all separated admin classes.
#
# To add a new admin module, simply import it here.
# -----------------------------------------------------------------------------

from .admin_configs.annotationAdmin import *
from .admin_configs.transcodingAdmin import *