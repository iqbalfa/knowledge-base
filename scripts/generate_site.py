#!/usr/bin/env python3
"""
Generate static site — builds index.html from JSON data files.
Run after scrapers to update the GitHub Pages site.
"""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

WIB = timezone(timedelta(hours=7))
DATA_DIR = Path(__file__).parent.parent / "data"
SITE_DIR = Path(__file__).parent.parent


def load_json(path):
    """Load JSON file, return empty dict if not found."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def generate_index_html(news, trending, youtube):
    """Generate a clean index.html with data summary."""
    news_count = news.get("count", 0)
    news_updated = news.get("updated", "N/A")
    youtube_videos = youtube.get("video_count", 0)
    youtube_comments = youtube.get("total_comments", 0)
    youtube_updated = youtube.get("updated", "N/A")

    # Top trending topics
    trending_html = ""
    for t in trending.get("topics", [])[:10]:
        headlines = "<br>".join(f"• {h}" for h in t.get("recent_headlines", [])[:2])
        trending_html += f"""
            <div class="topic-card">
                <div class="topic-name">{t['topic']}</div>
                <div class="topic-count">{t['article_count']} articles</div>
                <div class="topic-headlines">{headlines}</div>
            </div>"""

    # Top YouTube videos
    youtube_html = ""
    for v in youtube.get("videos", [])[:10]:
        stats = v.get("stats", {})
        views = f"{stats.get('views', 0):,}"
        comments = v.get("comment_count", 0)
        youtube_html += f"""
            <div class="video-card">
                <a href="{v['url']}" target="_blank">{v['title']}</a>
                <div class="video-meta">{v['channel']} • {views} views • {comments} comments</div>
            </div>"""

    html = f"""<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Indonesia Knowledge Base</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0a0a0a; color: #e0e0e0; padding: 20px; }}
        .container {{ max-width: 1000px; margin: 0 auto; }}
        h1 {{ color: #fff; font-size: 1.8em; margin-bottom: 5px; }}
        .subtitle {{ color: #888; margin-bottom: 30px; font-size: 0.9em; }}
        .section {{ margin-bottom: 40px; }}
        .section-title {{ color: #4fc3f7; font-size: 1.2em; margin-bottom: 15px; border-bottom: 1px solid #333; padding-bottom: 8px; }}
        .stats {{ display: flex; gap: 20px; margin-bottom: 30px; flex-wrap: wrap; }}
        .stat {{ background: #1a1a1a; padding: 15px 20px; border-radius: 8px; border: 1px solid #333; }}
        .stat-value {{ font-size: 1.5em; font-weight: bold; color: #4fc3f7; }}
        .stat-label {{ color: #888; font-size: 0.85em; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 15px; }}
        .topic-card, .video-card {{ background: #1a1a1a; padding: 15px; border-radius: 8px; border: 1px solid #333; }}
        .topic-name {{ font-weight: bold; color: #fff; text-transform: capitalize; }}
        .topic-count {{ color: #4fc3f7; font-size: 0.85em; margin: 4px 0; }}
        .topic-headlines {{ color: #999; font-size: 0.8em; line-height: 1.4; }}
        .video-card a {{ color: #4fc3f7; text-decoration: none; font-weight: 500; }}
        .video-card a:hover {{ text-decoration: underline; }}
        .video-meta {{ color: #888; font-size: 0.8em; margin-top: 5px; }}
        .endpoint {{ background: #1a1a1a; padding: 12px 15px; border-radius: 6px; border: 1px solid #333; margin-bottom: 8px; font-family: monospace; font-size: 0.85em; }}
        .endpoint a {{ color: #81c784; text-decoration: none; }}
        .endpoint a:hover {{ text-decoration: underline; }}
        .updated {{ color: #666; font-size: 0.75em; margin-top: 5px; }}
        footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #333; color: #666; font-size: 0.8em; text-align: center; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🇮🇩 Indonesia Knowledge Base</h1>
        <p class="subtitle">Real-time Indonesian news & social media data for Pabrik Konten</p>

        <div class="stats">
            <div class="stat">
                <div class="stat-value">{news_count}</div>
                <div class="stat-label">News Articles</div>
            </div>
            <div class="stat">
                <div class="stat-value">{youtube_videos}</div>
                <div class="stat-label">YouTube Videos</div>
            </div>
            <div class="stat">
                <div class="stat-value">{youtube_comments}</div>
                <div class="stat-label">Netizen Comments</div>
            </div>
        </div>

        <div class="section">
            <div class="section-title">📡 JSON Endpoints (for Pabrik Konten)</div>
            <div class="endpoint">📰 <a href="data/news/latest.json">data/news/latest.json</a> — Latest news articles</div>
            <div class="endpoint">🔥 <a href="data/news/trending.json">data/news/trending.json</a> — Trending topics</div>
            <div class="endpoint">💬 <a href="data/youtube/comments.json">data/youtube/comments.json</a> — YouTube comments</div>
        </div>

        <div class="section">
            <div class="section-title">🔥 Trending Topics</div>
            <div class="grid">
                {trending_html if trending_html else '<div class="topic-card">No trending data yet. Run scrapers first.</div>'}
            </div>
            <div class="updated">Updated: {news_updated}</div>
        </div>

        <div class="section">
            <div class="section-title">🎬 Top YouTube Videos</div>
            <div class="grid">
                {youtube_html if youtube_html else '<div class="video-card">No YouTube data yet. Set YOUTUBE_API_KEY and run scrapers.</div>'}
            </div>
            <div class="updated">Updated: {youtube_updated}</div>
        </div>

        <footer>
            Auto-updated via GitHub Actions • Data sources: RSS feeds (Detik, Kompas, Tempo, CNN Indonesia, Tribun, Antara, Suara) + YouTube Data API v3
        </footer>
    </div>
</body>
</html>"""

    return html


def main():
    print("[Generate Site] Loading data...")

    news = load_json(DATA_DIR / "news" / "latest.json")
    trending = load_json(DATA_DIR / "news" / "trending.json")
    youtube = load_json(DATA_DIR / "youtube" / "comments.json")

    print("[Generate Site] Generating index.html...")
    html = generate_index_html(news, trending, youtube)

    outpath = SITE_DIR / "index.html"
    with open(outpath, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[Generate Site] Done. Saved to {outpath}")


if __name__ == "__main__":
    main()
