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
        self.dmk_keywords = dmk_keywords or ["dmk", "டிஎம்கே", "stalin", "ஸ்டாலின்", "udhay", "உதயநிதி"]
        self.admk_keywords = admk_keywords or ["admk", "aiadmk", "அதிமுக", "eps", "இபிஎஸ்", "ops", "ஓபிஎஸ்"]
        self.tvk_keywords = tvk_keywords or ["tvk", "டி.வி.கே", "vijay", "விஜய்", "thalapathy"]

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
    """Classifier for detecting Palladam and TN region relevance."""

    def __init__(
        self,
        region_keywords: Optional[List[str]] = None
    ):
        """Initialize the classifier with region keywords."""
        # Core Palladam keywords
        self.palladam_keywords = ["palladam", "பல்லடம்"]
        
        # Related regions (Tiruppur district)
        self.related_keywords = [
            "tiruppur", "tirupur", "\u0ba4\u0bbf\u0bb0\u0bc1\u0baa\u0bcd\u0baa\u0bc2\u0bb0\u0bcd", 
            "kangeyam", "\u0b95\u0bbe\u0b99\u0bcd\u0b95\u0bc7\u0baf\u0bae\u0bcd",
            "dharapuram", "\u0ba4\u0bbe\u0bb0\u0bbe\u0baa\u0bc1\u0bb0\u0bae\u0bcd",
            "avanashi", "\u0b85\u0bb5\u0ba3\u0bbe\u0b9a\u0bbf"
        ]
        
        self.region_keywords = region_keywords or (self.palladam_keywords + self.related_keywords)
        self.region_pattern = self._compile_pattern(self.region_keywords)
        self.palladam_pattern = self._compile_pattern(self.palladam_keywords)

    def _compile_pattern(self, keywords: List[str]) -> re.Pattern:
        """Compile a regex pattern from region keywords."""
        escaped_keywords = [re.escape(kw) for kw in keywords]
        pattern = r"(?i)(?:\b|)(?:" + "|".join(escaped_keywords) + r")(?:\b|$)"
        return re.compile(pattern, re.UNICODE)

    def is_palladam_related(
        self,
        text: Optional[str] = None,
        source: Optional[str] = None,
        author: Optional[str] = None
    ) -> bool:
        """Determine if content is Palladam-related (directly or indirectly)."""
        if not text:
            return False
            
        # Direct match for Palladam
        if self.palladam_pattern.search(text):
            return True
            
        # Indirect match (Tiruppur district)
        if self.region_pattern.search(text):
            return True

        if source and self.region_pattern.search(source):
            return True

        if author and self.region_pattern.search(author):
            return True

        return False

    def get_relevance_score(self, text: str) -> int:
        """Calculate a relevance score for sorting purposes."""
        score = 0
        if self.palladam_pattern.search(text):
            score += 10
        elif self.region_pattern.search(text):
            score += 5
        return score


def apply_filters(
    records: List[SocialMediaRecord],
    require_party_mention: bool = True,
    require_palladam_related: bool = True,
    strict_mode: bool = False
) -> List[SocialMediaRecord]:
    """Apply keyword and region filters with optional strict mode."""
    filtered = []
    
    # If not in strict mode, we are more inclusive
    for record in records:
        # Party check
        if require_party_mention and not record.parties_mentioned:
            if strict_mode:
                continue
            # If search was keyword-based, it's likely relevant even if the snippet is short
            
        # Region check
        if require_palladam_related and not record.is_palladam_related:
            if strict_mode:
                continue
            # If not strict, we might still keep it if it's high engagement or from a tracked user
            # But for now, let's at least allow Tiruppur matches

        filtered.append(record)

    logger.info(
        f"Filtered {len(records)} records down to {len(filtered)} "
        f"(party: {require_party_mention}, palladam: {require_palladam_related}, strict: {strict_mode})"
    )

    return filtered