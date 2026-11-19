from django.contrib import admin

from windows.models import Agreement, CollectionWindow


class AgreementInline(admin.StackedInline):
    model = Agreement
    extra = 0


@admin.register(CollectionWindow)
class CollectionWindowAdmin(admin.ModelAdmin):
    list_display = ("generator", "scheduled_date", "scheduled_time", "status", "materials")
    list_filter = ("status",)
    inlines = [AgreementInline]


@admin.register(Agreement)
class AgreementAdmin(admin.ModelAdmin):
    list_display = ("window", "collector", "confirmed_at")
