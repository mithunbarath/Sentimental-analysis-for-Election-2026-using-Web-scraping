"""
NLP Pipeline for Palladam Politics Scraper.

Adds two enrichment fields to each SocialMediaRecord:
  - nlp_sentiment      : "positive" | "neutral" | "negative"
  - nlp_sentiment_score: float confidence (0.0 – 1.0)
  - nlp_trend_score    : relative frequency of record keywords
                         vs a rolling window of recent records

Model used by default:
  nlptown/bert-base-multilingual-uncased-sentiment
  → Supports Tamil (Dravidian script) via multilingual tokenisation.
  → Produces 1–5 star rating which we map to pos/neutral/neg.

Override in config.yaml:
  nlp:
    model_name: "ai4bharat/indic-bert"  # Better for Indian languages

Usage:
    from nlp_pipeline import NLPPipeline
    pipe = NLPPipeline(cfg.nlp)
    enriched = pipe.enrich_records(records)
"""

import logging
import re
from collections import Counter
from typing import List, Optional

from models import SocialMediaRecord

logger = logging.getLogger(__name__)

# Party / region keywords for trend scoring
_TREND_KEYWORDS = [
    "palladam", "பல்லடம்",
    "dmk", "டிஎம்கே", "stalin", "ஸ்டாலின்",
    "admk", "aiadmk", "அதிமுக", "eps", "edappadi",
    "tvk", "டி.வி.கே", "vijay", "விஜய்",
    "tiruppur", "திருப்பூர்",
]


def _label_to_sentiment(label: str) -> tuple[str, float]:
    """
    Map model output label → (sentiment_string, confidence).

    nlptown model returns '1 star' … '5 stars'.
    We treat 1–2 = negative, 3 = neutral, 4–5 = positive.
    """
    label_lower = label.lower()
    if "1 star" in label_lower or "2 star" in label_lower:
        return "negative", 1.0
    elif "3 star" in label_lower:
        return "neutral", 1.0
    elif "4 star" in label_lower or "5 star" in label_lower:
        return "positive", 1.0
    # Fallback for other model formats (POSITIVE / NEGATIVE / NEUTRAL)
    if "positive" in label_lower:
        return "positive", 1.0
    if "negative" in label_lower:
        return "negative", 1.0
    return "neutral", 1.0


def _keyword_score(text: str) -> float:
    """Count how many trend keywords appear in text (normalised 0–1)."""
    if not text:
        return 0.0
    text_lower = text.lower()
    hits = sum(1 for kw in _TREND_KEYWORDS if kw.lower() in text_lower)
    return min(hits / max(len(_TREND_KEYWORDS), 1), 1.0)


class NLPPipeline:
    """
    Sentiment + trend enrichment pipeline.

    Lazy-loads the transformer model on first call to `enrich_records`
    so importing this module doesn't block startup.
    """

    def __init__(self, nlp_cfg=None):
        self._cfg = nlp_cfg
        self._pipe = None  # lazy init
        self._model_name = (
            getattr(nlp_cfg, "model_name", None)
            or "nlptown/bert-base-multilingual-uncased-sentiment"
        )
        self._batch_size = getattr(nlp_cfg, "batch_size", 16)
        self._window_size = getattr(nlp_cfg, "trend_window_size", 100)

    def _load_model(self):
        """Load the HuggingFace pipeline (downloads on first use)."""
        if self._pipe is not None:
            return
        try:
            from transformers import pipeline as hf_pipeline
            logger.info(f"Loading NLP model: {self._model_name} …")
            self._pipe = hf_pipeline(
                "sentiment-analysis",
                model=self._model_name,
                truncation=True,
                max_length=512,
            )
            logger.info("NLP model loaded successfully.")
        except Exception as e:
            logger.error(
                f"Failed to load NLP model '{self._model_name}': {e}\n"
                f"Install transformers: pip install transformers sentencepiece torch"
            )
            self._pipe = None

    def _get_texts(self, records: List[SocialMediaRecord]) -> List[str]:
        """Extract combined text from each record for sentiment analysis."""
        texts = []
        for rec in records:
            parts = []
            if rec.title:
                parts.append(rec.title)
            if rec.text:
                parts.append(rec.text)
            combined = " ".join(parts).strip()
            # Truncate to 512 chars (model max tokens ~512 sub-words)
            texts.append(combined[:512] if combined else "")
        return texts

    def _compute_trend_scores(
        self,
        records: List[SocialMediaRecord],
        window_scores: List[float],
    ) -> List[float]:
        """
        Compute trend score as keyword density relative to rolling window mean.

        trend_score = record_score / (window_mean + epsilon)
        Values > 1.0 mean this record has higher-than-average keyword density.
        Capped at 3.0 to avoid huge outliers.
        """
        if not window_scores:
            return [0.0] * len(records)
        window_mean = sum(window_scores) / len(window_scores)
        eps = 1e-6
        scores = []
        for rec in records:
            text = (rec.text or "") + " " + (rec.title or "")
            raw = _keyword_score(text)
            trend = min(raw / (window_mean + eps), 3.0)
            scores.append(round(trend, 4))
        return scores

    def enrich_records(
        self,
        records: List[SocialMediaRecord],
        rolling_window: Optional[List[SocialMediaRecord]] = None,
    ) -> List[SocialMediaRecord]:
        """
        Enrich records in-place with NLP fields.

        Args:
            records       : Records to enrich.
            rolling_window: Previous records used as trend baseline.
                           If None, uses `records` itself as baseline.

        Returns:
            The same list with nlp_* fields populated.
        """
        if not records:
            return records

        self._load_model()

        # ── Sentiment ────────────────────────────────────────────────────────
        texts = self._get_texts(records)
        sentiments: List[Optional[tuple]] = [None] * len(records)

        if self._pipe:
            # Filter out empty texts; run in batches
            non_empty = [(i, t) for i, t in enumerate(texts) if t.strip()]
            batch_texts = [t for _, t in non_empty]

            try:
                results = []
                for i in range(0, len(batch_texts), self._batch_size):
                    batch = batch_texts[i : i + self._batch_size]
                    results.extend(self._pipe(batch))

                for (orig_idx, _), res in zip(non_empty, results):
                    label = res.get("label", "neutral")
                    score = res.get("score", 0.5)
                    sentiment_str, _ = _label_to_sentiment(label)
                    sentiments[orig_idx] = (sentiment_str, round(score, 4))

            except Exception as e:
                logger.error(f"Sentiment batch inference error: {e}")
        else:
            # Fallback: rule-based Tamil positive/negative word lists
            logger.warning("NLP model unavailable — using rule-based fallback.")
            _positive_words = ["நல்ல", "வெற்றி", "good", "win", "support", "proud"]
            _negative_words = ["மோசம்", "தோல்வி", "bad", "fail", "corrupt", "protest"]
            for i, text in enumerate(texts):
                tl = text.lower()
                pos = sum(1 for w in _positive_words if w in tl)
                neg = sum(1 for w in _negative_words if w in tl)
                if pos > neg:
                    sentiments[i] = ("positive", 0.6)
                elif neg > pos:
                    sentiments[i] = ("negative", 0.6)
                else:
                    sentiments[i] = ("neutral", 0.5)

        # ── Trend scores ──────────────────────────────────────────────────────
        window = rolling_window if rolling_window is not None else records
        window_raw = [
            _keyword_score((r.text or "") + " " + (r.title or ""))
            for r in window[-self._window_size :]
        ]
        trend_scores = self._compute_trend_scores(records, window_raw)

        # ── Write back ────────────────────────────────────────────────────────
        for rec, sentiment_tuple, trend in zip(records, sentiments, trend_scores):
            if sentiment_tuple:
                rec.nlp_sentiment, rec.nlp_sentiment_score = sentiment_tuple
            rec.nlp_trend_score = trend

        logger.info(
            f"NLP enrichment complete: {len(records)} records processed. "
            f"Sentiments — "
            + ", ".join(
                f"{s}: {sum(1 for r in records if r.nlp_sentiment == s)}"
                for s in ["positive", "neutral", "negative"]
            )
        )
        return records


# ── Module-level helper ────────────────────────────────────────────────────────

def enrich_if_configured(
    records: List[SocialMediaRecord],
    nlp_cfg,
    rolling_window: Optional[List[SocialMediaRecord]] = None,
) -> List[SocialMediaRecord]:
    """
    Convenience wrapper — call this from main.py.
    Returns records unchanged if NLP is disabled.
    """
    if not getattr(nlp_cfg, "enabled", False):
        return records
    pipeline = NLPPipeline(nlp_cfg)
    return pipeline.enrich_records(records, rolling_window=rolling_window)
