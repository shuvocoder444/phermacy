from django.urls import path
from . import views
from . import voice_service
from . import ocr_service

app_name = "pos"

urlpatterns = [
    path("", views.pos_screen_view, name="screen"),
    path("", views.pos_screen_view, name="pos_screen"),
    path("search/", views.drug_search_htmx, name="search"),
    path("cart/add/", views.cart_add_htmx, name="cart_add"),
    path("cart/update/", views.cart_update_quantity_htmx, name="cart_update"),
    path("cart/remove/", views.cart_remove_item_htmx, name="cart_remove"),
    path("cart/discount/", views.cart_apply_discount_htmx, name="cart_discount"),
    path("cart/clear/", views.cart_clear_htmx, name="cart_clear"),
    path("cart/hold/", views.hold_cart_htmx, name="hold_cart"),
    path("cart/held-list/", views.held_carts_modal, name="held_carts"),
    path("cart/resume/<str:hold_id>/", views.resume_cart_htmx, name="resume_cart"),
    path("checkout/modal/", views.checkout_modal_htmx, name="checkout_modal"),
    path("checkout/submit/", views.checkout_submit_htmx, name="checkout_submit"),
    path("receipt/<uuid:invoice_id>/print/", views.print_thermal_receipt, name="print_receipt"),
    path("recent-invoices/", views.recent_invoices_modal, name="recent_invoices"),
    # Voice Dispensing Endpoint
    path("voice/add/", voice_service.voice_add_to_cart_htmx, name="voice_add"),
    path("voice/parse/", voice_service.voice_add_to_cart_htmx, name="voice_parse"),
    path("voice/search/", voice_service.voice_medicine_search, name="voice_medicine_search"),
    # Camera OCR Scan Endpoint
    path("camera/scan/", ocr_service.process_camera_scan_htmx, name="camera_scan"),
    path("ocr/scan/", ocr_service.scan_medicine_ocr, name="scan_medicine_ocr"),
    # Custom Medicine Instant Addition
    path("drug/add-custom/", views.add_custom_drug_and_batch_htmx, name="add_custom_drug"),
    # AI Medicine Training / Alias Mapping
    path("train/medicine/", views.train_medicine_alias_view, name="train_medicine"),
    # Multimodal AI Engine Configuration & Test
    path("ai/config/", views.ai_config_view, name="ai_config"),
    path("ai/test-connection/", views.test_gemini_connection_view, name="ai_test_connection"),
]
