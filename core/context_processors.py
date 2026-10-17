from core.models import PlatformSetting

def platform_settings(request):
    """
    Exposes platform branding (logo, name, tagline) across all templates.
    """
    try:
        settings_obj = PlatformSetting.get_settings()
    except Exception:
        settings_obj = None
    return {
        "platform_settings": settings_obj,
    }

