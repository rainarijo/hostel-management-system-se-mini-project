from django.urls import path

from . import views

app_name = "fees"

urlpatterns = [
    path("", views.index, name="index"),
    path("my/", views.my_dues, name="my_dues"),
]
