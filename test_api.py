import requests, json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
r = requests.get(
    'https://adhahi.dz/api/v1/public/wilaya-quotas',
    headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://adhahi.dz/register', 'Origin': 'https://adhahi.dz'},
    timeout=30
)
d = r.json()
print(f"Total wilayas: {len(d)}")
print(f"\nSample keys: {list(d[0].keys())}")
print(f"\nSample entry:\n{json.dumps(d[0], indent=2, ensure_ascii=False)}")
print("\n--- TARGET WILAYAS ---")
for w in d:
    code = w.get('wilayaCode', '')
    if code in ['16', '09', '15']:
        print(f"  Code {code}: {w.get('wilayaNameFr', '?')} -> available={w.get('available', False)}")
print("\n--- ALL AVAILABLE ---")
avail = [w for w in d if w.get('available')]
if avail:
    for w in avail:
        print(f"  Code {w.get('wilayaCode','?')}: {w.get('wilayaNameFr','?')}")
else:
    print("  None available")
