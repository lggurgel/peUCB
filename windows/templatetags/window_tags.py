from django import template
from django.utils.html import format_html

from windows.models import KIND_LABELS, MATERIAL_LABELS, STATUS_LABELS
from windows.queries import format_wait

register = template.Library()


@register.filter
def material_label(code):
    return MATERIAL_LABELS.get(code, code)


@register.filter
def status_label(code):
    return STATUS_LABELS.get(code, code)


@register.filter
def kind_label(code):
    return KIND_LABELS.get(code, code)


@register.filter
def wait(delta):
    return format_wait(delta)


@register.filter
def initials(name):
    return "".join(part[0] for part in str(name).split()[:2]).upper()


@register.simple_tag
def icon(name):
    """One icon from the sprite in templates/_icons.html."""
    return format_html('<svg class="i" aria-hidden="true"><use href="#i-{}"/></svg>', name)
