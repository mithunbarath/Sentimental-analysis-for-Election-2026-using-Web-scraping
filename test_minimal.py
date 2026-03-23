"""
Minimal test script for the Palladam Politics Scraper core components.
"""

import sys
import logging
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from config import Config, load_config
from models import SocialMediaRecord
from filters import PartyClassifier, RegionClassifier
from deduplication import DeduplicationManager, merge_deduplicated_datasets

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_config():
    logger.info("Testing configuration...")
    config = load_config()
    assert config is not None
    assert hasattr(config, "instagram")
    assert hasattr(config, "filters")
    logger.info("Configuration test passed.")

def test_models():
    logger.info("Testing models...")
    record = SocialMediaRecord(
        platform="instagram",
        type="post",
        id="test_id",
        author="test_author",
        text="This is a test post about DMK in Palladam.",
        timestamp=datetime.now(),
        parties_mentioned=["dmk"],
        is_palladam_related=True
    )
    row = record.to_csv_row()
    assert row["platform"] == "instagram"
    assert row["parties_mentioned"] == "dmk"
    assert row["is_palladam_related"] == "True"
    logger.info("Models test passed.")

def test_filters():
    logger.info("Testing filters...")
    party_classifier = PartyClassifier()
    region_classifier = RegionClassifier()

    text = "Vote for ADMK in Tiruppur!"
    parties = party_classifier.classify_parties(text)
    assert "admk" in parties
    
    is_palladam = region_classifier.is_palladam_related(text=text)
    assert is_palladam is True  # Tiruppur is in region_keywords

    text2 = "Something unrelated."
    assert not party_classifier.classify_parties(text2)
    assert not region_classifier.is_palladam_related(text=text2)
    
    logger.info("Filters test passed.")

def test_deduplication():
    logger.info("Testing deduplication...")
    # Initialize without storage for clean test
    manager = DeduplicationManager(use_hash_deduplication=True)
    
    record1 = SocialMediaRecord(
        platform="twitter",
        type="post",
        id="123",
        text="Duplicate text"
    )
    record2 = SocialMediaRecord(
        platform="facebook",
        type="post",
        id="456",
        text="Duplicate text"
    )
    
    # Test basic ID deduplication
    assert not manager.is_duplicate(record1)
    manager.add_record(record1)
    
    record3 = SocialMediaRecord(
        platform="twitter",
        type="post",
        id="123",
        text="New text"
    )
    assert manager.is_duplicate(record3)
    
    logger.info("Testing merge_deduplicated_datasets...")
    dataset1 = [record1]
    dataset2 = [record1, record2]
    
    # Use a fresh manager via the merge function
    merged = merge_deduplicated_datasets([dataset1, dataset2])
    
    # Dataset 1: [record1] -> added
    # Dataset 2: [record1, record2] -> record1 is dup, record2 is added
    assert len(merged) == 2
    assert merged[0].id == "123"
    assert merged[1].id == "456"
    
    logger.info("Deduplication test passed.")

def run_all_tests():
    try:
        test_config()
        test_models()
        test_filters()
        test_deduplication()
        logger.info("=" * 50)
        logger.info("All minimal tests passed!")
        logger.info("=" * 50)
    except Exception as e:
        logger.error(f"Tests failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    run_all_tests()
