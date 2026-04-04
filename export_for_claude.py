import firebase_admin
from firebase_admin import credentials, firestore
import csv

def export_full_data():
    print("Connecting to Firestore database...")
    try:
        cred = credentials.Certificate('firebase_credentials.json')
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
        db = firestore.client()
    except Exception as e:
        print(f"Error connecting to Firebase: {e}")
        return

    print("Fetching full data records (this may take a moment)...")
    docs = db.collection('social_records').stream()
    
    output_filename = "claude_data_export.csv"
    
    headers = [
        "platform", 
        "parties_mentioned", 
        "nlp_sentiment", 
        "nlp_sentiment_score", 
        "is_kongu_related",
        "text",
        "timestamp", 
        "url"
    ]
    
    count = 0
    with open(output_filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        
        for doc in docs:
            data = doc.to_dict()
            
            # Safely format list down to string
            parties = data.get('parties_mentioned', [])
            if isinstance(parties, list):
                parties_str = ", ".join(parties)
            else:
                parties_str = str(parties)
                
            row = {
                "platform": data.get('platform', ''),
                "parties_mentioned": parties_str,
                "nlp_sentiment": data.get('nlp_sentiment', ''),
                "nlp_sentiment_score": data.get('nlp_sentiment_score', ''),
                "is_kongu_related": data.get('is_kongu_related', ''),
                "text": str(data.get('text', '')).replace('\n', ' ').replace('\r', ' '),
                "timestamp": data.get('timestamp', ''),
                "url": data.get('url', '')
            }
            writer.writerow(row)
            count += 1

    print(f"\n✅ COMPLETE! Successfully exported {count} posts to: {output_filename}")
    print("You can now open this file or upload it directly to Claude!")

if __name__ == "__main__":
    export_full_data()
