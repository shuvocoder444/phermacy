from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from django.core.cache import cache
from django.db.models import Q

from inventory.models import BrandDrug
from pos.models import MedicineAlias
from pos.utils import (
    COMMON_BN_MEDICINE_ALIASES,
    compute_metaphone,
    compute_soundex,
    rank_phonetic_matches,
    transliterate_bangla_to_phonetic,
)

logger = logging.getLogger(__name__)

CACHE_KEY_TRAINED_ALIASES = "pos:trained_medicine_aliases:"


class DrugTrainingService:
    """
    Self-learning and training engine for PharmaFlow POS.
    Allows pharmacists to train custom voice pronunciations, regional medicine nicknames,
    and OCR packaging aliases that automatically map to DGDA catalog drugs.
    """

    @classmethod
    def load_trained_aliases(cls, tenant_id: str) -> Dict[str, str]:
        """Loads learned aliases from this pharmacy only."""
        cache_key = f"{CACHE_KEY_TRAINED_ALIASES}{tenant_id}"
        cached = cache.get(cache_key)
        if cached is not None and isinstance(cached, dict):
            return cached
        aliases = dict(MedicineAlias.objects.filter(tenant_id=tenant_id).values_list("alias", "brand_name"))
        cache.set(cache_key, aliases, 86400)
        return aliases

    @classmethod
    def save_trained_alias(cls, alias_phrase: str, brand_name: str, tenant_id: str) -> bool:
        """
        Saves a newly trained pronunciation or OCR alias mapping.
        Example: 'লাল নাপা' -> 'Napa Extra'
                 'টাইপ্লাস' -> 'Ty-plus'
                 'entacid' -> 'Entacyd'
        """
        clean_alias = alias_phrase.strip().lower()
        clean_brand = brand_name.strip()
        if not clean_alias or not clean_brand:
            return False

        accessible = Q(tenant__isnull=True) | Q(tenant_id=tenant_id)
        if not BrandDrug.objects.filter(accessible, brand_name__iexact=clean_brand, is_active=True).exists():
            return False
        aliases = [clean_alias]
        trans = transliterate_bangla_to_phonetic(clean_alias).lower()
        if trans != clean_alias:
            aliases.append(trans)

        try:
            for alias in aliases:
                MedicineAlias.objects.update_or_create(
                    tenant_id=tenant_id, alias=alias, defaults={"brand_name": clean_brand}
                )
            cache.delete(f"{CACHE_KEY_TRAINED_ALIASES}{tenant_id}")
            logger.info("Successfully trained alias: '%s' -> '%s'", clean_alias, clean_brand)
            return True
        except Exception as e:
            logger.error("Failed saving training alias: %s", e)
            return False

    @classmethod
    def find_match(cls, query: str, tenant_id: str) -> Optional[str]:
        """
        Looks up a query in:
        1. Exact match in user-trained custom aliases
        2. Exact match in comprehensive built-in aliases
        3. Phonetic transliteration exact match
        4. Longest-match substring where alias key is contained in user query
        """
        if not query:
            return None

        clean_q = query.strip().lower()

        # 1. Exact match in user-trained dictionary
        trained = cls.load_trained_aliases(tenant_id)
        if clean_q in trained:
            return trained[clean_q]

        # 2. Exact match in built-in common aliases
        for bn_key, eng_val in COMMON_BN_MEDICINE_ALIASES.items():
            if bn_key.lower() == clean_q:
                return eng_val

        # 3. Transliterated exact match
        trans_q = transliterate_bangla_to_phonetic(clean_q).lower()
        if trans_q in trained:
            return trained[trans_q]
        for bn_key, eng_val in COMMON_BN_MEDICINE_ALIASES.items():
            if bn_key.lower() == trans_q:
                return eng_val

        # 4. Longest-first substring match (user query contains alias key)
        sorted_trained = sorted(trained.items(), key=lambda x: len(x[0]), reverse=True)
        for alias_key, target_brand in sorted_trained:
            if alias_key in clean_q or alias_key in trans_q:
                return target_brand

        sorted_builtin = sorted(COMMON_BN_MEDICINE_ALIASES.items(), key=lambda x: len(x[0]), reverse=True)
        for bn_key, eng_val in sorted_builtin:
            if bn_key.lower() in clean_q or bn_key.lower() in trans_q:
                return eng_val

        return None

