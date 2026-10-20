from __future__ import annotations

import base64
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import requests
from django.conf import settings
from django.core.cache import cache
from django.db.models import Q

from inventory.models import BrandDrug

logger = logging.getLogger(__name__)

AI_CONFIG_PATH = os.path.join(settings.BASE_DIR, "media", "ai_config.json")
ENV_FILE_PATH = os.path.join(settings.BASE_DIR, ".env")
CACHE_KEY_AI_CONFIG = "pos:ai_system_config"
GEMINI_MODELS = [
    "gemini-3.5-flash",
    "gemini-flash-latest",
]


def _read_env_gemini_key() -> str:
    """Dynamically reads GEMINI_API_KEY from .env file if present."""
    if os.path.exists(ENV_FILE_PATH):
        try:
            with open(ENV_FILE_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("GEMINI_API_KEY="):
                        val = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if val:
                            return val
        except Exception:
            pass
    return ""


def _write_env_gemini_key(api_key: str):
    """Dynamically persists or clears GEMINI_API_KEY in .env file."""
    try:
        lines = []
        found = False
        if os.path.exists(ENV_FILE_PATH):
            with open(ENV_FILE_PATH, "r", encoding="utf-8") as f:
                lines = f.readlines()
        new_lines = []
        target_line = "GEMINI_API_KEY=" + api_key.strip() + chr(10)
        for line in lines:
            if line.strip().startswith("GEMINI_API_KEY="):
                found = True
                if api_key.strip():
                    new_lines.append(target_line)
            else:
                new_lines.append(line)
        if not found and api_key.strip():
            if new_lines and not new_lines[-1].endswith(chr(10)):
                new_lines.append(chr(10))
            new_lines.append(target_line)
        with open(ENV_FILE_PATH, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
    except Exception as e:
        logger.warning("Could not persist GEMINI_API_KEY to .env: %s", e)


class GeminiAIService:
    """
    Multimodal AI Service powered by Google Gemini:
    - Vision API: Human-grade medicine strip, bottle, and carton identification.
    - Voice API: Advanced natural language understanding of complex pharmacy voice orders in Bengali & English.
    - Resilient multi-model fallback across Gemini 3.5 Flash and Gemini 3.8 Flash.
    """

    @classmethod
    def _execute_gemini_request(cls, api_key: str, payload: Dict[str, Any], timeout: int = 15) -> Tuple[bool, Any]:
        """
        Executes a Gemini REST request across available models with automatic fallback
        if a specific model is busy (503) or not found (404).
        """
        clean_key = api_key.strip()
        if not clean_key:
            return False, "কোনো API Key প্রদান করা হয়নি।"

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": clean_key,
        }

        last_error = ""
        for model in GEMINI_MODELS:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={clean_key}"
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
                if resp.status_code == 200:
                    return True, resp.json()

                # If model is deprecated (404) or experiencing temporary demand spike (503), try next model
                if resp.status_code in (404, 503):
                    logger.warning("Gemini model %s returned %s, trying next candidate...", model, resp.status_code)
                    continue

                error_data = resp.json().get("error", {})
                last_error = error_data.get("message", resp.text)
                logger.warning("Gemini model %s error %s: %s", model, resp.status_code, last_error)
            except requests.exceptions.Timeout:
                logger.warning("Gemini model %s timed out, trying next candidate...", model)
                continue
            except Exception as req_err:
                last_error = str(req_err)
                logger.warning("Gemini model %s request exception: %s", model, req_err)

        return False, last_error or "সবগুলো Gemini মডেল আনএভেইলেবল বা নেটওয়ার্ক টাইমআউট হয়েছে।"

    @classmethod
    def get_config(cls) -> Dict[str, Any]:
        """Loads AI config dynamically from cache, media/ai_config.json, .env, or settings."""
        cached = cache.get(CACHE_KEY_AI_CONFIG)
        if cached is not None and isinstance(cached, dict):
            return cached

        config = {
            "gemini_api_key": "",
            "enabled": True,
            "preferred_engine": "gemini",
        }

        # 1. Check media/ai_config.json
        if os.path.exists(AI_CONFIG_PATH):
            try:
                with open(AI_CONFIG_PATH, "r", encoding="utf-8") as f:
                    file_conf = json.load(f)
                    if isinstance(file_conf, dict):
                        config.update(file_conf)
            except Exception as e:
                logger.warning("Could not read ai_config.json: %s", e)

        # 2. Check .env if still empty
        if not config.get("gemini_api_key"):
            env_key = _read_env_gemini_key()
            if env_key:
                config["gemini_api_key"] = env_key

        # 3. Check os.environ and settings if still empty
        if not config.get("gemini_api_key"):
            config["gemini_api_key"] = (
                os.environ.get("GEMINI_API_KEY", "")
                or getattr(settings, "GEMINI_API_KEY", "")
                or ""
            ).strip()

        cache.set(CACHE_KEY_AI_CONFIG, config, 3600)
        return config

    @classmethod
    def save_config(cls, api_key: str, enabled: bool = True, preferred_engine: str = "gemini") -> bool:
        """Saves updated Gemini config dynamically to media/ai_config.json, .env, and updates cache."""
        clean_key = api_key.strip()
        if "..." in clean_key:
            clean_key = cls.get_api_key()
        elif clean_key.upper() == "CLEAR":
            clean_key = ""

        config = {
            "gemini_api_key": clean_key,
            "enabled": bool(enabled),
            "preferred_engine": preferred_engine,
        }
        try:
            os.makedirs(os.path.dirname(AI_CONFIG_PATH), exist_ok=True)
            with open(AI_CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)

            # Update live process memory and .env file
            if clean_key:
                os.environ["GEMINI_API_KEY"] = clean_key
                _write_env_gemini_key(clean_key)

            cache.set(CACHE_KEY_AI_CONFIG, config, 86400)
            logger.info("Successfully updated AI configuration dynamically")
            return True
        except Exception as e:
            logger.error("Failed saving AI config: %s", e)
            return False

    @classmethod
    def get_api_key(cls) -> str:
        conf = cls.get_config()
        return conf.get("gemini_api_key", "").strip()

    @classmethod
    def is_gemini_active(cls) -> bool:
        conf = cls.get_config()
        key = conf.get("gemini_api_key", "").strip()
        enabled = conf.get("enabled", True)
        return bool(key) and bool(enabled)

    @classmethod
    def test_gemini_connection(cls, api_key: Optional[str] = None) -> Tuple[bool, str]:
        """Tests if the given or configured Gemini API key is valid."""
        key = api_key.strip() if (api_key and "..." not in api_key) else cls.get_api_key()
        if not key:
            return False, "কোনো API Key প্রদান করা হয়নি।"

        payload = {
            "contents": [
                {
                    "parts": [{"text": "Hello, respond with ONLY the word OK."}]
                }
            ],
            "generationConfig": {
                "maxOutputTokens": 10,
                "temperature": 0.0,
            }
        }
        success, res_or_err = cls._execute_gemini_request(key, payload, timeout=10)
        if success:
            return True, "Gemini AI কানেকশন সফল হয়েছে!"
        return False, f"Gemini API এরর: {res_or_err}"

    @classmethod
    def analyze_medicine_image(cls, image_bytes: bytes, mime_type: str = "image/jpeg") -> Optional[Dict[str, Any]]:
        """
        Submits medicine blister/package image to Google Gemini Vision.
        Extracts brand name, generic name, strength, dosage form, and manufacturer.
        """
        api_key = cls.get_api_key()
        if not api_key:
            return None

        b64_image = base64.b64encode(image_bytes).decode("utf-8")
        prompt = (
            "You are an expert pharmaceutical vision and OCR system in Bangladesh. "
            "Examine this medicine image (blister strip, foil pack, bottle, or carton). "
            "FOCUS PRIMARILY ON THE LARGEST, MOST PROMINENT PRIMARY MEDICINE TRADE / BRAND NAME printed on the packaging "
            "(e.g., Napa, Napa Extra, Entacyd Plus, Ty-plus, Seclo, Sergel, Monas, Ace, Alarid, Ceevit, etc.). "
            "Ignore tiny batch numbers, manufacturing licenses, dates, barcodes, DAR numbers, prices, or secondary fine print. "
            "Return strictly valid JSON with no markdown wrapping or code fences. "
            "JSON structure:\n"
            "{\n"
            '  "brand_name": "Largest prominent brand name (e.g. Entacyd Plus, Napa, Ty-plus)",\n'
            '  "generic_name": "Active chemical/generic composition (e.g. Aluminium Hydroxide + Magnesium Hydroxide + Simethicone)",\n'
            '  "strength": "Strength (e.g. 500 mg or 20 mg)",\n'
            '  "dosage_form": "Dosage form (e.g. Tablet, Chewable Tablet, Capsule, Suspension, Syrup, Drops)",\n'
            '  "manufacturer": "Pharma company (e.g. Square, Incepta, Beximco, Renata)",\n'
            '  "confidence": 0.98\n'
            "}\n"
            "Do not guess or infer a brand from color, packaging style, or generic ingredients. "
            "If the printed brand name is not clearly readable, return an empty brand_name and low confidence."
        )

        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": b64_image,
                            }
                        },
                        {
                            "text": prompt
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 1000,
                "response_mime_type": "application/json",
            }
        }

        # Vision is an optional assist; keep its worst-case delay bounded so a
        # slow provider does not stall the cashier for two full model timeouts.
        success, data = cls._execute_gemini_request(api_key, payload, timeout=15)
        if not success or not isinstance(data, dict):
            logger.error("Gemini Vision analysis failed: %s", data)
            return None

        try:
            candidates = data.get("candidates", [])
            if not candidates:
                return None

            text_content = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
            cleaned_json_text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text_content, flags=re.MULTILINE).strip()
            parsed = json.loads(cleaned_json_text)
            logger.info("Gemini Vision Success: %s", parsed)
            try:
                confidence = float(parsed.get("confidence", 0) or 0)
            except (TypeError, ValueError):
                confidence = 0
            # Medicine identity is safety-sensitive; reject weak visual guesses.
            if not parsed.get('brand_name') or (confidence > 0 and confidence < 0.50):
                return None
            return parsed
        except Exception as e:
            logger.error("Gemini Vision JSON parsing exception: %s", e)
            return None

    @classmethod
    def parse_voice_transcript(cls, transcript: str) -> Optional[List[Dict[str, Any]]]:
        """
        Uses Gemini to understand natural Bengali/English pharmacy speech.
        """
        api_key = cls.get_api_key()
        if not api_key:
            return None

        prompt = (
            "You are a pharmaceutical voice order assistant for a Bangladeshi pharmacy POS. "
            f"Parse the following spoken command in Bengali/English: '{transcript}'. "
            "Convert quantities intelligently: 1 pata/strip = 10 pcs, 1 box = 100 pcs. "
            "Identify the brand name in standard English DGDA format (e.g. 'Napa Extra', 'Entacyd Plus', 'Seclo', 'Sergel'). "
            "Return strictly a JSON array of objects with keys: brand_name (str), quantity (int), dosage_form (str). "
            "No markdown code fences."
        )

        payload = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 1000,
                "response_mime_type": "application/json",
            }
        }

        success, data = cls._execute_gemini_request(api_key, payload, timeout=10)
        if not success or not isinstance(data, dict):
            return None

        try:
            text_content = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
            cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text_content, flags=re.MULTILINE).strip()
            parsed = json.loads(cleaned)
            if isinstance(parsed, list):
                return parsed
        except Exception as e:
            logger.warning("Gemini Voice Parse exception: %s", e)

        return None

    @classmethod
    def match_drug_from_gemini(cls, gemini_result: Dict[str, Any], tenant_key: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Takes structured Gemini Vision output and matches with high clinical precision
        against BrandDrug inventory, respecting dosage form, strength, and generic ingredients.
        """
        b_name = (gemini_result.get("brand_name") or "").strip()
        g_name = (gemini_result.get("generic_name") or "").strip()
        s_form = (gemini_result.get("dosage_form") or "").strip()
        s_strength = (gemini_result.get("strength") or "").strip()

        # A generic alone cannot identify a dispensable brand and strength variant.
        if not b_name:
            return []

        # Candidate query: exact, starts_with, contains, or generic
        catalog_scope = Q(tenant__isnull=True)
        if tenant_key and tenant_key != "default_tenant":
            catalog_scope |= Q(tenant_id=tenant_key)
        query_set = BrandDrug.objects.filter(catalog_scope, is_active=True)
        candidates = list(query_set.filter(brand_name__iexact=b_name))
        if not candidates:
            candidates = list(query_set.filter(brand_name__istartswith=b_name))
        if not candidates:
            # Multi-word token search (e.g. "Entacyd Plus", "Ty-plus")
            first_word = re.split(r'[\s\-+]+', b_name)[0] if b_name else ""
            if len(first_word) >= 3:
                candidates = list(query_set.filter(brand_name__icontains=first_word))

        if not candidates:
            return []

        ranked_items = []
        for drug in candidates:
            vision_strength_numbers = set(re.findall(r"\d+(?:\.\d+)?", s_strength))
            catalog_strength_numbers = set(re.findall(r"\d+(?:\.\d+)?", drug.strength or ""))
            if vision_strength_numbers and catalog_strength_numbers and not (
                vision_strength_numbers & catalog_strength_numbers
            ):
                continue

            score = 50.0

            # Brand name comparison
            if drug.brand_name.lower() == b_name.lower():
                score += 35.0
            elif b_name.lower() in drug.brand_name.lower():
                score += 25.0

            # Dosage form comparison (e.g. Chewable Tablet vs Suspension)
            d_form_name = (drug.dosage_form.name if drug.dosage_form else "").lower()
            if s_form:
                s_form_lower = s_form.lower()
                if "chew" in s_form_lower and "chew" in d_form_name:
                    score += 20.0
                elif "tab" in s_form_lower and "tab" in d_form_name:
                    score += 15.0
                elif ("susp" in s_form_lower or "syr" in s_form_lower) and ("susp" in d_form_name or "syr" in d_form_name):
                    score += 15.0

            # Strength comparison
            if s_strength and drug.strength:
                s_nums = re.findall(r"\d+", s_strength)
                d_nums = re.findall(r"\d+", drug.strength)
                matching_nums = set(s_nums).intersection(set(d_nums))
                if matching_nums:
                    score += 10.0 * len(matching_nums)

            # Generic comparison
            if g_name and drug.generic:
                d_gen = drug.generic.name.lower()
                for token in re.findall(r"[a-z]{5,}", g_name.lower()):
                    if token in d_gen:
                        score += 5.0

            fefo = drug.batches.fefo().first() or drug.batches.order_by("-expiry_date").first()
            drug_dict = {
                "id": str(drug.id),
                "brand_name": drug.brand_name,
                "name": drug.brand_name,
                "unit_mrp": str(drug.unit_mrp),
                "price": float(drug.unit_mrp),
                "strength": drug.strength or "",
                "dosage_form": drug.dosage_form.short_name or drug.dosage_form.name if drug.dosage_form else "Tab",
                "generic_name": drug.generic.name if drug.generic else "N/A",
                "manufacturer": drug.manufacturer.name if drug.manufacturer else "N/A",
                "total_stock": drug.total_stock,
                "score": min(100, round(score)),
                "ai_engine": "gemini",
                "fefo_batch": {
                    "id": str(fefo.id) if fefo else None,
                    "batch_number": fefo.batch_number if fefo else "N/A",
                    "expiry_date": fefo.expiry_date.strftime("%Y-%m-%d") if fefo else "N/A",
                    "stock": fefo.current_stock if fefo else 0,
                } if fefo else None
            }
            ranked_items.append(drug_dict)

        ranked_items.sort(key=lambda x: x["score"], reverse=True)
        return ranked_items
