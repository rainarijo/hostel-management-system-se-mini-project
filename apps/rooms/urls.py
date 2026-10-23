from django.urls import path

from . import views

app_name = "rooms"

urlpatterns = [
    path("", views.index, name="index"),
    path("hostels/new/", views.hostel_create, name="hostel_create"),
    path("hostels/<int:pk>/edit/", views.hostel_edit, name="hostel_edit"),
    path("hostels/<int:pk>/deactivate/", views.hostel_deactivate, name="hostel_deactivate"),
    path("hostels/<int:pk>/reactivate/", views.hostel_reactivate, name="hostel_reactivate"),
    path("rooms/new/", views.room_create, name="room_create"),
    path("rooms/<int:pk>/edit/", views.room_edit, name="room_edit"),
    path("rooms/<int:pk>/deactivate/", views.room_deactivate, name="room_deactivate"),
    path("rooms/<int:pk>/reactivate/", views.room_reactivate, name="room_reactivate"),
]
