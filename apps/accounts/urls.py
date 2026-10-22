
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("register/", views.register_view, name="register"),
    path(
        "verify/<str:token>/",
        views.verify_email_view,
        name="verify_email",
    ),
    path(
        "password-reset/",
        views.password_reset_view,
        name="password_reset",
    ),
]
