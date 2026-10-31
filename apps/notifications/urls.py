from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("", views.index, name="index"),
    path("announcements/post/", views.post_announcement, name="post_announcement"),
]
