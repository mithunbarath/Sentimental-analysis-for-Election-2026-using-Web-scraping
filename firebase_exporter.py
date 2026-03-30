"""
Firebase Firestore exporter module for the Palladam Politics Scraper.
"""

import logging
from typing import List, Dict, Any, Optional
from models import SocialMediaRecord

logger = logging.getLogger(__name__)

try:
    import firebase_admin
    from firebase_admin import credentials, firestore
except ImportError:
    logger.error("firebase-admin package is missing. Run: pip install firebase-admin")
    firebase_admin = None
    firestore = None


_db = None

def _get_firestore_client(cred_path: str):
    global _db
    if _db is not None:
        return _db
    
    if not firebase_admin or not firestore:
        return None
        
    try:
        if not firebase_admin._apps:
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
        _db = firestore.client()
        return _db
    except Exception as e:
        logger.error(f"Failed to initialize Firebase Admin SDK: {e}")
        return None

def export_to_firestore(records: List[SocialMediaRecord], firebase_config) -> Optional[int]:
    """
    Pushes scraped records to Firebase Firestore.
    """
    if not firebase_config.enabled or not firebase_config.credentials_path:
        return None

    db = _get_firestore_client(firebase_config.credentials_path)
    if not db:
        return None

    try:
        collection_ref = db.collection(firebase_config.collection_name)
        
        # Firestore batch operations can process up to 500 documents at a time
        batch = db.batch()
        count = 0
        total_written = 0
        
        for record in records:
            # We use the record.id as the document ID for absolute uniqueness to deduplicate 
            # posts natively at the database level!
            doc_ref = collection_ref.document(record.id)
            
            # Use set() with merge=True to update interactions/likes continuously 
            # without erasing historical sentiment tags
            batch.set(doc_ref, record.to_dict(), merge=True)
            count += 1
            
            if count == 500:
                batch.commit()
                total_written += count
                batch = db.batch()
                count = 0
                
        if count > 0:
            batch.commit()
            total_written += count

        logger.info(f"Firebase Export Complete: {total_written} records synced to Firestore '{firebase_config.collection_name}' collection.")
        return total_written

    except Exception as e:
        logger.error(f"Firebase export failed: {e}")
        return None
