#!/usr/bin/env python3
"""
RSS News Scraper — Indonesian news aggregator.
Scrapes RSS feeds from major Indonesian news outlets.
Outputs: data/news/latest.json
"""

import json
import hashlib
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import feedparser
import requests

WIB = timezone(timedelta(hours=7))

RSS_FEEDS = [
    # Detik
    {"url": "https://rss.detik.com/index.php/detikcom", "source": "detik.com"},
    {"url": "https://rss.detik.com/index.php/finance", "source": "detik.com/finance"},
    {"url": "https://rss.detik.com/index.php/inet", "source": "detik.com/inet"},
    # Kompas
    {"url": "https://rss.kompas.com/?feed=news", "source": "kompas.com"},
    {"url": "https://rss.kompas.com/?feed=tekno", "source": "kompas.com/tekno"},
    # Tempo
    {"url": "https://rss.tempo.co/nasional", "source": "tempo.co/nasional"},
    {"url": "https://rss.tempo.co/ekonomi", "source": "tempo.co/ekonomi"},
    {"url": "https://rss.tempo.co/teknologi", "source": "tempo.co/teknologi"},
    # CNN Indonesia
    {"url": "https://www.cnnindonesia.com/nasional/rss", "source": "cnnindonesia.com"},
    {"url": "https://www.cnnindonesia.com/ekonomi/rss", "source": "cnnindonesia.com/ekonomi"},
    # Tribunnews
    {"url": "https://www.tribunnews.com/rss", "source": "tribunnews.com"},
    # Antara
    {"url": "https://www.antaranews.com/rss/terkini.xml", "source": "antaranews.com"},
    # Suara
    {"url": "https://www.suara.com/rss", "source": "suara.com"},
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; KnowledgeBaseBot/1.0)"
}

MAX_ITEMS = 200
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "news"


def make_id(entry):
    """Generate stable dedup ID from URL or title."""
    key = entry.get("link", "") or entry.get("title", "")
    return hashlib.md5(key.encode()).hexdigest()[:12]


def parse_date(entry):
    """Parse entry date to ISO format."""
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            return dt.astimezone(WIB).isoformat()
        except Exception:
            pass
    return datetime.now(WIB).isoformat()


def extract_summary(entry):
    """Extract clean summary from entry."""
    summary = entry.get("summary", "") or entry.get("description", "")
    # Strip HTML tags (basic)
    import re
    clean = re.sub(r"<[^>]+>", "", summary)
    return clean[:500].strip()


def classify_topics(title, summary):
    """Simple keyword-based topic classification."""
    text = (title + " " + summary).lower()
    topics = []

    topic_keywords = {
        "ekonomi": ["ekonomi", "rupiah", "inflasi", "harga", "sembako", "upah", "gaji", "gdp", "ihsg", "saham", "investasi", "bisnis", "umkm", "startup", "ekspor", "impor"],
        "politik": ["politik", "pemilu", "presiden", "menteri", "gubernur", "dprd", "partai", "koalisi", "pilkada", "undang-undang", "uu", "ruu", "demokrasi"],
        "teknologi": ["teknologi", "digital", "ai", "internet", "startup", "aplikasi", "smartphone", "media sosial", "tiktok", "gojek", "grab", "tokopedia"],
        "sosial": ["sosial", "pendidikan", "kesehatan", "banjir", "gempa", "bencana", "kemiskinan", "korupsi", "hukum", "kekerasan"],
        "olahraga": ["olahraga", "liga", "sepakbola", "bola", "basket", "badminton", "motogp", "f1"],
        "hiburan": ["hiburan", "film", "musik", "artis", "selebriti", "drama", "anime", "game"],
        "internasional": ["internasional", "global", "amerika", "china", "jepang", "eropa", "timur tengah", "perang"],
    }

    for topic, keywords in topic_keywords.items():
        if any(kw in text for kw in keywords):
            topics.append(topic)

    return topics if topics else ["umum"]


def scrape_feeds():
    """Scrape all RSS feeds and return deduplicated articles."""
    seen_ids = set()
    articles = []

    for feed_info in RSS_FEEDS:
        url = feed_info["url"]
        source = feed_info["source"]

        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            feed = feedparser.parse(resp.content)
        except Exception as e:
            print(f"  [WARN] Failed {source}: {e}", file=sys.stderr)
            continue

        count = 0
        for entry in feed.entries:
            aid = make_id(entry)
            if aid in seen_ids:
                continue
            seen_ids.add(aid)

            title = entry.get("title", "").strip()
            if not title:
                continue

            summary = extract_summary(entry)
            articles.append({
                "id": aid,
                "title": title,
                "url": entry.get("link", ""),
                "source": source,
                "summary": summary,
                "topics": classify_topics(title, summary),
                "published": parse_date(entry),
            })
            count += 1

        print(f"  [OK] {source}: {count} articles")

    # Sort by published date (newest first), limit
    articles.sort(key=lambda x: x["published"], reverse=True)
    return articles[:MAX_ITEMS]


def main():
    print("[RSS News Scraper] Starting...")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    articles = scrape_feeds()
    now = datetime.now(WIB).isoformat()

    output = {
        "updated": now,
        "source": "RSS aggregator",
        "count": len(articles),
        "items": articles,
    }

    outpath = OUTPUT_DIR / "latest.json"
    with open(outpath, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"[RSS News Scraper] Done. {len(articles)} articles saved to {outpath}")

    # Also generate trending topics summary
    topic_counts = {}
    topic_sentiment_words = {
        "positive": ["naik", "melonjak", "positif", "berhasil", "sukses", "menang", "untung", "tumbuh", "meningkat"],
        "negative": ["turun", "anjlok", "gagal", "korban", "rusak", "meninggal", "rug", "merosot", "krisis"],
    }

    for art in articles:
        for topic in art["topics"]:
            topic_counts[topic] = topic_counts.get(topic, 0) + 1

    trending = []
    for topic, count in sorted(topic_counts.items(), key=lambda x: -x[1]):
        # Get recent articles for this topic
        topic_articles = [a for a in articles if topic in a["topics"]][:5]
        trending.append({
            "topic": topic,
            "article_count": count,
            "recent_headlines": [a["title"] for a in topic_articles[:3]],
        })

    trending_output = {
        "updated": now,
        "topics": trending,
    }

    trending_path = OUTPUT_DIR / "trending.json"
    with open(trending_path, "w", encoding="utf-8") as f:
        json.dump(trending_output, f, ensure_ascii=False, indent=2)

    print(f"[RSS News Scraper] Trending topics saved to {trending_path}")


if __name__ == "__main__":
    main()
