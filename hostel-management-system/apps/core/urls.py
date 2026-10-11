from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("dashboard/student/", views.student_dashboard, name="student_dashboard"),
    path("dashboard/warden/", views.warden_dashboard, name="warden_dashboard"),
    path("dashboard/admin/", views.admin_dashboard, name="admin_dashboard"),
]
