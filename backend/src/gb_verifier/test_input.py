import re

def extract_gb_number(text: str) -> str:
    """
    Extracts the GB number from a string.
    Example: 'GB 2763-2021' -> '2763'
             'GB/T 1234-2020' -> '1234'
    """
    if not text:
        return ""
        
    # Remove 'GB' or 'GB/T' or 'GBT' prefix case insensitive
    clean_text = re.sub(r'^(?:GB/T|GB|GBT)\s*', '', text.strip(), flags=re.IGNORECASE)
    
    # Remove year if present (-20xx)
    clean_text = re.split(r'-\d{4}', clean_text)[0]
    
    return clean_text.strip()
