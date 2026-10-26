
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
    path("manage/", views.account_list_view, name="account_list"),
    path("manage/create/", views.account_create_view, name="account_create"),
    path(
        "manage/<int:user_id>/role/",
        views.account_change_role_view,
        name="account_change_role",
    ),
    path(
        "manage/<int:user_id>/deactivate/",
        views.account_deactivate_view,
        name="account_deactivate",
    ),
    path(
    "password-reset/<str:token>/",
    views.password_reset_confirm_view,
    name="password_reset_confirm",
),
]
