from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from django.conf import settings
from django.core.cache import cache

from inventory.models import BrandDrug, GenericDrug
from pos.utils import (
    COMMON_BN_MEDICINE_ALIASES,
    compute_metaphone,
    compute_soundex,
    rank_phonetic_matches,
    transliterate_bangla_to_phonetic,
)

logger = logging.getLogger(__name__)

TRAINING_FILE_PATH = os.path.join(settings.BASE_DIR, "media", "medicine_training_aliases.json")
CACHE_KEY_TRAINED_ALIASES = "pos:trained_medicine_aliases"


class DrugTrainingService:
    """
    Self-learning and training engine for PharmaFlow POS.
    Allows pharmacists to train custom voice pronunciations, regional medicine nicknames,
    and OCR packaging aliases that automatically map to DGDA catalog drugs.
    """

    @classmethod
    def load_trained_aliases(cls) -> Dict[str, str]:
        """Loads custom user-trained aliases from cache or persistent JSON file."""
        cached = cache.get(CACHE_KEY_TRAINED_ALIASES)
        if cached is not None and isinstance(cached, dict):
            return cached

        aliases = {}
        if os.path.exists(TRAINING_FILE_PATH):
            try:
                with open(TRAINING_FILE_PATH, "r", encoding="utf-8") as f:
                    aliases = json.load(f)
            except Exception as e:
                logger.warning("Could not read training aliases file: %s", e)

        cache.set(CACHE_KEY_TRAINED_ALIASES, aliases, 86400)
        return aliases

    @classmethod
    def save_trained_alias(cls, alias_phrase: str, brand_name: str) -> bool:
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

        aliases = cls.load_trained_aliases()
        aliases[clean_alias] = clean_brand
        # Also save phonetic transliterated version
        trans = transliterate_bangla_to_phonetic(clean_alias).lower()
        if trans != clean_alias:
            aliases[trans] = clean_brand

        try:
            os.makedirs(os.path.dirname(TRAINING_FILE_PATH), exist_ok=True)
            with open(TRAINING_FILE_PATH, "w", encoding="utf-8") as f:
                json.dump(aliases, f, ensure_ascii=False, indent=2)
            cache.set(CACHE_KEY_TRAINED_ALIASES, aliases, 86400)
            logger.info("Successfully trained alias: '%s' -> '%s'", clean_alias, clean_brand)
            return True
        except Exception as e:
            logger.error("Failed saving training alias: %s", e)
            return False

    @classmethod
    def find_match(cls, query: str) -> Optional[str]:
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
        trained = cls.load_trained_aliases()
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

