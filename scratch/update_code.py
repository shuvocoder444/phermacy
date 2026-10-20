# Update inventory/services.py and pos/views.py

with open('inventory/services.py', 'r', encoding='utf-8') as f:
    services_text = f.read()

target_services = """        if not query_clean:
            popular_names = ["Napa", "Sergel", "Maxpro", "Seclo", "Monas", "Fexo", "Ace", "Cef-3", "Zimax", "Bislol"]
            db_qs = (
                BrandDrug.objects.filter(brand_name__in=popular_names, is_active=True)
                .select_related("generic", "manufacturer", "dosage_form")
                .prefetch_related(fefo_prefetch)
                .annotate(
                    available_stock=Sum(
                        "batches__current_stock",
                        filter=stock_filter
                    )
                )[:limit]
            )
        else:
            db_qs = (
                BrandDrug.objects.filter(
                    Q(brand_name__icontains=query_clean)
                    | Q(generic__name__icontains=query_clean)
                    | Q(brand_name_bn__icontains=query_clean)
                    | Q(barcode__iexact=query_clean)
                    | Q(dosage_form__name__icontains=query_clean)
                    | Q(dosage_form__name_bn__icontains=query_clean),
                    is_active=True
                )
                .select_related("generic", "manufacturer", "dosage_form")
                .prefetch_related(fefo_prefetch)
                .annotate(
                    available_stock=Sum(
                        "batches__current_stock",
                        filter=stock_filter
                    ),
                    is_exact=Case(
                        When(brand_name__iexact=query_clean, then=Value(0)),
                        When(brand_name__istartswith=query_clean, then=Value(1)),
                        When(brand_name_bn__startswith=query_clean, then=Value(2)),
                        default=Value(3),
                        output_field=IntegerField(),
                    )
                )
                .order_by("is_exact", "brand_name")[:limit]
            )"""

replacement_services = """        tenant_stock_drug_ids = list(
            DrugBatch.objects.filter(batch_filter)
            .values_list("drug_id", flat=True)
            .distinct()
        )
        if not query_clean:
            popular_names = ["Napa", "Sergel", "Maxpro", "Seclo", "Monas", "Fexo", "Ace", "Cef-3", "Zimax", "Bislol"]
            empty_filter = Q(id__in=tenant_stock_drug_ids)
            if popular_names:
                empty_filter |= Q(brand_name__in=popular_names)

            db_qs = (
                BrandDrug.objects.filter(empty_filter, is_active=True)
                .select_related("generic", "manufacturer", "dosage_form")
                .prefetch_related(fefo_prefetch)
                .annotate(
                    is_in_stock=Case(
                        When(id__in=tenant_stock_drug_ids, then=Value(1)),
                        default=Value(0),
                        output_field=IntegerField(),
                    ),
                    available_stock=Sum(
                        "batches__current_stock",
                        filter=stock_filter
                    )
                )
                .order_by("-is_in_stock", "brand_name")[:limit]
            )
        else:
            db_qs = (
                BrandDrug.objects.filter(
                    Q(brand_name__icontains=query_clean)
                    | Q(generic__name__icontains=query_clean)
                    | Q(brand_name_bn__icontains=query_clean)
                    | Q(barcode__iexact=query_clean)
                    | Q(dosage_form__name__icontains=query_clean)
                    | Q(dosage_form__name_bn__icontains=query_clean),
                    is_active=True
                )
                .select_related("generic", "manufacturer", "dosage_form")
                .prefetch_related(fefo_prefetch)
                .annotate(
                    is_in_stock=Case(
                        When(id__in=tenant_stock_drug_ids, then=Value(1)),
                        default=Value(0),
                        output_field=IntegerField(),
                    ),
                    available_stock=Sum(
                        "batches__current_stock",
                        filter=stock_filter
                    ),
                    is_exact=Case(
                        When(brand_name__iexact=query_clean, then=Value(0)),
                        When(brand_name__istartswith=query_clean, then=Value(1)),
                        When(brand_name_bn__startswith=query_clean, then=Value(2)),
                        default=Value(3),
                        output_field=IntegerField(),
                    )
                )
                .order_by("-is_in_stock", "is_exact", "brand_name")[:limit]
            )"""

# Normalize \r\n to \n for replacement
norm_services = services_text.replace('\r\n', '\n')
assert target_services in norm_services, "target_services not found"
norm_services = norm_services.replace(target_services, replacement_services, 1)
with open('inventory/services.py', 'w', encoding='utf-8', newline='') as f:
    f.write(norm_services.replace('\n', '\r\n'))
print("Successfully updated inventory/services.py")

