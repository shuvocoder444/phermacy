import re

# 1. Update pos/gemini_service.py
with open('pos/gemini_service.py', 'r', encoding='utf-8') as f:
    g_content = f.read()

g_content = re.sub(
    r'GEMINI_MODELS\s*=\s*\[[^\]]+\]',
    '''GEMINI_MODELS = [
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
]''',
    g_content
)

with open('pos/gemini_service.py', 'w', encoding='utf-8') as f:
    f.write(g_content)
print("pos/gemini_service.py updated with Gemini 2.0 Flash as primary!")

# 2. Update templates/pos/pos.html
with open('templates/pos/pos.html', 'r', encoding='utf-8') as f:
    p_content = f.read()

p_content = p_content.replace(
    'Google Gemini 1.5 Flash Vision & Voice ইন্টিগ্রেশন',
    'Google Gemini 2.0 Flash Vision & Voice ইন্টিগ্রেশন'
)
p_content = p_content.replace(
    "isAiActive ? 'Gemini 1.5 Flash সক্রিয়' : 'লোকাল স্মার্ট ইঞ্জিন চলমান'",
    "isAiActive ? 'Gemini 2.0 Flash সক্রিয় ⚡' : 'লোকাল স্মার্ট ইঞ্জিন চলমান'"
)
p_content = p_content.replace(
    '<option value="gemini">Google Gemini 1.5 Flash (সুপার নির্ভুল - রিকমেন্ডেড)</option>',
    '<option value="gemini">Google Gemini 2.0 Flash (সর্বোচ্চ নির্ভুল ও দ্রুততম ⚡ - রিকমেন্ডেড)</option>'
)

with open('templates/pos/pos.html', 'w', encoding='utf-8') as f:
    f.write(p_content)
print("templates/pos/pos.html updated with Gemini 2.0 Flash UI labels!")

