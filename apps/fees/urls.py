from django.urls import path

from . import views

app_name = "fees"

urlpatterns = [
    path("", views.index, name="index"),
    path("my/", views.my_dues, name="my_dues"),
    path(
        "allocations/<int:allocation_id>/payments/",
        views.payment,
        name="payment",
    ),
    path(
        "payments/<str:receipt_no>/receipt.pdf",
        views.receipt,
        name="receipt",
    ),
    path(
        "provisional-unpaid/",
        views.provisional_unpaid,
        name="provisional_unpaid",
    ),
]
