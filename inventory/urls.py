from django.urls import path
from . import views

app_name = "inventory"

urlpatterns = [
    path("", views.stock_dashboard, name="dashboard"),
    path("add-batch/", views.add_batch_view, name="add_batch"),
    path("batch/<uuid:batch_id>/movements/", views.stock_movement_history, name="movements"),
]

