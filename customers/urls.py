from django.urls import path
from . import views

app_name = "customers"

urlpatterns = [
    path("", views.customer_dashboard, name="dashboard"),
    path("add/", views.add_customer, name="add"),
    path("collect-due/<uuid:customer_id>/", views.collect_due, name="collect_due"),
    path("statement/<uuid:customer_id>/", views.customer_statement, name="statement"),
    path("api/search/", views.search_customers_api, name="api_search"),
]

