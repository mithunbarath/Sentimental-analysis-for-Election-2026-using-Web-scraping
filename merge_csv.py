import os
import csv
import glob
import argparse

def merge_csvs(output_dir='output', merged_name='merged_all_scraped_data.csv'):
    csv_files = glob.glob(os.path.join(output_dir, '*.csv'))
    
    # Exclude the output file itself so we don't infinitely append
    csv_files = [f for f in csv_files if not f.endswith(merged_name)]
    
    if not csv_files:
        print("No CSV files found in the output directory.")
        return

    print(f"Found {len(csv_files)} CSV files. Merging...")
    
    all_records = {} # Map of ID -> Record
    header_set = set()
    
    for file in csv_files:
        try:
            with open(file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                # Capture headers from all files
                if reader.fieldnames:
                    header_set.update(reader.fieldnames)
                
                for row in reader:
                    # Deduplicate by post ID if it exists, otherwise just store it
                    row_id = row.get("id", str(len(all_records)))
                    
                    # Store row
                    all_records[row_id] = row
        except Exception as e:
            print(f"Could not read {file}: {e}")
            
    if not header_set:
        print("No valid CSV data found.")
        return
        
    # Sort headers so the output is consistent
    headers = sorted(list(header_set))
        
    output_path = os.path.join(output_dir, merged_name)
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=headers, restval='', extrasaction='ignore')
        writer.writeheader()
        for record in all_records.values():
            writer.writerow(record)
            
    print(f"\n✅ Merged {len(all_records)} unique records into: {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--dir', type=str, default='output')
    args = parser.parse_args()
    merge_csvs(args.dir)
