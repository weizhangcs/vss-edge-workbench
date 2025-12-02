# 文件路径: apps/media_assets/storage_backends.py

from django.conf import settings
from django.core.files.storage import FileSystemStorage


class EdgeLocalStorage(FileSystemStorage):
    """
    [V6.0 全局存储适配器]
    继承原生文件存储，但强制 URL 指向 Nginx (9999) 端口。
    解决 Django Admin 中 FileField 默认指向 8000 端口导致 404 的问题。
    """

    def __init__(self, location=None, base_url=None):
        # 如果没有显式指定 base_url，则自动从 settings 拼接
        if base_url is None:
            # 逻辑: http://IP:9999 + /media/
            # 结果: http://192.168.1.90:9999/media/
            base_url = f"{settings.LOCAL_MEDIA_URL_BASE.rstrip('/')}{settings.MEDIA_URL}"

        super().__init__(location, base_url)
