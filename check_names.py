import requests, json, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
r = requests.get(
    'https://adhahi.dz/api/v1/public/wilaya-quotas',
    headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://adhahi.dz/register'},
    timeout=30
)
d = r.json()
targets = ['02', '09', '10', '15', '16', '26', '35', '42', '44']
for w in d:
    code = w.get('wilayaCode', '')
    if code in targets:
        print(f"{code}: FR='{w['wilayaNameFr']}' | AR='{w['wilayaNameAr']}'")
