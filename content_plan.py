import json
import os
from datetime import datetime, timezone


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
            return json.load(file)
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


def load_config():
    config = load_json_file(CONFIG_FILE, {})
    return config if isinstance(config, dict) else {}


def get_output_path(config, key, fallback_path):
    output_files = config.get("output_files", {})
    if isinstance(output_files, dict):
        return output_files.get(key, fallback_path)
    return fallback_path


def pick_keywords(seo_data, seed_keywords):
    keywords = []
    if isinstance(seo_data, dict):
        for keyword in seo_data.get("high_priority_keywords", []):
            if isinstance(keyword, str) and keyword.strip() and keyword not in keywords:
                keywords.append(keyword.strip())

    for keyword in seed_keywords:
        if isinstance(keyword, str) and keyword.strip() and keyword not in keywords:
            keywords.append(keyword.strip())

    if not keywords:
        keywords = ["youtube growth", "content strategy", "video seo", "channel analytics"]

    return keywords


def pick_topics(topic_data, fallback_keywords):
    topics = []
    if isinstance(topic_data, dict):
        for item in topic_data.get("topics", []):
            if isinstance(item, dict):
                topics.append(item)

    if topics:
        return topics

    return [
        {
            "topic": f"{keyword.title()} for Small Channels",
            "angle": f"Practical steps creators can apply using {keyword}",
            "audience": "small creators",
            "keywords": [keyword],
            "cta": "Ask viewers what challenge they want solved next.",
        }
        for keyword in fallback_keywords[:7]
    ]


def build_weekly_plan(topics, keywords):
    content_types = [
        "Educational video",
        "Short-form tip",
        "Case study",
        "Tutorial",
        "Myth-busting video",
        "Checklist video",
        "Weekly roundup",
    ]
    days = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]

    plan = []
    for index, day in enumerate(days):
        topic = topics[index % len(topics)]
        primary_keyword = keywords[index % len(keywords)]
        working_title = topic.get("topic") or f"{primary_keyword.title()} Strategy"
        angle = topic.get("angle") or f"Useful lessons about {primary_keyword}"
        cta = topic.get("cta") or "Invite viewers to subscribe for more practical channel growth ideas."

        thumbnail_text = primary_keyword.upper()
        if len(thumbnail_text) > 28:
            thumbnail_text = thumbnail_text[:28].rstrip()

        plan.append(
            {
                "day": day,
                "content_type": content_types[index % len(content_types)],
                "working_title": working_title,
                "thumbnail_text": thumbnail_text,
                "primary_keyword": primary_keyword,
                "cta": cta,
                "angle": angle,
            }
        )

    return plan


def build_best_practices(analytics_data):
    practices = [
        "Open with a clear promise in the first 10 seconds.",
        "Use one primary keyword naturally in the title and first description paragraph.",
        "Keep thumbnail text short, bold, and easy to read on mobile.",
        "End each video with one simple next action for the viewer.",
        "Link related videos and playlists to extend session time.",
    ]

    if isinstance(analytics_data, dict):
        recommendations = analytics_data.get("recommendations", [])
        if isinstance(recommendations, list):
            for item in recommendations:
                if isinstance(item, str) and item.strip() and item not in practices:
                    practices.append(item.strip())

    return practices[:10]


def generate_content_plan():
    config = load_config()
    seed_keywords = config.get("default_keywords_seed", [])
    if not isinstance(seed_keywords, list):
        seed_keywords = []

    analytics_path = get_output_path(config, "analytics", os.path.join("output", "channel_analytics.json"))
    seo_path = get_output_path(config, "seo", os.path.join("output", "seo_suggestions.json"))
    topics_path = get_output_path(config, "topics", os.path.join("output", "topic_ideas.json"))
    calendar_path = get_output_path(config, "calendar", os.path.join("output", "content_calendar.json"))

    analytics_data = load_json_file(analytics_path, {})
    seo_data = load_json_file(seo_path, {})
    topics_data = load_json_file(topics_path, {})

    keywords = pick_keywords(seo_data, seed_keywords)
    topics = pick_topics(topics_data, keywords)

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "weekly_plan": build_weekly_plan(topics, keywords),
        "best_practices": build_best_practices(analytics_data),
    }

    save_json_file(calendar_path, output)


if __name__ == "__main__":
    try:
        generate_content_plan()
    except Exception as exc:
        log_error(f"Fatal error in content_plan.py: {exc}")
        raise
