from django import template

from windows.models import KIND_LABELS, MATERIAL_LABELS, STATUS_LABELS

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
