import requests

resp = requests.get('https://loot.farm/fullpriceRUST.json', timeout=30)
items = resp.json()

print(f"Total items: {len(items)}")
print("\nSearching for Santa Chest Plate...")

for item in items:
    if 'santa' in item['name'].lower() and 'chest' in item['name'].lower():
        print(f"\nName: {item['name']}")
        print(f"Price: ${item['price']/100:.2f}")
        print(f"Have: {item['have']} (у ботов)")
        print(f"Max: {item['max']} (лимит)")
        print(f"Rate: {item['rate']}")
