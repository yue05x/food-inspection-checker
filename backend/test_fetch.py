import sys
sys.path.insert(0, './src')
from gb_verifier.runner import fetch_and_update_from_detail_page
import json

parsed = {
    'foodmate_detail_page_url': 'https://down.foodmate.net/standard/sort/3/53165.html',
    'gb_number': '23200.113'
}

success, err, html = fetch_and_update_from_detail_page(parsed, '23200.113')
print('SUCCESS:', success)
print('ERR:', err)
print('PARSED:', json.dumps(parsed, ensure_ascii=False))

with open('test_html.html', 'w', encoding='utf-8') as f:
    if html:
        f.write(html)
