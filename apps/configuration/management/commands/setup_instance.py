# 文件路径: apps/configuration/management/commands/setup_instance.py

import os

from decouple import config
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.configuration.models import EncodingProfile, IntegrationSettings  # [修改] 导入 IntegrationSettings


class Command(BaseCommand):
    help = "Performs one-time initialization for a new Visify Story Studio instance."

    def add_arguments(self, parser: CommandParser):
        # [新增] 接受一个可选的 LS Token 参数
        parser.add_argument(
            "--ls-token", type=str, default=None, help="Label Studio API Token to be written to IntegrationSettings."
        )

        # [新增] Cloud API 相关参数
        parser.add_argument("--cloud-url", type=str, default=None, help="Cloud API Base URL")
        parser.add_argument("--cloud-id", type=str, default=None, help="Cloud Instance ID")
        parser.add_argument("--cloud-key", type=str, default=None, help="Cloud API Key")

    def handle(self, *args, **options):
        # ls_token_arg = options["ls_token"]
        self.stdout.write(self.style.SUCCESS("🚀 Starting Visify Story Studio instance setup..."))
        self._create_django_superuser()
        self._create_default_encoding_profile()
        self._update_integration_settings(options)
        # [核心修复] 将接收到的参数传递给方法
        # self._set_label_studio_token(ls_token_arg)
        self.stdout.write(self.style.SUCCESS("✅✅✅ Instance setup completed successfully! ✅✅✅"))
        self.stdout.write("You can now log in using the username and password you provided.")

    def _create_django_superuser(self):
        # ... (保持原有逻辑不变)
        self.stdout.write("🔑 Creating/updating local Django superuser...")
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL")
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")
        if not email or not password:
            raise CommandError("Error: DJANGO_SUPERUSER_EMAIL and DJANGO_SUPERUSER_PASSWORD must be set in .env file.")

        try:
            user, created = User.objects.update_or_create(
                username=email, defaults={"email": email, "is_staff": True, "is_superuser": True}
            )
            user.email = email
            user.is_staff = True
            user.is_superuser = True
            user.set_password(password)
            user.save()

            if created:
                self.stdout.write(self.style.SUCCESS(f"Local Django superuser '{email}' created."))
            else:
                self.stdout.write(
                    self.style.WARNING(f"Local Django superuser '{email}' already existed, password has been reset.")
                )
        except Exception as e:
            raise CommandError(f"Error creating/updating local Django superuser: {e}")

    def _update_integration_settings(self, options):
        """
        [重构] 统一更新 IntegrationSettings 单例模型。
        包含 Label Studio Token 和 Cloud API 配置。
        """
        self.stdout.write("⚙️  Configuring Integration Settings...")

        ls_token = options.get("ls_token")
        cloud_url = options.get("cloud_url")
        cloud_id = options.get("cloud_id")
        cloud_key = options.get("cloud_key")

        try:
            # 1. 获取单例对象 (使用原子锁 get_or_create(pk=1))
            settings_obj, created = IntegrationSettings.objects.get_or_create(pk=1, defaults={})

            update_fields = []

            # 2. 处理 Label Studio Token
            if ls_token and ls_token != "Manual_Setup_Required":
                settings_obj.label_studio_access_token = ls_token
                update_fields.append("label_studio_access_token")
                self.stdout.write(f"- Label Studio Token set (starts with {ls_token[:5]}...)")
            elif ls_token == "Manual_Setup_Required":
                self.stdout.write(self.style.WARNING("- Label Studio Token skipped (Manual setup required)."))

            # 3. [新增] 处理 Cloud API 配置
            # 只有当参数不为空时才更新
            if cloud_url:
                # 简单的清洗，去除末尾斜杠防止 404
                clean_url = cloud_url.strip().rstrip("/")
                settings_obj.cloud_api_base_url = clean_url
                update_fields.append("cloud_api_base_url")
                self.stdout.write(f"- Cloud URL set to: {clean_url}")

            if cloud_id:
                settings_obj.cloud_instance_id = cloud_id.strip()
                update_fields.append("cloud_instance_id")
                self.stdout.write("- Cloud Instance ID set.")

            if cloud_key:
                settings_obj.cloud_api_key = cloud_key.strip()
                update_fields.append("cloud_api_key")
                self.stdout.write("- Cloud API Key set.")

            # 4. 保存变更
            if update_fields:
                settings_obj.save(update_fields=update_fields)
                self.stdout.write(self.style.SUCCESS("✅ Integration Settings updated in database."))
            else:
                self.stdout.write("   - No changes made to Integration Settings.")

        except Exception as e:
            raise CommandError(f"CRASH ERROR: Fatal exception during integration settings update: {e}")

    def _create_default_encoding_profile(self):
        # ... (保持原有逻辑不变)
        self.stdout.write("🎞️ Creating default Encoding Profile for Annotation...")

        name = config("DEFAULT_ENCODING_NAME", "H.264 720p (1Mbps UltraFast)")
        cmd = config("DEFAULT_FFMPEG_CMD", "-c:v libx264 -b:v 1M -vf scale=-2:720 -preset ultrafast")

        if EncodingProfile.objects.filter(is_default=True, name=name).exists():
            self.stdout.write(
                self.style.WARNING("Default Encoding Profile already exists with desired name. Skipping creation.")
            )
            return

        profile, created = EncodingProfile.objects.update_or_create(
            name=name,
            defaults={
                "description": "Automatically generated optimized profile for fast annotation viewing (720p/1Mbps).",
                "container": "mp4",
                "ffmpeg_command": cmd,
                "is_default": True,
            },
        )

        if created:
            self.stdout.write(self.style.SUCCESS(f"Created default Encoding Profile: '{name}'."))
        else:
            self.stdout.write(self.style.WARNING(f"Updated existing Encoding Profile: '{name}' to be the default."))

    def _set_label_studio_token(self, ls_token: str):
        """
        [最终健壮性修复] 使用原子化的 get_or_create(pk=1) 模式，并添加强制 Checkpoint。
        """
        self.stdout.write("🔑 Setting up Label Studio API Token...")

        # 1. [检查点 1] 打印 Token 状态
        self.stdout.write(
            self.style.NOTICE(
                f"DEBUG: Checkpoint 1: LS_TOKEN received (first 10 chars): {ls_token[:10] if ls_token else 'None'}"
            )
        )

        # 2. 检查占位符
        if not ls_token or ls_token == "Manual_Setup_Required":
            self.stdout.write(self.style.WARNING("Warning: LABEL_STUDIO_ACCESS_TOKEN 缺失或需要手动设置。跳过 LS token 写入。"))
            return

        # 3. [检查点 2] 尝试 ORM 操作
        try:
            self.stdout.write(self.style.NOTICE("DEBUG: Checkpoint 2: Starting atomic ORM get_or_create(pk=1)."))

            # 使用 get_or_create 和 pk=1 确保实例存在
            settings_obj, created = IntegrationSettings.objects.get_or_create(
                pk=1, defaults={}  # 强制在主键 1 上操作  # 允许使用字段默认值
            )

            if created:
                self.stdout.write(self.style.WARNING("DEBUG: IntegrationSettings 实例被显式创建。"))

            self.stdout.write(
                self.style.NOTICE("DEBUG: Checkpoint 3: IntegrationSettings instance successfully obtained.")
            )

            # 4. 写入并保存 Token
            settings_obj.label_studio_access_token = ls_token
            # 强制保存 Token，只更新这一个字段
            settings_obj.save(update_fields=["label_studio_access_token"])

            # 5. [检查点 4] 验证并打印成功
            re_read_token = IntegrationSettings.objects.get(pk=1).label_studio_access_token
            self.stdout.write(
                self.style.NOTICE(
                    f"DEBUG: Token successfully saved to DB (first 10 chars): {re_read_token[:10] if re_read_token else 'Failed'}"  # noqa: E501
                )
            )

            self.stdout.write(self.style.SUCCESS("Successfully set Label Studio API Token in IntegrationSettings."))
        except Exception as e:
            # 强制记录内部异常
            raise CommandError(f"CRASH ERROR: Fatal exception during token write: {e}")
