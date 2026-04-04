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
    Pushes scraped records to Firebase Firestore, separating posts and comments.
    """
    if not firebase_config.enabled or not firebase_config.credentials_path:
        return None

    db = _get_firestore_client(firebase_config.credentials_path)
    if not db:
        return None

    try:
        posts = [r for r in records if r.type == 'post']
        comments = [r for r in records if r.type == 'comment']

        total_written = 0

        def _batch_upload(item_list, target_collection: str):
            if not item_list:
                return 0
            
            collection_ref = db.collection(target_collection)
            batch = db.batch()
            count = 0
            local_total = 0

            for record in item_list:
                doc_ref = collection_ref.document(record.id)
                batch.set(doc_ref, record.to_dict(), merge=True)
                count += 1
                
                if count == 500:
                    batch.commit()
                    local_total += count
                    batch = db.batch()
                    count = 0
                    
            if count > 0:
                batch.commit()
                local_total += count
            
            logger.info(f"Firebase Sync: {local_total} records pushed to '{target_collection}'")
            return local_total

        # Upload Posts
        if posts:
            total_written += _batch_upload(posts, firebase_config.collection_name)
            
        # Upload Comments
        if comments:
            comments_collection = f"{firebase_config.collection_name}_comments"
            total_written += _batch_upload(comments, comments_collection)

        return total_written

    except Exception as e:
        logger.error(f"Firebase export failed: {e}")
        return None
