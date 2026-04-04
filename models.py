"""
Data models for the Palladam Politics Scraper.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum


class Platform(str, Enum):
    """Supported social media platforms."""
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    YOUTUBE = "youtube"
    TWITTER = "twitter"


class ContentType(str, Enum):
    """Types of content collected."""
    POST = "post"
    COMMENT = "comment"


@dataclass
class SocialMediaRecord:
    """Unified data model for social media posts and comments."""

    platform: str
    type: str
    id: str
    parent_id: Optional[str] = None
    url: Optional[str] = None
    author: Optional[str] = None
    text: Optional[str] = None
    title: Optional[str] = None
    like_count: Optional[int] = None
    reaction_count: Optional[int] = None
    view_count: Optional[int] = None
    retweet_count: Optional[int] = None
    reply_count: Optional[int] = None
    comment_count: Optional[int] = None
    source: Optional[str] = None
    timestamp: Optional[datetime] = None
    parties_mentioned: List[str] = field(default_factory=list)
    is_kongu_related: bool = False
    raw_data: Optional[Dict[str, Any]] = field(default=None)
    # NLP enrichment fields (populated by nlp_pipeline.py)
    nlp_sentiment: Optional[str] = None        # e.g. "positive", "neutral", "negative"
    nlp_sentiment_score: Optional[float] = None # 0.0–1.0 confidence
    nlp_trend_score: Optional[float] = None    # relative frequency vs rolling window
    district: Optional[str] = None  # Added for District classification

    def to_dict(self) -> Dict[str, Any]:
        """Convert the record to a dictionary."""
        result = asdict(self)
        if result["timestamp"] is not None:
            result["timestamp"] = result["timestamp"].isoformat()
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SocialMediaRecord":
        """Create a record from a dictionary."""
        if data.get("timestamp") and isinstance(data["timestamp"], str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)

    def to_csv_row(self) -> Dict[str, str]:
        """Convert record to a flat dictionary for CSV export."""
        return {
            "platform": self.platform,
            "type": self.type,
            "id": self.id or "",
            "parent_id": self.parent_id or "",
            "url": self.url or "",
            "author": self.author or "",
            "title": self.title or "",
            "text": (self.text or "").replace("\n", " ").replace("\r", " "),
            "like_count": str(self.like_count) if self.like_count is not None else "",
            "reaction_count": str(self.reaction_count) if self.reaction_count is not None else "",
            "view_count": str(self.view_count) if self.view_count is not None else "",
            "retweet_count": str(self.retweet_count) if self.retweet_count is not None else "",
            "reply_count": str(self.reply_count) if self.reply_count is not None else "",
            "comment_count": str(self.comment_count) if self.comment_count is not None else "",
            "source": self.source or "",
            "timestamp": self.timestamp.isoformat() if self.timestamp else "",
            "parties_mentioned": ",".join(self.parties_mentioned) if self.parties_mentioned else "",
            "is_kongu_related": str(self.is_kongu_related),
            "nlp_sentiment": self.nlp_sentiment or "",
            "nlp_sentiment_score": str(self.nlp_sentiment_score) if self.nlp_sentiment_score is not None else "",
            "nlp_trend_score": str(self.nlp_trend_score) if self.nlp_trend_score is not None else "",
            "district": self.district or ""
        }

    @classmethod
    def get_csv_headers(cls) -> List[str]:
        """Get the headers for CSV export."""
        return [
            "platform", "type", "id", "parent_id", "url", "author", "title", "text",
            "like_count", "reaction_count", "view_count", "retweet_count",
            "reply_count", "comment_count", "source", "timestamp",
            "parties_mentioned", "is_kongu_related",
            "nlp_sentiment", "nlp_sentiment_score", "nlp_trend_score",
            "district"
        ]


@dataclass
class InstagramPost:
    """Raw Instagram post data before normalization."""
    post_id: str
    url: str
    author: Optional[str] = None
    caption: Optional[str] = None
    timestamp: Optional[datetime] = None
    like_count: Optional[int] = None
    comment_count: Optional[int] = None
    source: Optional[str] = None
    raw_data: Optional[Dict[str, Any]] = None


@dataclass
class InstagramComment:
    """Raw Instagram comment data before normalization."""
    comment_id: str
    post_id: str
    post_url: Optional[str] = None
    author: Optional[str] = None
    text: Optional[str] = None
    timestamp: Optional[datetime] = None
    like_count: Optional[int] = None
    raw_data: Optional[Dict[str, Any]] = None


@dataclass
class FacebookPost:
    """Raw Facebook post data before normalization."""
    post_id: str
    url: str
    author: Optional[str] = None
    text: Optional[str] = None
    timestamp: Optional[datetime] = None
    reaction_count: Optional[int] = None
    comment_count: Optional[int] = None
    source: Optional[str] = None
    raw_data: Optional[Dict[str, Any]] = None


@dataclass
class FacebookComment:
    """Raw Facebook comment data before normalization."""
    comment_id: str
    post_id: str
    post_url: Optional[str] = None
    author: Optional[str] = None
    text: Optional[str] = None
    timestamp: Optional[datetime] = None
    reaction_count: Optional[int] = None
    raw_data: Optional[Dict[str, Any]] = None


@dataclass
class YouTubeVideo:
    """Raw YouTube video data before normalization."""
    video_id: str
    url: str
    title: Optional[str] = None
    description: Optional[str] = None
    timestamp: Optional[datetime] = None
    view_count: Optional[int] = None
    like_count: Optional[int] = None
    comment_count: Optional[int] = None
    source: Optional[str] = None
    raw_data: Optional[Dict[str, Any]] = None


@dataclass
class YouTubeComment:
    """Raw YouTube comment data before normalization."""
    comment_id: str
    video_id: str
    video_url: Optional[str] = None
    author: Optional[str] = None
    text: Optional[str] = None
    timestamp: Optional[datetime] = None
    like_count: Optional[int] = None
    raw_data: Optional[Dict[str, Any]] = None


@dataclass
class TwitterTweet:
    """Raw Twitter tweet data before normalization."""
    tweet_id: str
    url: str
    author: Optional[str] = None
    display_name: Optional[str] = None
    text: Optional[str] = None
    timestamp: Optional[datetime] = None
    retweet_count: Optional[int] = None
    reply_count: Optional[int] = None
    like_count: Optional[int] = None
    quote_count: Optional[int] = None
    source: str = "twitter_search"
    raw_data: Optional[Dict[str, Any]] = None


@dataclass
class TwitterReply:
    """Raw Twitter reply data before normalization."""
    reply_id: str
    parent_tweet_id: str
    parent_tweet_url: Optional[str] = None
    author: Optional[str] = None
    display_name: Optional[str] = None
    text: Optional[str] = None
    timestamp: Optional[datetime] = None
    like_count: Optional[int] = None
    raw_data: Optional[Dict[str, Any]] = None