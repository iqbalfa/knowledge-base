#!/usr/bin/env python3
"""
YouTube Comments Scraper — Fetches comments from trending Indonesian videos.
Uses YouTube Data API v3 (API key only, no OAuth needed for public data).
Outputs: data/youtube/comments.json
"""

import json
import re
import sys
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

WIB = timezone(timedelta(hours=7))

# API key from environment (set in GitHub Actions or local .env)
API_KEY = os.environ.get("YOUTUBE_API_KEY", "")

BASE_URL = "https://www.googleapis.com/youtube/v3"

# Indonesian search queries — topics that generate engagement
SEARCH_QUERIES = [
    "ekonomi indonesia 2026",
    "harga sembako indonesia",
    "politik indonesia terkini",
    "umkm indonesia",
    "teknologi indonesia",
    "pendidikan indonesia",
    "kebijakan pemerintah indonesia",
    "viral indonesia",
]

MAX_RESULTS_PER_QUERY = 3  # Videos per query
MAX_COMMENTS_PER_VIDEO = 50
MAX_VIDEOS = 100  # Cap total videos in knowledge base
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "youtube"


def api_get(endpoint, params):
    """Make YouTube API GET request."""
    params["key"] = API_KEY
    resp = requests.get(f"{BASE_URL}{endpoint}", params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def search_videos(query, max_results=3):
    """Search for videos matching query, sorted by relevance + viewCount."""
    data = api_get("/search", {
        "part": "snippet",
        "q": query,
        "type": "video",
        "order": "viewCount",
        "maxResults": max_results,
        "regionCode": "ID",
        "relevanceLanguage": "id",
        "publishedAfter": (datetime.now(WIB) - timedelta(days=7)).strftime("%Y-%m-%dT00:00:00Z"),
    })

    videos = []
    for item in data.get("items", []):
        videos.append({
            "video_id": item["id"]["videoId"],
            "title": item["snippet"]["title"],
            "channel": item["snippet"]["channelTitle"],
            "published_at": item["snippet"]["publishedAt"],
            "thumbnail": item["snippet"]["thumbnails"].get("high", {}).get("url", ""),
        })
    return videos


def get_video_stats(video_ids):
    """Get view/like/comment counts for videos."""
    if not video_ids:
        return {}

    data = api_get("/videos", {
        "part": "statistics",
        "id": ",".join(video_ids),
    })

    stats = {}
    for item in data.get("items", []):
        vid = item["id"]
        s = item.get("statistics", {})
        stats[vid] = {
            "views": int(s.get("viewCount", 0)),
            "likes": int(s.get("likeCount", 0)),
            "comments": int(s.get("commentCount", 0)),
        }
    return stats


def get_comments(video_id, max_results=50):
    """Fetch top comments for a video (ordered by relevance)."""
    comments = []
    page_token = None
    fetched = 0

    while fetched < max_results:
        params = {
            "part": "snippet",
            "videoId": video_id,
            "order": "relevance",
            "maxResults": min(20, max_results - fetched),
            "textFormat": "plainText",
        }
        if page_token:
            params["pageToken"] = page_token

        try:
            data = api_get("/commentThreads", params)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                print(f"    [WARN] Comments disabled for video {video_id}", file=sys.stderr)
                break
            raise

        for item in data.get("items", []):
            top = item["snippet"]["topLevelComment"]["snippet"]
            comments.append({
                "text": top["textDisplay"][:500],
                "author": top.get("authorDisplayName", "Unknown"),
                "likes": int(top.get("likeCount", 0)),
                "published": top.get("publishedAt", ""),
                "reply_count": item["snippet"].get("totalReplyCount", 0),
            })
            fetched += 1

        page_token = data.get("nextPageToken")
        if not page_token:
            break

    # Sort by likes (most engaging first)
    comments.sort(key=lambda x: x["likes"], reverse=True)
    return comments[:max_results]


def classify_comment_topics(text):
    """Simple keyword-based topic classification for comments."""
    text = text.lower()
    topics = []

    topic_map = {
        "ekonomi": ["ekonomi", "harga", "mahal", "murah", "gaji", "upah", "kerja", "bisnis", "dagang", "jualan", "laku", "rugi", "untung"],
        "politik": ["presiden", "menteri", "gubernur", "pemilu", "partai", "korupsi", "kebijakan", "aturan", "uu", "undang"],
        "pendidikan": ["sekolah", "kuliah", "mahasiswa", "siswa", "guru", "dosen", "beasiswa", "biaya"],
        "kesehatan": ["sakit", "obat", "rumah sakit", "bpjs", "dokter", "sehat", "penyakit"],
        "sosial": ["rakyat", "masyarakat", "kemiskinan", "banjir", "bencana", "bantuan", "subsidi"],
        "teknologi": ["hp", "internet", "aplikasi", "online", "digital", "ai", "robot"],
    }

    for topic, keywords in topic_map.items():
        if any(kw in text for kw in keywords):
            topics.append(topic)

    return topics if topics else ["umum"]


RETENTION_DAYS = 7  # Keep only last 7 days of data


def load_existing(path):
    """Load existing YouTube data, return empty list if not found."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("videos", [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def prune_old_videos(videos, days=RETENTION_DAYS):
    """Remove videos older than N days based on published date."""
    cutoff = datetime.now(WIB) - timedelta(days=days)
    cutoff_iso = cutoff.strftime("%Y-%m-%dT%H:%M:%S")
    return [v for v in videos if v.get("published", "") >= cutoff_iso]


def merge_videos(existing, new_videos):
    """Merge new videos with existing, deduplicate by video_id."""
    seen = {}
    for v in existing + new_videos:
        vid = v.get("video_id", "")
        if vid and vid not in seen:
            seen[vid] = v
    merged = list(seen.values())
    merged.sort(key=lambda x: x.get("stats", {}).get("views", 0), reverse=True)
    return merged


def main():
    if not API_KEY:
        print("[YouTube Scraper] ERROR: YOUTUBE_API_KEY not set!", file=sys.stderr)
        print("Set via: export YOUTUBE_API_KEY=your_key_here", file=sys.stderr)
        sys.exit(1)

    print("[YouTube Scraper] Starting...")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    outpath = OUTPUT_DIR / "comments.json"

    all_videos = []
    seen_video_ids = set()

    # Search for videos
    for query in SEARCH_QUERIES:
        print(f"  Searching: '{query}'")
        try:
            videos = search_videos(query, MAX_RESULTS_PER_QUERY)
            for v in videos:
                if v["video_id"] not in seen_video_ids:
                    seen_video_ids.add(v["video_id"])
                    all_videos.append(v)
                    print(f"    Found: {v['title'][:60]}...")
        except Exception as e:
            print(f"    [WARN] Search failed: {e}", file=sys.stderr)

    print(f"\n  Total unique videos found: {len(all_videos)}")

    # Get stats
    video_ids = [v["video_id"] for v in all_videos]
    print("  Fetching video stats...")
    stats = get_video_stats(video_ids)

    # Get comments for each video
    results = []
    for video in all_videos:
        vid = video["video_id"]
        print(f"  Fetching comments: {video['title'][:50]}...")

        try:
            comments = get_comments(vid, MAX_COMMENTS_PER_VIDEO)
        except Exception as e:
            print(f"    [WARN] Failed: {e}", file=sys.stderr)
            comments = []

        # Classify comments
        for c in comments:
            c["topics"] = classify_comment_topics(c["text"])

        video_stats = stats.get(vid, {})

        results.append({
            "video_id": vid,
            "title": video["title"],
            "channel": video["channel"],
            "url": f"https://www.youtube.com/watch?v={vid}",
            "published": video["published_at"],
            "stats": video_stats,
            "comment_count": len(comments),
            "comments": comments,
        })

    # Sort by engagement (views)
    results.sort(key=lambda x: x.get("stats", {}).get("views", 0), reverse=True)

    # Load existing + merge + prune
    existing = load_existing(outpath)
    print(f"\n  Existing videos: {len(existing)}")

    merged = merge_videos(existing, results)
    videos = prune_old_videos(merged)
    # Cap total videos
    if len(videos) > MAX_VIDEOS:
        print(f"  Capped at {MAX_VIDEOS} videos (was {len(videos)})")
        videos = videos[:MAX_VIDEOS]
    pruned = len(merged) - len(videos)
    if pruned > 0:
        print(f"  Pruned {pruned} videos older than {RETENTION_DAYS} days")

    now = datetime.now(WIB).isoformat()
    output = {
        "updated": now,
        "source": "YouTube Data API v3",
        "retention_days": RETENTION_DAYS,
        "video_count": len(videos),
        "total_comments": sum(r.get("comment_count", 0) for r in videos),
        "videos": videos,
    }

    outpath = OUTPUT_DIR / "comments.json"
    with open(outpath, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    total_comments = output["total_comments"]
    print(f"\n[YouTube Scraper] Done. {len(results)} videos, {total_comments} comments saved to {outpath}")


if __name__ == "__main__":
    main()
