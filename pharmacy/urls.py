from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("login/", auth_views.LoginView.as_view(template_name="pharmacy/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("pos/", views.pos, name="pos"),
    path("pos/search/", views.pos_search, name="pos_search"),
    path("pos/cart/add/", views.cart_add, name="cart_add"),
    path("pos/cart/discount/", views.cart_discount, name="cart_discount"),
    path("pos/cart/remove/<str:medicine_id>/", views.cart_remove, name="cart_remove"),
    path("pos/checkout/", views.checkout_view, name="checkout"),
    path("sales/<uuid:sale_id>/receipt/", views.receipt, name="receipt"),
    path("customers/due/collect/", views.due_collect, name="due_collect"),
    path("customers/due/<str:phone>/", views.customer_due, name="customer_due"),
]
