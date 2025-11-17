# 文件路径: apps/configuration/management/commands/setup_instance.py

import os
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from decouple import config  # [新增] 导入 config
from apps.configuration.models import EncodingProfile  # [新增] 导入 EncodingProfile


class Command(BaseCommand):
    help = 'Performs one-time initialization for a new Visify Story Studio instance.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("🚀 Starting Visify Story Studio instance setup..."))
        self._create_django_superuser()
        self._create_default_encoding_profile()  # [新增步骤]
        self.stdout.write(self.style.SUCCESS("✅✅✅ Instance setup completed successfully! ✅✅✅"))
        self.stdout.write("You can now log in using the username and password you provided.")

    def _create_django_superuser(self):
        self.stdout.write("🔑 Creating/updating local Django superuser...")
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
        if not email or not password:
            raise CommandError("Error: DJANGO_SUPERUSER_EMAIL and DJANGO_SUPERUSER_PASSWORD must be set in .env file.")

        try:
            user, created = User.objects.update_or_create(
                username=email,
                defaults={'email': email, 'is_staff': True, 'is_superuser': True}
            )
            user.set_password(password)
            user.save()

            if created:
                self.stdout.write(self.style.SUCCESS(f"Local Django superuser '{email}' created."))
            else:
                self.stdout.write(
                    self.style.WARNING(f"Local Django superuser '{email}' already existed, password has been reset."))
        except Exception as e:
            raise CommandError(f"Error creating/updating local Django superuser: {e}")

    def _create_default_encoding_profile(self):
        """
        根据 .env 配置创建或更新默认的转码配置，用于加速标注。
        """
        self.stdout.write("🎞️ Creating default Encoding Profile for Annotation...")

        # 从 .env 读取配置，提供 fallback 值
        name = config('DEFAULT_ENCODING_NAME', 'H.264 720p (1Mbps UltraFast)')
        cmd = config('DEFAULT_FFMPEG_CMD', '-c:v libx264 -b:v 1M -vf scale=-2:720 -preset ultrafast')

        if EncodingProfile.objects.filter(is_default=True, name=name).exists():
            self.stdout.write(
                self.style.WARNING("Default Encoding Profile already exists with desired name. Skipping creation."))
            return

        # 如果存在其他默认 profile，Django 模型保存逻辑会自动处理 is_default=True 的唯一性。

        profile, created = EncodingProfile.objects.update_or_create(
            name=name,
            defaults={
                'description': 'Automatically generated optimized profile for fast annotation viewing (720p/1Mbps).',
                'container': 'mp4',
                'ffmpeg_command': cmd,
                'is_default': True
            }
        )

        if created:
            self.stdout.write(self.style.SUCCESS(f"Created default Encoding Profile: '{name}'."))
        else:
            # 这种情况通常发生在用户手动删除了 is_default 标记但保留了 profile name 时
            self.stdout.write(self.style.WARNING(f"Updated existing Encoding Profile: '{name}' to be the default."))