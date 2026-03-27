"""
Scrapy items — map directly to SocialMediaRecord fields.
"""

import scrapy


class SocialPostItem(scrapy.Item):
    platform = scrapy.Field()
    type = scrapy.Field()         # "post" or "comment"
    id = scrapy.Field()
    parent_id = scrapy.Field()
    url = scrapy.Field()
    author = scrapy.Field()
    text = scrapy.Field()
    title = scrapy.Field()
    like_count = scrapy.Field()
    reaction_count = scrapy.Field()
    view_count = scrapy.Field()
    retweet_count = scrapy.Field()
    reply_count = scrapy.Field()
    comment_count = scrapy.Field()
    source = scrapy.Field()
    timestamp = scrapy.Field()
    parties_mentioned = scrapy.Field()
    is_palladam_related = scrapy.Field()
    raw_data = scrapy.Field()
