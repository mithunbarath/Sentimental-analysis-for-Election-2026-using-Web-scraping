import firebase_admin
from firebase_admin import credentials, firestore
from collections import defaultdict

def generate_report():
    print("Connecting to Firestore database...")
    try:
        cred = credentials.Certificate('firebase_credentials.json')
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
        db = firestore.client()
    except Exception as e:
        print(f"Error connecting to Firebase: {e}\nEnsure your firebase_credentials.json is correct.")
        return

    print("Fetching data (this may take a few seconds)...")
    try:
        docs = db.collection('kongu_social_monitoring').stream()
    except Exception as e:
        print(f"Error fetching data: {e}")
        return
        
    platforms = defaultdict(int)
    parties = defaultdict(int)
    party_sentiment = defaultdict(lambda: {'positive': 0, 'negative': 0, 'neutral': 0})
    
    total_docs = 0
    total_party_mentions = 0

    for doc in docs:
        data = doc.to_dict()
        total_docs += 1
        
        # Platform proportions
        plat = data.get('platform', 'unknown')
        platforms[plat] += 1
        
        # Party Mentions
        mentioned = data.get('parties_mentioned', [])
        if isinstance(mentioned, str): 
            mentioned = [m.strip() for m in mentioned.split(',') if m.strip()]
                
        # Sentiment
        sentiment = str(data.get('nlp_sentiment', 'neutral')).strip().lower()
        if sentiment not in ['positive', 'negative', 'neutral']:
            sentiment = 'neutral'
            
        for party in mentioned:
            p = party.upper()
            if p:
                parties[p] += 1
                total_party_mentions += 1
                party_sentiment[p][sentiment] += 1

    if total_docs == 0:
        print("\nNo data found in the database yet!")
        return

    # Print the report without any absolute post numbers!
    print("\n" + "="*60)
    print(" 📊 KONGU POLITICAL INTELLIGENCE REPORT (Relative Metrics)")
    print("="*60)
    
    print("\n🌐 PLATFORM DISTRIBUTION:")
    for p, count in sorted(platforms.items(), key=lambda x: x[1], reverse=True):
        pct = (count / total_docs) * 100
        print(f"  • {p.capitalize():12} : {pct:>5.1f}%")

    if total_party_mentions > 0:
        print("\n🗣️ PARTY SHARE OF VOICE:")
        for p, count in sorted(parties.items(), key=lambda x: x[1], reverse=True):
             pct = (count / total_party_mentions) * 100
             print(f"  • {p:12} : {pct:>5.1f}%")
             
        print("\n🎭 SENTIMENT BREAKDOWN PER PARTY:")
        for p, counts in sorted(party_sentiment.items(), key=lambda x: sum(x[1].values()), reverse=True):
            total_for_party = sum(counts.values())
            if total_for_party > 0:
                pos = (counts['positive'] / total_for_party) * 100
                neg = (counts['negative'] / total_for_party) * 100
                neu = (counts['neutral'] / total_for_party) * 100
                print(f"  • {p:10} | Positive: {pos:>5.1f}% | Negative: {neg:>5.1f}% | Neutral: {neu:>5.1f}%")
    else:
        print("\n🗣️ No party-specific sentiment data collected yet.")
        
    print("\n" + "="*60)

if __name__ == "__main__":
    generate_report()
