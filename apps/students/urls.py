from django.urls import path

from . import views

app_name = "students"

urlpatterns = [
    path("", views.index, name="index"),
    path(
        "profile/<int:profile_id>/",
        views.profile_detail,
        name="profile_detail",
    ),
    path(
        "profile/<int:profile_id>/edit/",
        views.profile_edit,
        name="profile_edit",
    ),
]
