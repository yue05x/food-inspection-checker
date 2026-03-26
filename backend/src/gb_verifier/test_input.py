import re

def extract_gb_number(text: str) -> str:
    """
    Extracts the GB standard number INCLUDING year from a GB code string.
    Keeping the year ensures we search for the exact version in the report,
    not the latest version on foodmate.net.

    Example: 'GB 2763-2021'        -> '2763-2021'
             'GB/T 1234-2020'      -> '1234-2020'
             'GB 23200.113- 2018'  -> '23200.113-2018'  (normalises space)
             'GB 2763'             -> '2763'             (no year, unchanged)
    """
    if not text:
        return ""

    # Remove 'GB', 'GB/T', 'GBT' prefix
    clean_text = re.sub(r'^(?:GB/T|GB|GBT)\s*', '', text.strip(), flags=re.IGNORECASE)

    # Normalise spaces around the year-separator hyphen (e.g. "113- 2018" → "113-2018")
    clean_text = re.sub(r'\s*-\s*', '-', clean_text)

    return clean_text.strip()
