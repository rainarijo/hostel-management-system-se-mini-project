from django.urls import path

from . import views

app_name = "allocation"

urlpatterns = [
    path("", views.index, name="index"),
]
