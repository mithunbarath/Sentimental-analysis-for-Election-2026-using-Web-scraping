import sys
from bs4 import BeautifulSoup
import re

print("Loading 8MB HTML...")
with open("facebook_debug.html", "r", encoding="utf-8") as f:
    html = f.read()

soup = BeautifulSoup(html, "html.parser")
print("Parsed HTML!")

selectors_to_test = [
    'div[data-ad-comet-preview="message"]',
    'div[dir="auto"]',
    'div[role="article"]',
    'div[data-ad-preview="message"]'
]

for sel in selectors_to_test:
    elements = soup.select(sel)
    print(f"Selector '{sel}': found {len(elements)} elements")
    
    if len(elements) > 0 and len(elements) < 100:
        print("Sample 1:")
        print(elements[0].get_text(strip=True)[:200])
        if len(elements) > 1:
            print("Sample 2:")
            print(elements[1].get_text(strip=True)[:200])
    print("-" * 40)
