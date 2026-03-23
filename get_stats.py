
import csv
from collections import Counter

file_path = r'c:\Users\navee\Downloads\claude-brightdata-scraper\output\palladam_politics_data.csv'
try:
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        platforms = [row['platform'] for row in reader]
        counts = Counter(platforms)
        print("Platform Distribution:")
        for platform, count in counts.items():
            print(f"  {platform}: {count}")
        print(f"Total Records: {len(platforms)}")
except Exception as e:
    print(f"Error reading CSV: {e}")
