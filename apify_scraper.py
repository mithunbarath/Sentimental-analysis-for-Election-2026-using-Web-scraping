"""
Apify-based scraper for all 4 platforms.

Uses Apify's pre-built actors to scrape posts AND comments without requiring
login sessions on the VM. Falls back gracefully if the API limit is hit.

Actors used:
  - Instagram: apify/instagram-scraper
  - Facebook:  apify/facebook-pages-scraper
  - Twitter:   apify/twitter-scraper
  - YouTube:   apify/youtube-scraper

Usage:
  from apify_scraper import scrape_with_apify
  records = scrape_with_apify("instagram", ["palladam", "dmk"], config)
"""

import logging
import os
from datetime import datetime
from typing import List, Optional

from models import SocialMediaRecord

logger = logging.getLogger(__name__)


def _get_client(api_token: Optional[str] = None):
    """Build Apify client, raising ImportError if package missing."""
    try:
        from apify_client import ApifyClient
    except ImportError:
        raise ImportError(
            "apify-client not installed. Run: pip install apify-client"
        )
    token = api_token or os.getenv("APIFY_API_TOKEN", "")
    if not token:
        raise ValueError(
            "No Apify API token. Set APIFY_API_TOKEN env var or apify.api_token in config."
        )
    return ApifyClient(token)


# ── Record normalisation helpers ─────────────────────────────────────────────

def _norm_instagram(item: dict, keyword: str) -> List[SocialMediaRecord]:
    """Normalise one Apify instagram-scraper result item (post + comments)."""
    records = []
    post_id = item.get("id") or item.get("shortCode", "")
    ts_str = item.get("timestamp") or item.get("takenAt") or ""
    try:
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00")) if ts_str else None
    except Exception:
        ts = None

    post = SocialMediaRecord(
        platform="instagram",
        type="post",
        id=post_id,
        url=item.get("url") or f"https://www.instagram.com/p/{item.get('shortCode', '')}",
        author=item.get("ownerUsername") or item.get("owner", {}).get("username"),
        text=item.get("caption") or "",
        like_count=item.get("likesCount"),
        comment_count=item.get("commentsCount"),
        timestamp=ts,
        source=f"apify_instagram_{keyword}",
        parties_mentioned=[],
        is_kongu_related="palladam" in (item.get("caption") or "").lower()
    )
    records.append(post)

    # Comments
    for c in item.get("latestComments", []):
        c_ts_str = c.get("timestamp", "")
        try:
            c_ts = datetime.fromisoformat(c_ts_str.replace("Z", "+00:00")) if c_ts_str else None
        except Exception:
            c_ts = None
        comment = SocialMediaRecord(
            platform="instagram",
            type="comment",
            id=c.get("id", ""),
            parent_id=post_id,
            url=post.url,
            author=c.get("ownerUsername"),
            text=c.get("text", ""),
            like_count=c.get("likesCount"),
            timestamp=c_ts,
            source=f"apify_instagram_{keyword}",
            parties_mentioned=[],
            is_kongu_related="palladam" in c.get("text", "").lower()
        )
        records.append(comment)

    return records


def _norm_facebook(item: dict, keyword: str) -> List[SocialMediaRecord]:
    records = []
    post_id = item.get("postId") or item.get("id", "")
    ts_str = item.get("time") or item.get("timestamp") or ""
    try:
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00")) if ts_str else None
    except Exception:
        ts = None

    post = SocialMediaRecord(
        platform="facebook",
        type="post",
        id=post_id,
        url=item.get("url") or item.get("link", ""),
        author=item.get("pageName") or item.get("authorName"),
        text=item.get("text") or item.get("message", ""),
        reaction_count=item.get("likes") or item.get("reactions"),
        comment_count=item.get("commentsCount"),
        timestamp=ts,
        source=f"apify_facebook_{keyword}",
        parties_mentioned=[],
        is_kongu_related="palladam" in (item.get("text") or "").lower()
    )
    records.append(post)

    for c in item.get("comments", []):
        c_ts_str = c.get("date", "")
        try:
            c_ts = datetime.fromisoformat(c_ts_str.replace("Z", "+00:00")) if c_ts_str else None
        except Exception:
            c_ts = None
        comment = SocialMediaRecord(
            platform="facebook",
            type="comment",
            id=c.get("commentId", ""),
            parent_id=post_id,
            url=post.url,
            author=c.get("authorName"),
            text=c.get("text", ""),
            reaction_count=c.get("reactions"),
            timestamp=c_ts,
            source=f"apify_facebook_{keyword}",
            parties_mentioned=[],
            is_kongu_related="palladam" in c.get("text", "").lower()
        )
        records.append(comment)

    return records


def _norm_twitter(item: dict, keyword: str) -> List[SocialMediaRecord]:
    records = []
    tweet_id = item.get("id") or item.get("tweetId", "")
    ts_str = item.get("createdAt") or item.get("created_at", "")
    try:
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00")) if ts_str else None
    except Exception:
        ts = None

    tweet = SocialMediaRecord(
        platform="twitter",
        type="post",
        id=tweet_id,
        url=item.get("url") or f"https://x.com/i/web/status/{tweet_id}",
        author=item.get("author", {}).get("userName") or item.get("userName"),
        text=item.get("text") or item.get("full_text", ""),
        like_count=item.get("likeCount"),
        retweet_count=item.get("retweetCount"),
        reply_count=item.get("replyCount"),
        timestamp=ts,
        source=f"apify_twitter_{keyword}",
        parties_mentioned=[],
        is_kongu_related="palladam" in (item.get("text") or "").lower()
    )
    records.append(tweet)

    for r in item.get("replies", []):
        r_ts_str = r.get("createdAt", "")
        try:
            r_ts = datetime.fromisoformat(r_ts_str.replace("Z", "+00:00")) if r_ts_str else None
        except Exception:
            r_ts = None
        reply = SocialMediaRecord(
            platform="twitter",
            type="comment",
            id=r.get("id", ""),
            parent_id=tweet_id,
            url=tweet.url,
            author=r.get("author", {}).get("userName"),
            text=r.get("text", ""),
            like_count=r.get("likeCount"),
            timestamp=r_ts,
            source=f"apify_twitter_{keyword}",
            parties_mentioned=[],
            is_kongu_related="palladam" in r.get("text", "").lower()
        )
        records.append(reply)

    return records


def _norm_youtube(item: dict, keyword: str) -> List[SocialMediaRecord]:
    records = []
    video_id = item.get("id") or item.get("videoId", "")
    ts_str = item.get("date") or item.get("publishedAt", "")
    try:
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00")) if ts_str else None
    except Exception:
        ts = None

    video = SocialMediaRecord(
        platform="youtube",
        type="post",
        id=video_id,
        url=item.get("url") or f"https://www.youtube.com/watch?v={video_id}",
        title=item.get("title"),
        text=item.get("description", ""),
        view_count=item.get("viewCount"),
        like_count=item.get("likes"),
        comment_count=item.get("commentsCount"),
        timestamp=ts,
        source=f"apify_youtube_{keyword}",
        parties_mentioned=[],
        is_kongu_related="palladam" in (item.get("title") or "").lower()
    )
    records.append(video)

    for c in item.get("comments", []):
        c_ts_str = c.get("date", "")
        try:
            c_ts = datetime.fromisoformat(c_ts_str.replace("Z", "+00:00")) if c_ts_str else None
        except Exception:
            c_ts = None
        comment = SocialMediaRecord(
            platform="youtube",
            type="comment",
            id=c.get("id", ""),
            parent_id=video_id,
            url=video.url,
            author=c.get("authorText"),
            text=c.get("text", ""),
            like_count=c.get("likes"),
            timestamp=c_ts,
            source=f"apify_youtube_{keyword}",
            parties_mentioned=[],
            is_kongu_related="palladam" in c.get("text", "").lower()
        )
        records.append(comment)

    return records


# ── Actor run helpers ─────────────────────────────────────────────────────────

_NORMALISE = {
    "instagram": _norm_instagram,
    "facebook": _norm_facebook,
    "twitter": _norm_twitter,
    "youtube": _norm_youtube,
}


def _run_actor(client, actor_id: str, run_input: dict, max_items: int) -> list:
    """Run an Apify actor synchronously and return items."""
    run = client.actor(actor_id).call(run_input=run_input)
    items = []
    for item in client.dataset(run["defaultDatasetId"]).iterate_items():
        items.append(item)
        if max_items and len(items) >= max_items:
            break
    return items


def scrape_with_apify(
    platform: str,
    keywords: List[str],
    apify_config,
) -> List[SocialMediaRecord]:
    """
    Scrape posts + comments for ``platform`` using an Apify actor.

    Args:
        platform:      One of instagram | facebook | twitter | youtube
        keywords:      Search keywords / hashtags
        apify_config:  ApifyConfig dataclass instance

    Returns:
        List of SocialMediaRecord (posts + comments)
    """
    if not apify_config.enabled:
        return []

    try:
        client = _get_client(apify_config.api_token)
    except (ImportError, ValueError) as e:
        logger.warning(f"Apify client unavailable: {e}")
        return []

    max_items = apify_config.max_items_per_run
    comments_per = apify_config.comments_per_post
    records: List[SocialMediaRecord] = []
    norm_fn = _NORMALISE.get(platform)
    if not norm_fn:
        logger.warning(f"Apify: unsupported platform '{platform}'")
        return []

    for keyword in keywords:
        try:
            if platform == "instagram":
                actor_id = apify_config.instagram_actor
                run_input = {
                    "hashtags": [keyword.lstrip("#")],
                    "resultsLimit": max_items,
                    "commentsPerPost": comments_per,
                    "scrapeComments": True,
                }
            elif platform == "facebook":
                actor_id = apify_config.facebook_actor
                run_input = {
                    "startUrls": [{"url": f"https://www.facebook.com/search/posts?q={keyword}"}],
                    "maxPosts": max_items,
                    "maxComments": comments_per,
                    "scrapeComments": True,
                }
            elif platform == "twitter":
                actor_id = apify_config.twitter_actor
                run_input = {
                    "searchTerms": [keyword],
                    "tweetLanguage": "ta,en",
                    "maxItems": max_items,
                    "scrapeReplies": True,
                    "maxReplies": comments_per,
                }
            elif platform == "youtube":
                actor_id = apify_config.youtube_actor
                run_input = {
                    "searchKeywords": keyword,
                    "maxResults": max_items,
                    "maxComments": comments_per,
                    "scrapeComments": True,
                }
            else:
                continue

            logger.info(f"Apify: running {actor_id} for keyword '{keyword}'")
            items = _run_actor(client, actor_id, run_input, max_items)
            for item in items:
                records.extend(norm_fn(item, keyword))
            logger.info(
                f"Apify [{platform}] '{keyword}': {len(items)} items"
            )

        except Exception as e:
            err_str = str(e).lower()
            if "rate limit" in err_str or "quota" in err_str or "limit" in err_str:
                logger.warning(f"Apify rate/quota limit hit for {platform}/{keyword}: {e}")
                raise  # bubble up so cascade can switch to next method
            logger.error(f"Apify error for {platform}/{keyword}: {e}")

    return records
