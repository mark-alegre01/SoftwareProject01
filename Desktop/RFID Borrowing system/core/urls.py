from django.urls import path

from . import views


app_name = "core"


urlpatterns = [
    path("login", views.login_view, name="login"),
    path("register", views.register_view, name="register"),
    path("logout", views.logout_view, name="logout"),
    path("dashboard", views.dashboard, name="dashboard"),
    path("borrow", views.borrow_page, name="borrow"),
    path("return", views.return_page, name="return"),
    path("register-borrower", views.register_borrower_page, name="register-borrower"),
    path("register-item", views.register_item_page, name="register-item"),
]


