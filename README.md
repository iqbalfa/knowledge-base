# Indonesia Knowledge Base

Real-time Indonesian news & social media data for Pabrik Konten content generation.

## Data Sources

- **RSS News**: Detik, Kompas, Tempo, CNN Indonesia, Tribun, Antara, Suara
- **YouTube Comments**: Trending Indonesian videos via YouTube Data API v3

## JSON Endpoints

| Endpoint | Description |
|----------|-------------|
| `data/news/latest.json` | Latest news articles (up to 200) |
| `data/news/trending.json` | Trending topics aggregation |
| `data/youtube/comments.json` | YouTube video comments with engagement data |

## Setup

1. Set `YOUTUBE_API_KEY` as GitHub Actions secret (Settings → Secrets → Actions)
2. Enable GitHub Pages (Settings → Pages → Source: main branch)
3. Scrapers run automatically 4x daily via GitHub Actions

## Local Run

```bash
pip install -r requirements.txt
export YOUTUBE_API_KEY=your_key_here
python scripts/scrape_news.py
python scripts/scrape_youtube.py
python scripts/generate_site.py
```

## Integration with Pabrik Konten

```python
import requests

news = requests.get("https://iqbalfa.github.io/knowledge-base/data/news/latest.json").json()
comments = requests.get("https://iqbalfa.github.io/knowledge-base/data/youtube/comments.json").json()
```
