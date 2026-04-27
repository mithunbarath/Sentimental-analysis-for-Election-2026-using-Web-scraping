"""
Keyword and region filtering module.
"""

import re
import logging
from typing import List, Set, Dict, Optional

from models import SocialMediaRecord

logger = logging.getLogger(__name__)


class PartyClassifier:
    """Classifier for detecting political party mentions in text."""

    def __init__(
        self,
        dmk_keywords: Optional[List[str]] = None,
        admk_keywords: Optional[List[str]] = None,
        tvk_keywords: Optional[List[str]] = None
    ):
        """Initialize the classifier with party keywords."""
        from config import KeywordConfig
        kc = KeywordConfig.load()
        
        self.dmk_keywords = dmk_keywords or kc.parties.get("dmk") or ["dmk", "டிஎம்கே", "stalin", "ஸ்டாலின்", "udhay", "உதயநிதி"]
        self.admk_keywords = admk_keywords or kc.parties.get("admk") or ["admk", "aiadmk", "அதிமுக", "eps", "இபிஎஸ்", "ops", "ஓபிஎஸ்"]
        self.tvk_keywords = tvk_keywords or kc.parties.get("tvk") or ["tvk", "டி.வி.கே", "vijay", "விஜய்", "thalapathy"]

        self.dmk_pattern = self._compile_pattern(self.dmk_keywords)
        self.admk_pattern = self._compile_pattern(self.admk_keywords)
        self.tvk_pattern = self._compile_pattern(self.tvk_keywords)

        all_keywords = self.dmk_keywords + self.admk_keywords + self.tvk_keywords
        self.any_party_pattern = self._compile_pattern(all_keywords)

    def _compile_pattern(self, keywords: List[str]) -> re.Pattern:
        """Compile a regex pattern from a list of keywords."""
        escaped_keywords = [re.escape(kw) for kw in keywords]
        pattern = r"(?i)(?:\b|)(?:" + "|".join(escaped_keywords) + r")(?:\b|$)"
        return re.compile(pattern, re.UNICODE)

    def classify_parties(self, text: Optional[str]) -> List[str]:
        """Classify which parties are mentioned in the given text."""
        if not text:
            return []

        parties_mentioned = []

        if self.dmk_pattern.search(text):
            parties_mentioned.append("dmk")

        if self.admk_pattern.search(text):
            parties_mentioned.append("admk")

        if self.tvk_pattern.search(text):
            parties_mentioned.append("tvk")

        return parties_mentioned

    def has_any_party(self, text: Optional[str]) -> bool:
        """Check if any party is mentioned in the text."""
        if not text:
            return False
        return bool(self.any_party_pattern.search(text))


class RegionClassifier:
    """Classifier for detecting Kongu Belt and TN region relevance."""

    def __init__(
        self,
        region_keywords: Optional[List[str]] = None
    ):
        """Initialize the classifier with region keywords."""
        from config import KeywordConfig
        kc = KeywordConfig.load()

        # Core Kongu Region keywords
        self.kongu_keywords = kc.regions.get("kongu") or [
            "kongu", "கொங்கு",
            "coimbatore", "கோயம்புத்தூர்", "kovai", "கோவை",
            "tiruppur", "tirupur", "திருப்பூர்", "palladam", "பல்லடம்",
            "erode", "ஈரோடு",
            "salem", "சேலம்",
            "namakkal", "நாமக்கல்",
            "karur", "கரூர்",
            "nilgiris", "நீலகிரி", "ooty", "ஊட்டி",
            "dharmapuri", "தருமபுரி",
            "krishnagiri", "கிருஷ்ணகிரி",
            "gobi", "கோபிசெட்டிபாளையம்", "pollachi", "பொள்ளாச்சி"
        ]
        
        self.region_keywords = region_keywords or self.kongu_keywords
        self.region_pattern = self._compile_pattern(self.region_keywords)
        self.kongu_pattern = self._compile_pattern(self.kongu_keywords)

    def _compile_pattern(self, keywords: List[str]) -> re.Pattern:
        """Compile a regex pattern from region keywords."""
        escaped_keywords = [re.escape(kw) for kw in keywords]
        pattern = r"(?i)(?:\b|)(?:" + "|".join(escaped_keywords) + r")(?:\b|$)"
        return re.compile(pattern, re.UNICODE)

    def is_kongu_related(
        self,
        text: Optional[str] = None,
        source: Optional[str] = None,
        author: Optional[str] = None
    ) -> bool:
        """Determine if content belongs to the Kongu region."""
        if not text:
            return False
            
        # Match for Kongu Region
        if self.kongu_pattern.search(text):
            return True

        if source and self.region_pattern.search(source):
            return True

        if author and self.region_pattern.search(author):
            return True

        return False

    def get_relevance_score(self, text: str) -> int:
        """Calculate a relevance score for sorting purposes."""
        score = 0
        if self.kongu_pattern.search(text):
            score += 10
        elif self.region_pattern.search(text):
            score += 5
        return score


def tag_regions(records: List[SocialMediaRecord]) -> List[SocialMediaRecord]:
    """Tag each record with its Tamil Nadu district/zone using TamilNaduRegionClassifier."""
    try:
        from region_classifier import TamilNaduRegionClassifier
        classifier = TamilNaduRegionClassifier()
        for r in records:
            text_to_check = " ".join(filter(None, [r.title, r.text, r.author, r.source]))
            r.district = classifier.classify_region(text_to_check)
            if r.district in ["tiruppur", "coimbatore", "erode", "salem", "namakkal", "nilgiris", "dharmapuri", "krishnagiri"]:
                r.is_kongu_related = True
        logger.info(f"Tagged regions for {len(records)} records.")
    except Exception as e:
        logger.error(f"Region tagging failed: {e}")
    return records


def apply_filters(
    records: List[SocialMediaRecord],
    require_party_mention: bool = True,
    require_kongu_related: bool = True,
    tn_wide_mode: bool = False,
    store_all: bool = False,
    strict_mode: bool = False
) -> List[SocialMediaRecord]:
    """Apply keyword and region filters with optional strict mode."""
    if store_all:
        logger.info(f"store_all=True: Keeping all {len(records)} records without filtering.")
        return records

    filtered = []
    
    # If not in strict mode, we are more inclusive
    for record in records:
        # Party check
        if require_party_mention and not record.parties_mentioned:
            if strict_mode:
                continue
            # If search was keyword-based, it's likely relevant even if the snippet is short
            
        # Region check
        if require_kongu_related and not tn_wide_mode and not record.is_kongu_related:
            if strict_mode:
                continue
            # If not strict, we might still keep it if it's high engagement or from a tracked user
            # But for now, let's at least allow Kongu matches

        # TN-wide region check (if in TN mode, drop non-TN records if strict)
        if tn_wide_mode and record.district == "unknown":
            if strict_mode:
                continue

        filtered.append(record)

    logger.info(
        f"Filtered {len(records)} records down to {len(filtered)} "
        f"(party: {require_party_mention}, kongu: {require_kongu_related}, "
        f"tn_wide: {tn_wide_mode}, strict: {strict_mode})"
    )

    return filtered


def filter_by_timestamp(
    records: List[SocialMediaRecord],
    max_age_hours: int
) -> List[SocialMediaRecord]:
    """Filter out records older than the specified maximum age in hours."""
    if max_age_hours <= 0:
        return records
        
    from datetime import datetime, timedelta, timezone
    
    filtered = []
    now = datetime.now(timezone.utc)
    cutoff_time = now - timedelta(hours=max_age_hours)
    
    for r in records:
        if not r.timestamp:
            filtered.append(r)
            continue
            
        r_time = r.timestamp
        if r_time.tzinfo is None:
            r_time = r_time.replace(tzinfo=timezone.utc)
            
        if r_time >= cutoff_time:
            filtered.append(r)
            
    logger.info(f"Temporal filter ({max_age_hours}h max age): {len(records)} -> {len(filtered)} records returned")
    return filtered


def filter_by_date_range(
    records: List[SocialMediaRecord],
    start_date_str: str,
    end_date_str: str
) -> List[SocialMediaRecord]:
    """Filter out records outside the specified start_date and end_date range (YYYY-MM-DD)."""
    if not start_date_str and not end_date_str:
        return records
        
    from datetime import datetime, timezone
    
    start_dt = None
    end_dt = None
    
    try:
        if start_date_str:
            start_dt = datetime.strptime(start_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        if end_date_str:
            # End of the day for the end_date
            end_dt = datetime.strptime(end_date_str, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
    except ValueError as e:
        logger.error(f"Invalid date format for filter_by_date_range. Expected YYYY-MM-DD. Error: {e}")
        return records

    filtered = []
    for r in records:
        if not r.timestamp:
            filtered.append(r)
            continue
            
        r_time = r.timestamp
        if r_time.tzinfo is None:
            r_time = r_time.replace(tzinfo=timezone.utc)
            
        # Check bounds
        if start_dt and r_time < start_dt:
            continue
        if end_dt and r_time > end_dt:
            continue
            
        filtered.append(r)
        
    logger.info(f"Date range filter ({start_date_str} to {end_date_str}): {len(records)} -> {len(filtered)} records returned")
    return filtered