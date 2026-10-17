from django.urls import path
from . import ledger_views

app_name = "ledger"

urlpatterns = [
    path("", ledger_views.ledger_dashboard_view, name="dashboard"),
    path("add/", ledger_views.ledger_add_entry_htmx, name="add_entry"),
    path("delete/<uuid:entry_id>/", ledger_views.ledger_delete_entry_htmx, name="delete_entry"),
]

