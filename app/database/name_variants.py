import re
import unicodedata

def remove_diacritics(text):
    normalized = unicodedata.normalize('NFKD', text)
    return ''.join([c for c in normalized if not unicodedata.combining(c)])

def turkish_soundex(name):
    name = remove_diacritics(name).lower()
    name = re.sub(r"[^a-z]", "", name)
    if not name:
        return ""
    first_letter = name[0]
    mapping = {
        "b": "1", "p": "1", "f": "1", "v": "1", "m": "1",
        "c": "2", "ç": "2", "s": "2", "z": "2", "j": "2", "ş": "2",
        "d": "3", "t": "3", "n": "3",
        "l": "4", "r": "4",
        "g": "5", "k": "5", "ğ": "5", "h": "5", "y": "5"
    }
    vowels = set("aeıioöuü")
    codes = []
    prev_code = None
    for letter in name[1:]:
        if letter in vowels:
            code = ""
        else:
            code = mapping.get(letter, "")
        if code and code != prev_code:
            codes.append(code)
            prev_code = code
    result = first_letter.upper() + "".join(codes[:3])
    while len(result) < 4:
        result += "0"
    return result

def get_name_variants(name: str):
    # Basit bir varyant üretimi: isimden diakritik işaretleri kaldırıp küçük harfe çevirir.
    name_clean = remove_diacritics(name).lower()
    variants = [name_clean]
    # İsteğe bağlı olarak ek varyantlar üretilebilir.
    return list(set(variants))

def find_context_matches(name, text, window_size=100):
    """İsmin geçtiği bağlamı analiz eder"""
    matches = []
    text_lower = text.lower()
    name_variants = get_name_variants(name)
    for variant in name_variants:
        start_pos = 0
        while True:
            pos = text_lower.find(variant, start_pos)
            if pos == -1:
                break
            # Bağlam penceresini belirle
            start = max(0, pos - window_size)
            end = min(len(text), pos + len(variant) + window_size)
            context = text[start:end]
            # Tarihler (yıl) için örnek bir regex
            years = re.findall(r'\b(1[0-9]{3}|20[0-2][0-9])\b', context)
            # Unvanları yakalamak için, örneğin boş bir liste veriyoruz;
            # ihtiyaç duyarsanız buraya unvan listesini ekleyin.
            titles = []
            matches.append({
                "variant": variant,
                "context": context,
                "years": years,
                "titles": titles
            })
            start_pos = pos + len(variant)
    return matches