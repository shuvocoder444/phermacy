from __future__ import annotations

import os
import sys

# Prevent OpenBLAS from spawning 32 threads and exhausting cPanel nproc limits
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"

# Prevent ascii encoding errors on Apache/Passenger stdout/stderr
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import base64
import difflib
import io
import logging
import re
import time
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)

# Toggle for saving preprocessed OCR images for inspection and debugging
DEBUG_OCR_SAVE = getattr(settings, "DEBUG_OCR_SAVE", True)
DEBUG_OCR_DIR = os.path.join(settings.BASE_DIR, "media", "ocr_debug")

# Optional deep learning & phonetic dependencies with pure-python fallbacks
try:
    import easyocr
    HAS_EASYOCR = True
except ImportError:
    easyocr = None
    HAS_EASYOCR = False

try:
    import jellyfish
    HAS_JELLYFISH = True
except ImportError:
    jellyfish = None
    HAS_JELLYFISH = False

try:
    from thefuzz import fuzz
    HAS_THEFUZZ = True
except ImportError:
    try:
        from fuzzywuzzy import fuzz
        HAS_THEFUZZ = True
    except ImportError:
        fuzz = None
        HAS_THEFUZZ = False

try:
    import cv2
    import numpy as np
    HAS_OPENCV = True
except ImportError:
    cv2 = None
    np = None
    HAS_OPENCV = False

try:
    import pytesseract
    HAS_PYTESSERACT = True
    # Auto-configure Tesseract binary and tessdata prefix if static binary or custom path exists
    STATIC_TESS_BIN = "/home/webkoders/.local/bin/tesseract"
    if os.path.exists(STATIC_TESS_BIN):
        pytesseract.pytesseract.tesseract_cmd = STATIC_TESS_BIN
        os.environ["TESSDATA_PREFIX"] = "/home/webkoders/tessdata"
except ImportError:
    pytesseract = None
    HAS_PYTESSERACT = False

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

# =========================================================================
# 1. EASYOCR SINGLETON INITIALIZATION
# =========================================================================

_EASYOCR_READER = None


def get_easyocr_reader():
    """
    Singleton lazy-loader for EasyOCR Reader.
    Supports English ('en') and Bengali ('bn') models.
    """
    global _EASYOCR_READER
    if not HAS_EASYOCR or easyocr is None:
        return None
    if _EASYOCR_READER is None:
        try:
            logger.info("Initializing EasyOCR reader with languages ['en', 'bn']...")
            # Use CPU by default (gpu=False) for broad compatibility
            _EASYOCR_READER = easyocr.Reader(['en', 'bn'], gpu=False, verbose=False)
            logger.info("EasyOCR reader initialized successfully.")
        except Exception as e:
            logger.warning("Failed to initialize EasyOCR reader: %s", e)
            _EASYOCR_READER = None
    return _EASYOCR_READER


# =========================================================================
# 2. BENGALI PHONETIC & TRANSLITERATION ENGINE
# =========================================================================

BN_PHONETIC_CHAR_MAP = {
    'অ': 'o', 'আ': 'a', 'ই': 'i', 'ঈ': 'i', 'উ': 'u', 'ঊ': 'u', 'ঋ': 'ri',
    'এ': 'e', 'ঐ': 'oi', 'ও': 'o', 'ঔ': 'ou',
    'ক': 'k', 'খ': 'kh', 'গ': 'g', 'ঘ': 'gh', 'ঙ': 'ng',
    'চ': 'c', 'ছ': 'ch', 'জ': 'j', 'ঝ': 'jh', 'ঞ': 'n',
    'ট': 't', 'ঠ': 'th', 'ড': 'd', 'ঢ': 'dh', 'ণ': 'n',
    'ত': 't', 'থ': 'th', 'দ': 'd', 'ধ': 'dh', 'ন': 'n',
    'প': 'p', 'ফ': 'f', 'ব': 'b', 'ভ': 'bh', 'ম': 'm',
    'য': 'j', 'র': 'r', 'ল': 'l', 'শ': 'sh', 'ষ': 'sh', 'স': 's', 'হ': 'h',
    'ড়': 'r', 'ঢ়': 'rh', 'য়': 'y', 'ৎ': 't', 'ং': 'ng', 'ঃ': 'h', 'ঁ': '',
    'া': 'a', 'ি': 'i', 'ী': 'i', 'ু': 'u', 'ূ': 'u', 'ৃ': 'ri',
    'ে': 'e', 'ৈ': 'oi', 'ো': 'o', 'ৌ': 'ou', '্': '',
}

COMMON_BN_MEDICINE_ALIASES = {
    # Paracetamol & Pain relief
    "নাপা": "Napa",
    "নাপা ৫০০": "Napa",
    "নাপা ওয়ান": "Napa One",
    "নাপা ১০০০": "Napa One",
    "নাপা এক্সট্রা": "Napa Extra",
    "নাপা রেপিড": "Napa Rapid",
    "নাপা র‍্যাপিড": "Napa Rapid",
    "নাপা সিরাপ": "Napa",
    "নাপা ড্রপ": "Napa",
    "এইস": "Ace",
    "এইস ৫০০": "Ace",
    "এইস প্লাস": "Ace Plus",
    "এইস সিরাপ": "Ace",
    "এস": "Ace",
    "এস প্লাস": "Ace Plus",
    "প্যারাসিটামল": "Napa",
    "টাই প্লাস": "Ty-plus",
    "টাইপ্লাস": "Ty-plus",
    "টাই-প্লাস": "Ty-plus",
    "ক্লোফেনাক": "Clofenac",
    "ডাইক্লোফেনাক": "Clofenac",
    "ভোভেরান": "Voveran",
    "নাপ্রোক্সেন": "Naprosyn",
    "ন্যাপ্রোসিন": "Naprosyn",
    "টোরাক্স": "Torax",
    "রোল্যাক": "Rolac",

    # Antacid & Gastric / PPI
    "এনটাসিড": "Entacyd",
    "এনটাসিড প্লাস": "Entacyd Plus",
    "এন্টাসিড": "Entacyd",
    "এন্টাসিড প্লাস": "Entacyd Plus",
    "এন্টাসিড সিরাপ": "Entacyd Plus",
    "মার্লক্স": "Marlux",
    "সারজেল": "Sergel",
    "সারজেল ২০": "Sergel",
    "সারজেল ৪০": "Sergel",
    "সার্জেল": "Sergel",
    "সার্জেল ২০": "Sergel",
    "ম্যাক্সপ্রো": "Maxpro",
    "ম্যাক্সপ্রো ২০": "Maxpro",
    "ম্যাক্সপ্রো ৪০": "Maxpro",
    "এসোমিপ্রাজল": "Maxpro",
    "সেকলো": "Seclo",
    "সেকলো ২০": "Seclo",
    "সেকলো ৪০": "Seclo",
    "সেকল": "Seclo",
    "ওমেপ্রাজল": "Seclo",
    "প্যান্টোনিক্স": "Pantonix",
    "প্যান্টোনিক্স ২০": "Pantonix",
    "প্যান্টোনিক্স ৪০": "Pantonix",
    "প্যান্টোপ্রাজল": "Pantonix",
    "ফিনিক্স": "Finix",
    "ফিনিক্স ২০": "Finix",
    "রেবিপ্রাজল": "Finix",

    # Asthma & Respiratory
    "মোনাস": "Monas",
    "মোনাস ১০": "Monas",
    "মোনাস ৪": "Monas",
    "মোনাস ৫": "Monas",
    "মন্টিন": "Montene",
    "মন্টিন ১০": "Montene",
    "প্রোভায়ার": "Provair",
    "মন্টেলুকাস্ট": "Monas",
    "উইন্ডেল": "Windel",
    "সালবুটামল": "Windel",
    "সাল্টোলিন": "Sultolin",

    # Antihistamine & Allergy
    "ফেক্সো": "Fexo",
    "ফেক্সো ৬০": "Fexo",
    "ফেক্সো ১২০": "Fexo",
    "ফেক্সো ১৮০": "Fexo",
    "ফেক্সোফেনাডিন": "Fexo",
    "বিলাটিন": "Bilatin",
    "বিলাস্টিন": "Bilatin",
    "অ্যালাট্রোল": "Alatrol",
    "এলাট্রোল": "Alatrol",
    "সেটিরিজিন": "Alatrol",
    "হিস্টাসিন": "Histacin",
    "রুপাফিন": "Rupafin",
    "ডেসলোর": "Deslor",

    # Cough & Cold
    "টাসকা": "Tusca",
    "টাস্কা": "Tusca",
    "আদভাস": "Adovas",
    "বাসক": "Adovas",
    "কাশির সিরাপ": "Tusca",
    "মিরাপেক্স": "Mirapex",

    # Antibiotics
    "সেফ ৩": "Cef-3",
    "সেফ-৩": "Cef-3",
    "সেফ থ্রি": "Cef-3",
    "সেফিক্সিম": "Cef-3",
    "জিম্যাক্স": "Zimax",
    "জিম্যাক্স ৫০০": "Zimax",
    "এজিথ্রোমাইসিন": "Zimax",
    "মক্সাক্ল্যাভ": "Moxaclav",
    "মক্সাক্লাভ": "Moxaclav",
    "সিপ্রোসিন": "Ciprocin",
    "সিপ্রোসিন ৫০০": "Ciprocin",
    "সিপ্রোফ্লক্সাসিন": "Ciprocin",
    "ফ্লামিড": "Flamyd",
    "ফ্লামিড ৪০০": "Flamyd",
    "মেট্রোনিডাজল": "Flamyd",

    # Diabetes & Cardiovascular
    "কম্প্যাথ": "Compath",
    "মেটফরমিন": "Compath",
    "জি মেট": "G-Met",
    "জি-মেট": "G-Met",
    "গ্লুকো-এক্স": "Gluco-X",
    "বাইসলল": "Bislol",
    "বাইসলল ২.৫": "Bislol",
    "বাইসলল ৫": "Bislol",
    "বিসোপ্রোলল": "Bislol",
    "এনজিলক": "Angilock",
    "রোসুভা": "Rosuva",
    "রোসুভা ১০": "Rosuva",
    "রোসুভা ৫": "Rosuva",
    "রোসুভাস্ট্যাটিন": "Rosuva",
    "অ্যাটোভা": "Atova",
    "বাইজোরান": "Bizoran",
    "ওসার্টিন": "Osartil",

    # Vitamins, Calcium & Minerals
    "কোরালক্যাল": "Coralcal",
    "কোরালক্যাল ডি": "Coralcal-D",
    "কোরালক্যাল-ডি": "Coralcal-D",
    "ক্যালবো": "Calbo",
    "ক্যালবো ডি": "Calbo-D",
    "ক্যালবো-ডি": "Calbo-D",
    "ক্যালসিয়াম": "Calbo-D",
    "বেক্সট্রাম গোল্ড": "Bextram Gold",
    "ফিলওয়েল গোল্ড": "Filwel Gold",
    "নিউরো বি": "Neuro-B",
    "নিউরো-বি": "Neuro-B",
    "ভিটামিন বি": "Neuro-B",
    "বেবি জিংক": "Baby Zinc",
    "জিংক": "Baby Zinc",

    # Ointments & Topical
    "বার্নসিল": "Burnsil",
    "বার্ন ক্রিম": "Burnsil",
    "ডার্মাসল": "Dermasol",
    "পেভিসন": "Pevisone",
    "পেভিসন মলম": "Pevisone",
    "বেটনোভেট": "Betnovate",
    "বেটনোভেট এন": "Betnovate-N",

    # Rehydration
    "স্যালাইন": "SMC ORSaline-N",
    "খাবার স্যালাইন": "SMC ORSaline-N",
    "ওরস্যালাইন": "SMC ORSaline-N",
    "টেস্টি স্যালাইন": "SMC ORSaline-N",
}


def transliterate_bangla_to_phonetic(text: str) -> str:
    """
    Converts Bengali text into English phonetic equivalent.
    Example: 'এন্টাসিড প্লাস' -> 'entasid plas'
    """
    clean_text = text.strip()
    for bn_key, eng_val in COMMON_BN_MEDICINE_ALIASES.items():
        if bn_key in clean_text:
            clean_text = clean_text.replace(bn_key, eng_val)

    output = []
    for char in clean_text:
        if char in BN_PHONETIC_CHAR_MAP:
            output.append(BN_PHONETIC_CHAR_MAP[char])
        else:
            output.append(char)
    return "".join(output)


def compute_metaphone(word: str) -> str:
    """Computes Metaphone phonetic code with jellyfish or pure-python fallback."""
    if not word:
        return ""
    clean_w = re.sub(r'[^a-zA-Z]', '', word).upper()
    if not clean_w:
        return ""

    if HAS_JELLYFISH and jellyfish:
        try:
            return jellyfish.metaphone(clean_w)
        except Exception:
            pass

    # Pure Python phonetic normalization fallback
    s = clean_w
    s = re.sub(r'[AEIOUY]', 'A', s)
    s = s.replace('PH', 'F').replace('TH', 'T').replace('CH', 'C').replace('SH', 'S')
    s = s.replace('K', 'C').replace('Q', 'C').replace('X', 'CS').replace('Z', 'S')
    s = re.sub(r'(.)\1+', r'\1', s)
    return s[:6]


def compute_soundex(word: str) -> str:
    """Computes Soundex code using jellyfish or pure-python algorithm."""
    if not word:
        return ""
    clean_w = re.sub(r'[^a-zA-Z]', '', word).upper()
    if not clean_w:
        return ""

    if HAS_JELLYFISH and jellyfish:
        try:
            return jellyfish.soundex(clean_w)
        except Exception:
            pass

    # Pure Python soundex fallback
    first = clean_w[0]
    codes = {
        'B': '1', 'F': '1', 'P': '1', 'V': '1',
        'C': '2', 'G': '2', 'J': '2', 'K': '2', 'Q': '2', 'S': '2', 'X': '2', 'Z': '2',
        'D': '3', 'T': '3',
        'L': '4',
        'M': '5', 'N': '5',
        'R': '6'
    }
    encoded = [first]
    prev = codes.get(first, '0')
    for char in clean_w[1:]:
        code = codes.get(char, '0')
        if code != '0' and code != prev:
            encoded.append(code)
        prev = code
    return (("".join(encoded) + "000")[:4])


def calculate_fuzzy_score(s1: str, s2: str) -> float:
    """Calculates 0-100 similarity score between two strings using thefuzz or difflib."""
    if not s1 or not s2:
        return 0.0
    s1_clean = s1.lower().strip()
    s2_clean = s2.lower().strip()

    if s1_clean == s2_clean:
        return 100.0

    if HAS_THEFUZZ and fuzz:
        try:
            ratio1 = fuzz.token_sort_ratio(s1_clean, s2_clean)
            ratio2 = fuzz.partial_ratio(s1_clean, s2_clean)
            return float(max(ratio1, ratio2))
        except Exception:
            pass

    matcher = difflib.SequenceMatcher(None, s1_clean, s2_clean)
    return float(matcher.ratio() * 100.0)


def rank_phonetic_matches(query: str, brand_candidates: list[str], top_n: int = 5) -> list[tuple[str, float]]:
    """
    Ranks brand names against a user query using combined:
    1. Direct string matching (exact, starts-with, contains)
    2. Transliteration (Bangla -> Latin)
    3. Metaphone & Soundex phonetic sound codes
    4. Fuzzy token sort ratio (thefuzz)
    """
    if not query:
        return []

    norm_query = transliterate_bangla_to_phonetic(query).lower()
    norm_query_clean = re.sub(r'[^a-zA-Z0-9\s]', ' ', norm_query).strip()
    query_tokens = norm_query_clean.split()
    query_first_token = query_tokens[0] if query_tokens else norm_query_clean
    query_meta = compute_metaphone(query_first_token)
    query_soundex = compute_soundex(query_first_token)

    scored_results = []

    for brand in brand_candidates:
        if not brand:
            continue
        brand_clean = brand.lower().strip()
        brand_tokens = re.sub(r'[^a-zA-Z0-9\s]', ' ', brand_clean).split()
        brand_first_token = brand_tokens[0] if brand_tokens else brand_clean
        brand_meta = compute_metaphone(brand_first_token)
        brand_soundex = compute_soundex(brand_first_token)

        score = 0.0

        if norm_query_clean == brand_clean:
            score = 100.0
        elif brand_clean.startswith(norm_query_clean) or norm_query_clean.startswith(brand_clean):
            score = 90.0
        else:
            fuzzy_full = calculate_fuzzy_score(norm_query_clean, brand_clean)
            fuzzy_first = calculate_fuzzy_score(query_first_token, brand_first_token)

            phonetic_bonus = 0.0
            if query_meta and brand_meta and query_meta == brand_meta:
                phonetic_bonus += 20.0
            if query_soundex and brand_soundex and query_soundex == brand_soundex:
                phonetic_bonus += 15.0

            score = max(fuzzy_full, fuzzy_first) + phonetic_bonus

        if score >= 45.0:
            scored_results.append((brand, min(score, 100.0)))

    scored_results.sort(key=lambda x: x[1], reverse=True)
    return scored_results[:top_n]


# =========================================================================
# 3. OPENCV MEDICINE FOIL STRIP & BLUE INK PREPROCESSING PIPELINE
# =========================================================================

def decode_image_input(image_input: Any) -> tuple[Image.Image, np.ndarray | None]:
    """Decodes base64 string, byte buffer, or uploaded file into PIL and OpenCV formats."""
    image_bytes = None
    if hasattr(image_input, "read"):
        image_bytes = image_input.read()
    elif isinstance(image_input, (str, bytes)):
        if isinstance(image_input, str) and image_input.startswith("data:image"):
            image_input = image_input.split(",", 1)[1]
            image_bytes = base64.b64decode(image_input)
        elif isinstance(image_input, str):
            image_bytes = base64.b64decode(image_input)
        else:
            image_bytes = image_input
    elif isinstance(image_input, Image.Image):
        pil_img = image_input.convert("RGB")
        np_arr = np.array(pil_img) if HAS_OPENCV and np is not None else None
        return pil_img, np_arr

    if not image_bytes:
        raise ValueError("Empty or invalid image data provided")

    pil_img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    np_arr = None
    if HAS_OPENCV and np is not None:
        np_arr = np.frombuffer(image_bytes, np.uint8)
        np_arr = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    return pil_img, np_arr


def preprocess_medicine_foil_image(image_input: Any, save_debug: bool = DEBUG_OCR_SAVE) -> Image.Image:
    """
    Advanced Computer Vision pipeline tailored for medicine blister and foil strip packaging:
    a. 2x Upscale / Resize for small text detection.
    b. Blue ink isolation: extracts Red channel where blue ink appears as dark text while silver reflections remain white.
    c. Reflection suppression: Median blur removes specular reflections, followed by Adaptive Gaussian Thresholding.
    d. Inversion normalization: ensures text is black (0) on pure white (255) background.
    e. Optional debug image persistence for verification.
    """
    pil_img, cv_img = decode_image_input(image_input)

    # OpenCV Pipeline
    if HAS_OPENCV and cv2 is not None and np is not None and cv_img is not None:
        try:
            # a. 2x Upscale / Resize for small font detection
            h, w = cv_img.shape[:2]
            scaled = cv2.resize(cv_img, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)

            # b. Blue ink isolation using Red channel
            # In BGR format: index 0 is Blue, 1 is Green, 2 is Red.
            _, _, r_channel = cv2.split(scaled)
            red_channel = r_channel

            # Enhance contrast locally using CLAHE on the Red channel
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            contrast_red = clahe.apply(red_channel)

            # c. Suppress silver reflection noise using Median Blur
            denoised = cv2.medianBlur(contrast_red, 3)

            # Apply Adaptive Gaussian Thresholding
            thresh = cv2.adaptiveThreshold(
                denoised,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                blockSize=21,
                C=10
            )

            # d. Ensure Text is Black (0) and Background is White (255)
            h_t, w_t = thresh.shape
            border_pixels = np.concatenate([
                thresh[0, :], thresh[h_t - 1, :],
                thresh[:, 0], thresh[:, w_t - 1]
            ])
            if np.mean(border_pixels) < 127:
                thresh = cv2.bitwise_not(thresh)

            # e. Optional Debug Image Saving
            if save_debug:
                try:
                    os.makedirs(DEBUG_OCR_DIR, exist_ok=True)
                    debug_file = os.path.join(DEBUG_OCR_DIR, f"ocr_debug_{int(time.time() * 1000)}.png")
                    cv2.imwrite(debug_file, thresh)
                    logger.info("Saved preprocessed OCR debug image to %s", debug_file)
                except Exception as save_err:
                    logger.debug("Failed saving OCR debug image: %s", save_err)

            return Image.fromarray(thresh)
        except Exception as e:
            logger.warning("OpenCV processing failed, falling back to PIL: %s", e)

    # PIL Fallback Pipeline
    w_p, h_p = pil_img.size
    pil_scaled = pil_img.resize((w_p * 2, h_p * 2), Image.Resampling.LANCZOS)
    r_band, _, _ = pil_scaled.split()
    enhancer = ImageEnhance.Contrast(r_band)
    high_contrast = enhancer.enhance(2.5)
    filtered = high_contrast.filter(ImageFilter.MedianFilter(size=3))
    auto_level = ImageOps.autocontrast(filtered, cutoff=3)
    binarized = auto_level.point(lambda p: 255 if p > 135 else 0)

    stat = ImageOps.grayscale(binarized)
    if np and np.mean(np.array(stat)) < 127:
        binarized = ImageOps.invert(binarized)

    return binarized


# =========================================================================
# 4. MULTI-ENGINE OCR EXTRACTION (EASYOCR + TESSERACT HYBRID)
# =========================================================================

def extract_medicine_text_from_image(image_input: Any) -> str:
    """
    Robust OCR extraction using EasyOCR with graceful Tesseract fallback:
    1. Preprocesses image to eliminate silver foil glare and isolate blue ink.
    2. Runs EasyOCR (with Bengali + English neural models) on the raw or preprocessed image.
    3. If EasyOCR is unavailable or returns empty, executes Tesseract with packaging flags (--psm 11).
    """
    pil_preprocessed = preprocess_medicine_foil_image(image_input)

    # 1. Try EasyOCR Deep Learning Pipeline
    reader = get_easyocr_reader()
    if reader is not None and HAS_OPENCV and np is not None:
        try:
            np_img = np.array(pil_preprocessed)
            # EasyOCR readtext with paragraph grouping
            results = reader.readtext(np_img, detail=0, paragraph=True)
            text_extracted = " ".join([r.strip() for r in results if r.strip()])
            if len(text_extracted) >= 2:
                logger.info("EasyOCR successfully extracted: '%s'", text_extracted)
                return text_extracted
        except Exception as err:
            logger.warning("EasyOCR run exception: %s, falling back to Tesseract", err)

    # 2. Tesseract OCR Fallback Pipeline
    if HAS_PYTESSERACT and pytesseract is not None:
        configs = [
            r'--oem 3 --psm 11 -l eng+ben',
            r'--oem 3 --psm 11 -l eng',
            r'--oem 3 --psm 6 -l eng+ben',
            r'--oem 3 --psm 6 -l eng',
        ]
        for config in configs:
            try:
                text = pytesseract.image_to_string(pil_preprocessed, config=config).strip()
                if len(text) >= 2:
                    logger.info("Tesseract successfully extracted with config '%s': '%s'", config, text)
                    return text
            except Exception:
                continue

    return ""
