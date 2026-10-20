import json
import logging
from decimal import Decimal
from typing import List, Dict, Any, Optional
from django.core.cache import cache
from django.db.models import Q, Sum, F, Case, When, Value, IntegerField, Prefetch
from django.utils import timezone
from .models import BrandDrug, DrugBatch, GenericDrug

logger = logging.getLogger(__name__)

TOP_DRUGS_CACHE_KEY_PREFIX = "pharma:top_drugs:"
DRUG_SEARCH_CACHE_TTL = 3600  # 1 Hour


class DrugSearchAndCacheService:
    """
    High-performance search service for 40,000+ pharmaceutical catalog.
    Executes fast indexed queries with exact match prioritization and FEFO batch resolution.
    """

    @classmethod
    def get_tenant_cache_key(cls, tenant_id: str) -> str:
        return f"{TOP_DRUGS_CACHE_KEY_PREFIX}{tenant_id}"

    @classmethod
    def prime_top_drugs_cache(cls, tenant_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        return []

    @classmethod
    def search_drugs(cls, query: str, tenant_id: str, limit: int = 15) -> List[Dict[str, Any]]:
        """
        High-performance search across 40,000+ Brand Drugs, Generics, Bengali names, and Barcodes.
        Optimized with Prefetch to resolve FEFO batches without N+1 query overhead.
        """
        query_clean = query.strip()
        today = timezone.now().date()

        # Tenant-aware batch filter
        batch_filter = Q(current_stock__gt=0)
        if tenant_id and tenant_id != "default_tenant":
            batch_filter &= (Q(tenant_id=tenant_id) | Q(tenant__isnull=True))

        fefo_prefetch = Prefetch(
            "batches",
            queryset=DrugBatch.objects.filter(batch_filter).order_by("expiry_date"),
            to_attr="prefetched_fefo_batches"
        )

        stock_filter = Q(batches__current_stock__gt=0, batches__expiry_date__gt=today)
        if tenant_id and tenant_id != "default_tenant":
            stock_filter &= (Q(batches__tenant_id=tenant_id) | Q(batches__tenant__isnull=True))

        if not query_clean:
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
            )

        results = []
        for drug in db_qs:
            batches = getattr(drug, "prefetched_fefo_batches", [])
            fefo_batch = next((b for b in batches if b.expiry_date and b.expiry_date > today), None)
            if not fefo_batch and batches:
                fefo_batch = batches[0]

            results.append({
                "id": str(drug.id),
                "brand_name": drug.brand_name,
                "brand_name_bn": drug.brand_name_bn or "",
                "generic_name": drug.generic.name,
                "generic_id": str(drug.generic.id),
                "strength": drug.strength,
                "dosage_form": drug.dosage_form.short_name or drug.dosage_form.name,
                "dosage_form_full": drug.dosage_form.name,
                "manufacturer": drug.manufacturer.name,
                "rack_location": drug.rack_location or "N/A",
                "unit_mrp": str(drug.unit_mrp),
                "unit_tp": str(drug.unit_tp),
                "vat_percent": str(drug.vat_percent),
                "total_stock": drug.available_stock or (fefo_batch.current_stock if fefo_batch else 0),
                "fefo_batch": {
                    "id": str(fefo_batch.id) if fefo_batch else None,
                    "batch_number": fefo_batch.batch_number if fefo_batch else "N/A",
                    "expiry_date": fefo_batch.expiry_date.strftime("%Y-%m-%d") if fefo_batch else "N/A",
                    "stock": fefo_batch.current_stock if fefo_batch else 0,
                } if fefo_batch else None
            })

        return results
