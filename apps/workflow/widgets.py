# 文件路径: apps/workflow/widgets.py

from django.utils.safestring import mark_safe
from unfold.widgets import UnfoldAdminFileFieldWidget
from django.template.loader import render_to_string


class FileFieldWithActionButtonWidget(UnfoldAdminFileFieldWidget):
    def __init__(self, attrs=None, button_url=None, button_text=None, button_variant="primary",
                 secondary_button_url=None, secondary_button_text=None, secondary_button_variant="default"):
        super().__init__(attrs)
        #
        self.button_url = button_url
        self.button_text = button_text
        self.button_variant = button_variant
        #
        self.secondary_button_url = secondary_button_url
        self.secondary_button_text = secondary_button_text
        self.secondary_button_variant = secondary_button_variant

    def render(self, name, value, attrs=None, renderer=None):
        file_input_html = super().render(name, value, attrs, renderer)

        #
        button_html = ""
        if self.button_url and self.button_text:
            button_context = {
                "href": self.button_url,
                "content": self.button_text,
                "variant": self.button_variant,
                "attrs": {"class": "ml-2"}
            }
            button_html = render_to_string("admin/components/_action_button.html", button_context)

        #
        secondary_button_html = ""
        if self.secondary_button_url and self.secondary_button_text:
            secondary_button_context = {
                "href": self.secondary_button_url,
                "content": self.secondary_button_text,
                "variant": self.secondary_button_variant,
                "attrs": {"class": "ml-2 js-cloud-trigger-btn"}  # <--- 在这里添加 class
            }
            secondary_button_html = render_to_string("admin/components/_action_button.html", secondary_button_context)

        #
        return mark_safe(f'<div class="flex items-center">{file_input_html}{button_html}{secondary_button_html}</div>')