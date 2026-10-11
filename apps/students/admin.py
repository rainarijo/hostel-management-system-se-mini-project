from django.contrib import admin

from .models import MasterStudent, StudentProfile


@admin.register(MasterStudent)
class MasterStudentAdmin(admin.ModelAdmin):
    list_display = ("srn", "name", "gender", "program", "year", "email")
    search_fields = ("srn", "name", "email")


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ("srn", "name", "gender", "year", "mobile", "priority_flag")
    list_filter = ("gender", "year", "priority_flag")
    search_fields = ("srn", "name")
