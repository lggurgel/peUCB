from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from accounts.models import Profile, User


class ProfileInline(admin.StackedInline):
    model = Profile
    extra = 0


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ("email",)
    list_display = ("email", "is_staff")
    search_fields = ("email",)
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
    )
    add_fieldsets = ((None, {"fields": ("email", "password1", "password2")}),)
    inlines = [ProfileInline]


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("public_name", "role", "user")
    list_filter = ("role", "collector_kind")
    search_fields = ("display_name", "organization_name", "user__email")
