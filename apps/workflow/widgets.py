# 文件路径: apps/workflow/widgets.py

from django.utils.safestring import mark_safe
from unfold.widgets import UnfoldAdminFileFieldWidget
from django.template.loader import render_to_string


class FileFieldWithActionButtonWidget(UnfoldAdminFileFieldWidget):
    def __init__(self, attrs=None, button_url=None, button_text=None, button_variant="primary"):
        super().__init__(attrs)
        self.button_url = button_url
        self.button_text = button_text
        self.button_variant = button_variant

    def render(self, name, value, attrs=None, renderer=None):
        file_input_html = super().render(name, value, attrs, renderer)

        button_html = ""
        if self.button_url and self.button_text:
            button_context = {
                "href": self.button_url,
                "content": self.button_text,
                "variant": self.button_variant,
                "attrs": {"class": "ml-2"}
            }
            # 调用并渲染我们自己的专用HTML代码段
            button_html = render_to_string("admin/components/_action_button.html", button_context)

        return mark_safe(f'<div class="flex items-center">{file_input_html}{button_html}</div>')