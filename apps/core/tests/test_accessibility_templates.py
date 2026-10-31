from pathlib import Path
import re
import unittest

from django.conf import settings


TEMPLATE_ROOT = Path(settings.BASE_DIR) / "templates"


def template_files():
    return sorted(TEMPLATE_ROOT.rglob("*.html"))


class AccessibilityTemplateTests(unittest.TestCase):
    def test_shared_base_has_skip_link_and_main_landmark(self):
        html = (TEMPLATE_ROOT / "base.html").read_text(encoding="utf-8")
        self.assertIn('href="#main-content"', html)
        self.assertIn('id="main-content"', html)
        self.assertIn('aria-label="Primary navigation"', html)

    def test_images_have_text_alternatives(self):
        for path in template_files():
            html = path.read_text(encoding="utf-8")
            for tag in re.findall(r"<img\b[^>]*>", html, flags=re.IGNORECASE):
                self.assertRegex(
                    tag,
                    r"\balt\s*=\s*[\"'][^\"']*[\"']",
                    msg=f"Image without alt text: {path}",
                )

    def test_tables_have_captions_and_column_scopes(self):
        for path in template_files():
            html = path.read_text(encoding="utf-8")
            for table in re.findall(
                r"<table\b.*?</table>", html, flags=re.IGNORECASE | re.DOTALL
            ):
                self.assertRegex(
                    table,
                    r"<caption\b[^>]*>",
                    msg=f"Table without caption: {path}",
                )
                for th in re.findall(r"<th\b[^>]*>", table, flags=re.IGNORECASE):
                    self.assertRegex(
                        th,
                        r"\bscope\s*=\s*[\"'](?:col|row)[\"']",
                        msg=f"Table header without scope: {path}: {th}",
                    )

    def test_alerts_are_announced(self):
        for path in template_files():
            html = path.read_text(encoding="utf-8")
            for alert in re.findall(
                r"<[^>]*class=[\"'][^\"']*\balert\b[^\"']*[\"'][^>]*>",
                html,
            ):
                self.assertRegex(
                    alert,
                    r"\brole\s*=\s*[\"'](?:alert|status)[\"']",
                    msg=f"Alert without an announcement role: {path}: {alert}",
                )

    def test_destructive_actions_do_not_use_inline_confirm_or_placeholder_links(self):
        for path in template_files():
            html = path.read_text(encoding="utf-8")
            self.assertNotRegex(
                html,
                r"\bonclick\s*=",
                msg=f"Inline JavaScript handler found: {path}",
            )
            self.assertNotRegex(
                html,
                r"href\s*=\s*[\"']#[\"']",
                msg=f"Placeholder link found: {path}",
            )

    def test_auto_rendered_forms_are_not_used(self):
        for path in template_files():
            html = path.read_text(encoding="utf-8")
            self.assertNotIn(
                "{{ form.as_p }}",
                html,
                msg=f"Uncontrolled form.as_p rendering found: {path}",
            )

    def test_bootstrap_modals_have_accessible_names(self):
        for path in template_files():
            html = path.read_text(encoding="utf-8")
            if 'class="modal' not in html:
                continue
            self.assertIn("aria-labelledby=", html, msg=f"Modal lacks name: {path}")
            self.assertIn('tabindex="-1"', html, msg=f"Modal lacks keyboard entry: {path}")
            self.assertIn('class="btn-close"', html, msg=f"Modal lacks close control: {path}")
