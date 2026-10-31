from django import forms
from django import template
from django.utils.html import format_html

register = template.Library()


@register.simple_tag
def accessible_field(field):
    """Render a bound form field with consistent Bootstrap/error semantics."""
    widget = field.field.widget
    attrs = dict(widget.attrs)

    if isinstance(widget, (forms.Select, forms.SelectMultiple)):
        css_class = "form-select"
    elif isinstance(widget, forms.CheckboxInput):
        css_class = "form-check-input"
    else:
        css_class = "form-control"

    existing = attrs.get("class", "").strip()
    if css_class not in existing.split():
        attrs["class"] = f"{existing} {css_class}".strip()

    described_by = []
    if field.help_text:
        described_by.append(f"{field.auto_id}_help")
    if field.errors:
        described_by.append(f"{field.auto_id}_errors")
        attrs["aria-invalid"] = "true"

    if described_by:
        attrs["aria-describedby"] = " ".join(described_by)

    return format_html("{}", field.as_widget(attrs=attrs))
