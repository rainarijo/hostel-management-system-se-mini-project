from django.urls import path

from . import views

app_name = "complaints"

urlpatterns = [
    path("", views.index, name="index"),
    path(
        "<str:complaint_no>/status/",
        views.change_complaint_status,
        name="change_status",
    ),
    path(
        "<str:complaint_no>/reopen/",
        views.reopen,
        name="reopen",
    ),
]
