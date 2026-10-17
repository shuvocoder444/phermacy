import re
with open("pos/voice_service.py", "r", encoding="utf-8") as f:
    code = f.read()

new_logic = """        import difflib
        from django.core.cache import cache
        all_brands = cache.get("all_active_brand_names")
        if not all_brands:
            all_brands = list(BrandDrug.objects.filter(is_active=True).values_list("brand_name", flat=True))
            cache.set("all_active_brand_names", all_brands, 3600)
        
        all_brands_lower = {b.lower(): b for b in all_brands if b}
        matches_lower = difflib.get_close_matches(first_word.lower(), list(all_brands_lower.keys()), n=1, cutoff=0.5)
        matches = [all_brands_lower[m] for m in matches_lower]
        db_drug = None"""

code = re.sub(
    r"import difflib.*?db_drug = None",
    new_logic,
    code,
    flags=re.DOTALL
)

with open("pos/voice_service.py", "w", encoding="utf-8") as f:
    f.write(code)

