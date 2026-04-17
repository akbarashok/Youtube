import json
import os
from datetime import datetime, timezone

import requests
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


CONFIG_FILE = "channel_config.json"
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


def build_youtube_client():
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        raise ValueError("Missing required environment variable: YOUTUBE_API_KEY")

    return build("youtube", "v3", developerKey=api_key)


def safe_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def load_channel_config():
    config = load_json_file(CONFIG_FILE, {})
    if not isinstance(config, dict):
        raise ValueError("Invalid channel_config.json format. Expected an object.")
    return config


def get_output_path(config):
    output_files = config.get("output_files", {})
    if not isinstance(output_files, dict):
        raise ValueError("Invalid channel_config.json format for output_files.")

    analytics_path = output_files.get("analytics")
    if not analytics_path:
        raise ValueError("Missing output_files.analytics in channel_config.json")

    return analytics_path


def fetch_channel_details(youtube, channel_id):
    request = youtube.channels().list(
        part="snippet,statistics,contentDetails",
        id=channel_id,
        maxResults=1,
    )
    response = request.execute()

    items = response.get("items", [])
    if not items:
        raise ValueError(f"No channel data returned for channel_id={channel_id}")

    item = items[0]
    snippet = item.get("snippet", {})
    statistics = item.get("statistics", {})
    content_details = item.get("contentDetails", {})
    related_playlists = content_details.get("relatedPlaylists", {})

    return {
        "channel": {
            "channel_id": channel_id,
            "title": snippet.get("title", ""),
            "published_at": snippet.get("publishedAt", ""),
            "subscriber_count": safe_int(statistics.get("subscriberCount")),
            "video_count": safe_int(statistics.get("videoCount")),
            "view_count": safe_int(statistics.get("viewCount")),
        },
        "uploads_playlist_id": related_playlists.get("uploads", ""),
    }


def fetch_upload_video_ids(youtube, uploads_playlist_id, max_results):
    if not uploads_playlist_id:
        return []

    request = youtube.playlistItems().list(
        part="contentDetails",
        playlistId=uploads_playlist_id,
        maxResults=max_results,
    )
    response = request.execute()

    video_ids = []
    for item in response.get("items", []):
        content_details = item.get("contentDetails", {})
        video_id = content_details.get("videoId")
        if video_id:
            video_ids.append(video_id)

    return video_ids


def fetch_videos_details(youtube, video_ids):
    if not video_ids:
        return []

    request = youtube.videos().list(
        part="snippet,statistics",
        id=",".join(video_ids),
        maxResults=len(video_ids),
    )
    response = request.execute()

    videos = []
    for item in response.get("items", []):
        snippet = item.get("snippet", {})
        statistics = item.get("statistics", {})

        videos.append(
            {
                "video_id": item.get("id", ""),
                "title": snippet.get("title", ""),
                "published_at": snippet.get("publishedAt", ""),
                "views": safe_int(statistics.get("viewCount")),
                "likes": safe_int(statistics.get("likeCount")),
                "comments": safe_int(statistics.get("commentCount")),
            }
        )

    order_map = {video_id: index for index, video_id in enumerate(video_ids)}
    videos.sort(key=lambda video: order_map.get(video.get("video_id", ""), len(order_map)))
    return videos


def build_summary(channel, videos):
    total_videos_analyzed = len(videos)
    total_recent_views = sum(video.get("views", 0) for video in videos)
    total_recent_likes = sum(video.get("likes", 0) for video in videos)
    total_recent_comments = sum(video.get("comments", 0) for video in videos)

    if total_videos_analyzed:
        average_views = round(total_recent_views / total_videos_analyzed, 2)
        average_likes = round(total_recent_likes / total_videos_analyzed, 2)
        average_comments = round(total_recent_comments / total_videos_analyzed, 2)
    else:
        average_views = 0
        average_likes = 0
        average_comments = 0

    subscriber_count = channel.get("subscriber_count", 0)
    view_count = channel.get("view_count", 0)
    video_count = channel.get("video_count", 0)

    return {
        "total_channel_subscribers": subscriber_count,
        "total_channel_videos": video_count,
        "total_channel_views": view_count,
        "videos_analyzed": total_videos_analyzed,
        "recent_total_views": total_recent_views,
        "recent_total_likes": total_recent_likes,
        "recent_total_comments": total_recent_comments,
        "average_views_per_video": average_views,
        "average_likes_per_video": average_likes,
        "average_comments_per_video": average_comments,
        "average_channel_views_per_video": round(view_count / video_count, 2) if video_count else 0,
    }


def build_recommendations(channel, summary, top_videos, recent_videos):
    recommendations = []

    if not recent_videos:
        recommendations.append(
            "Publish consistently and review performance once enough recent uploads are available for comparison."
        )
        return recommendations

    average_views = summary.get("average_views_per_video", 0)
    average_likes = summary.get("average_likes_per_video", 0)
    average_comments = summary.get("average_comments_per_video", 0)
    subscriber_count = channel.get("subscriber_count", 0)

    best_video = top_videos[0] if top_videos else None
    latest_video = recent_videos[0] if recent_videos else None

    if best_video and average_views and best_video.get("views", 0) > average_views * 1.5:
        recommendations.append(
            f"Review the format and topic of '{best_video.get('title', '')}' because it is outperforming the recent channel average."
        )

    if latest_video and average_views and latest_video.get("views", 0) < average_views:
        recommendations.append(
            f"Consider refreshing the packaging of the latest upload '{latest_video.get('title', '')}' with stronger titles, descriptions, and thumbnails."
        )

    if average_comments < 5:
        recommendations.append(
            "Increase audience interaction prompts by asking one clear question in each video and description to encourage more comments."
        )

    if average_likes and average_views:
        like_rate = average_likes / average_views
        if like_rate < 0.03:
            recommendations.append(
                "Add clearer calls to action for likes and highlight the main value earlier to improve engagement rate."
            )

    if subscriber_count and average_views and average_views < max(subscriber_count * 0.1, 1):
        recommendations.append(
            "Test more discoverable topics and keyword-focused titles because average recent views are low relative to the subscriber base."
        )

    if not recommendations:
        recommendations.append(
            "Maintain the current publishing approach and continue doubling down on the topics and formats that appear in the highest-view recent videos."
        )

    return recommendations


def generate_report():
    config = load_channel_config()
    channel_id = config.get("channel_id")
    if not channel_id:
        raise ValueError("Missing channel_id in channel_config.json")

    max_videos = safe_int(config.get("max_videos_for_reports"))
    if max_videos <= 0:
        max_videos = 10

    output_path = get_output_path(config)
    youtube = build_youtube_client()

    channel_data = fetch_channel_details(youtube, channel_id)
    uploads_playlist_id = channel_data.get("uploads_playlist_id", "")
    channel = channel_data.get("channel", {})

    video_ids = fetch_upload_video_ids(youtube, uploads_playlist_id, min(max_videos, 50))
    recent_videos = fetch_videos_details(youtube, video_ids)

    top_videos = sorted(recent_videos, key=lambda video: video.get("views", 0), reverse=True)[:5]
    summary = build_summary(channel, recent_videos)
    recommendations = build_recommendations(channel, summary, top_videos, recent_videos)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "channel": channel,
        "summary": summary,
        "top_videos": top_videos,
        "recent_videos": recent_videos,
        "recommendations": recommendations,
    }

    save_json_file(output_path, report)


if __name__ == "__main__":
    try:
        generate_report()
    except HttpError as exc:
        log_error(f"YouTube API error: {exc}")
    except requests.RequestException as exc:
        log_error(f"Network error: {exc}")
    except Exception as exc:
        log_error(f"Fatal error: {exc}")