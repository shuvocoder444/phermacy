from django.urls import path

from . import views

app_name = "inventory"

urlpatterns = [
    path("", views.stock_dashboard, name="dashboard"),
    path("add-batch/", views.add_batch_view, name="add_batch"),
    path("batch/<uuid:batch_id>/edit/", views.edit_batch_view, name="edit_batch"),
    path("batch/<uuid:batch_id>/delete/", views.delete_batch_view, name="delete_batch"),
    path("export/csv/", views.export_stock_csv_view, name="export_stock_csv"),
    path("sample/csv/", views.download_sample_stock_csv_view, name="sample_stock_csv"),
    path("import/csv/", views.import_stock_csv_view, name="import_stock_csv"),
    path("autocomplete/", views.drug_autocomplete_view, name="autocomplete"),
    path("batch/<uuid:batch_id>/movements/", views.stock_movement_history, name="movements"),
]
