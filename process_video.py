import json
import os
import re
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

import requests
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


QUEUE_FILE = "queue.json"
RESULTS_FILE = os.path.join("output", "results.json")
ERROR_LOG_FILE = "error.log"


def ensure_file(path, default_value):
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as file:
            json.dump(default_value, file, indent=2, ensure_ascii=False)


def load_json_file(path, default_value):
    ensure_file(path, default_value)
    try:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
            return data
    except Exception as exc:
        log_error(f"Failed to read JSON file: {path} | Error: {exc}")
        return default_value


def save_json_file(path, data):
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)


def log_error(message):
    timestamp = datetime.now(timezone.utc).isoformat()
    with open(ERROR_LOG_FILE, "a", encoding="utf-8") as file:
        file.write(f"[{timestamp}] {message}\n")


def extract_video_id(url):
    if not url or not isinstance(url, str):
        return None

    url = url.strip()

    patterns = [
        r"(?:v=|\/)([0-9A-Za-z_-]{11})(?:[?&/#]|$)",
        r"youtu\.be\/([0-9A-Za-z_-]{11})(?:[?&/#]|$)",
        r"youtube\.com\/shorts\/([0-9A-Za-z_-]{11})(?:[?&/#]|$)",
        r"youtube\.com\/embed\/([0-9A-Za-z_-]{11})(?:[?&/#]|$)",
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    try:
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        if "v" in query and query["v"]:
            candidate = query["v"][0]
            if re.fullmatch(r"[0-9A-Za-z_-]{11}", candidate):
                return candidate
    except Exception as exc:
        log_error(f"URL parsing failed for '{url}' | Error: {exc}")

    return None


def build_youtube_client():
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        raise ValueError("Missing required environment variable: YOUTUBE_API_KEY")

    return build("youtube", "v3", developerKey=api_key)


def fetch_video_metadata(youtube, video_id):
    request = youtube.videos().list(
        part="snippet,statistics",
        id=video_id,
        maxResults=1,
    )
    response = request.execute()

    items = response.get("items", [])
    if not items:
        raise ValueError(f"No video data returned for video_id={video_id}")

    item = items[0]
    snippet = item.get("snippet", {})
    statistics = item.get("statistics", {})

    return {
        "video_id": video_id,
        "source_title": snippet.get("title", ""),
        "source_description": snippet.get("description", ""),
        "channel_title": snippet.get("channelTitle", ""),
        "published_at": snippet.get("publishedAt", ""),
        "category_id": snippet.get("categoryId", ""),
        "default_language": snippet.get("defaultLanguage", ""),
        "tags": snippet.get("tags", []),
        "view_count": int(statistics.get("viewCount", 0)),
        "like_count": int(statistics.get("likeCount", 0)) if statistics.get("likeCount") else 0,
        "comment_count": int(statistics.get("commentCount", 0)) if statistics.get("commentCount") else 0,
    }


def clean_words(text):
    words = re.findall(r"[A-Za-z0-9]+", text.lower())
    stopwords = {
        "the", "and", "for", "with", "that", "this", "from", "your", "have", "will",
        "about", "into", "video", "youtube", "how", "what", "when", "where", "why",
        "are", "was", "were", "has", "had", "you", "they", "them", "their", "our",
        "out", "all", "can", "not", "but", "too", "its", "it's", "than", "then",
    }
    return [word for word in words if len(word) > 2 and word not in stopwords]


def generate_optimized_title(source_title, channel_title):
    title = source_title.strip()
    if not title:
        title = "YouTube Video"

    if len(title) > 90:
        title = title[:87].rstrip() + "..."

    if channel_title and channel_title.lower() not in title.lower():
        return f"{title} | {channel_title}".strip()

    return title


def generate_optimized_description(metadata):
    source_description = (metadata.get("source_description") or "").strip()
    source_title = metadata.get("source_title") or "YouTube Video"
    channel_title = metadata.get("channel_title") or "Unknown Channel"
    stats_line = (
        f"Views: {metadata.get('view_count', 0)} | "
        f"Likes: {metadata.get('like_count', 0)} | "
        f"Comments: {metadata.get('comment_count', 0)}"
    )

    summary = source_description[:400].strip()
    if not summary:
        summary = f"Metadata summary for '{source_title}' from channel '{channel_title}'."

    description_parts = [
        f"Optimized summary for: {source_title}",
        f"Channel: {channel_title}",
        stats_line,
        "",
        summary,
        "",
        "Generated automatically for metadata review and content planning.",
    ]

    return "\n".join(description_parts).strip()


def generate_optimized_tags(metadata):
    base_terms = clean_words(metadata.get("source_title", ""))
    description_terms = clean_words(metadata.get("source_description", ""))
    channel_terms = clean_words(metadata.get("channel_title", ""))

    combined = []
    for term in base_terms + description_terms + channel_terms:
        if term not in combined:
            combined.append(term)

    original_tags = metadata.get("tags", [])
    for tag in original_tags:
        normalized = tag.strip().lower()
        if normalized and normalized not in combined:
            combined.append(normalized)

    combined.extend(["youtube", "content", "metadata", "automation"])

    deduped = []
    for tag in combined:
        if tag and tag not in deduped:
            deduped.append(tag)

    return deduped[:15]


def generate_optimized_metadata(metadata):
    return {
        "title": generate_optimized_title(
            metadata.get("source_title", ""),
            metadata.get("channel_title", ""),
        ),
        "description": generate_optimized_description(metadata),
        "tags": generate_optimized_tags(metadata),
    }


def validate_queue(queue_data):
    if isinstance(queue_data, list):
        return queue_data

    if isinstance(queue_data, dict) and isinstance(queue_data.get("urls"), list):
        return queue_data["urls"]

    log_error("Invalid queue.json format. Expected a list or {'urls': []}.")
    return []


def append_result(results, url, metadata, optimized_metadata):
    results.append(
        {
            "processed_at": datetime.now(timezone.utc).isoformat(),
            "url": url,
            "video_id": metadata.get("video_id"),
            "source_metadata": metadata,
            "optimized_metadata": optimized_metadata,
        }
    )


def process_queue():
    ensure_file(QUEUE_FILE, [])
    ensure_file(RESULTS_FILE, [])

    queue_raw = load_json_file(QUEUE_FILE, [])
    results = load_json_file(RESULTS_FILE, [])

    queue_urls = validate_queue(queue_raw)

    if not isinstance(results, list):
        log_error("Invalid results.json format. Resetting to empty list.")
        results = []

    if not queue_urls:
        return

    youtube = build_youtube_client()
    remaining_urls = []

    for url in queue_urls:
        try:
            video_id = extract_video_id(url)
            if not video_id:
                raise ValueError(f"Could not extract video ID from URL: {url}")

            metadata = fetch_video_metadata(youtube, video_id)
            optimized_metadata = generate_optimized_metadata(metadata)
            append_result(results, url, metadata, optimized_metadata)
        except HttpError as exc:
            log_error(f"YouTube API error for URL '{url}' | Error: {exc}")
            remaining_urls.append(url)
        except requests.RequestException as exc:
            log_error(f"Network error for URL '{url}' | Error: {exc}")
            remaining_urls.append(url)
        except Exception as exc:
            log_error(f"Processing failed for URL '{url}' | Error: {exc}")
            remaining_urls.append(url)

    save_json_file(RESULTS_FILE, results)

    if isinstance(queue_raw, dict) and "urls" in queue_raw:
        queue_raw["urls"] = remaining_urls
        save_json_file(QUEUE_FILE, queue_raw)
    else:
        save_json_file(QUEUE_FILE, remaining_urls)


if __name__ == "__main__":
    try:
        process_queue()
    except Exception as exc:
        log_error(f"Fatal error: {exc}")
        raise
