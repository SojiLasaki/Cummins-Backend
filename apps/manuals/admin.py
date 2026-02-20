from django.contrib import admin
from .models import Manual, Tag

# # --- Component Admin ---
# @admin.register(Component)
# class ComponentAdmin(admin.ModelAdmin):
#     list_display = ("name", "parent")
#     search_fields = ("name",)

# --- Tag Admin ---
@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)

# --- Manual Admin ---
@admin.register(Manual)
class ManualAdmin(admin.ModelAdmin):
    list_display = ("title", "version", "created_at")
    list_filter = ("component", "tags")  # <-- add tags as a filter
    search_fields = ("title", "content")
    filter_horizontal = ("tags",)  # <-- makes tag selection easier in the admin form