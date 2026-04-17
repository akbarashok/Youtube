import json
import os
import re
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


def clean_words(text):
    words = re.findall(r"[A-Za-z0-9]+", (text or "").lower())
    stopwords = {
        "the", "and", "for", "with", "that", "this", "from", "your", "have", "will",
        "about", "into", "video", "youtube", "how", "what", "when", "where", "why",
        "are", "was", "were", "has", "had", "you", "they", "them", "their", "our",
        "out", "all", "can", "not", "but", "too", "its", "than", "then", "more",
        "best", "using", "used", "use", "guide", "tips",
    }
    return [word for word in words if len(word) > 2 and word not in stopwords]


def load_config():
    config = load_json_file(CONFIG_FILE, {})
    if not isinstance(config, dict):
        log_error("Invalid channel_config.json format. Expected an object.")
        return {}

    return config


def get_output_path(config, key, fallback_path):
    output_files = config.get("output_files", {})
    if isinstance(output_files, dict):
        return output_files.get(key, fallback_path)
    return fallback_path


def extract_video_text_items(analytics_data):
    if not isinstance(analytics_data, dict):
        return []

    text_items = []

    for key in ("top_videos", "recent_videos"):
        videos = analytics_data.get(key, [])
        if not isinstance(videos, list):
            continue

        for video in videos:
            if not isinstance(video, dict):
                continue

            title = video.get("title", "")
            if title:
                text_items.append(title)

    recommendations = analytics_data.get("recommendations", [])
    if isinstance(recommendations, list):
        for item in recommendations:
            if isinstance(item, str) and item.strip():
                text_items.append(item.strip())

    return text_items


def build_priority_keywords(seed_keywords, analytics_data):
    keyword_scores = {}

    for keyword in seed_keywords:
        normalized = keyword.strip().lower()
        if normalized:
            keyword_scores[normalized] = keyword_scores.get(normalized, 0) + 5

    text_items = extract_video_text_items(analytics_data)
    for text in text_items:
        for word in clean_words(text):
            keyword_scores[word] = keyword_scores.get(word, 0) + 1

    combined_keywords = []
    for keyword in seed_keywords:
        normalized = keyword.strip().lower()
        if normalized and normalized not in combined_keywords:
            combined_keywords.append(normalized)

    ranked_words = sorted(
        keyword_scores.items(),
        key=lambda item: (-item[1], item[0]),
    )

    for keyword, _score in ranked_words:
        if keyword not in combined_keywords:
            combined_keywords.append(keyword)

    return combined_keywords[:12]


def build_title_patterns(priority_keywords):
    base_keywords = priority_keywords[:6] or ["content strategy"]

    patterns = []
    for keyword in base_keywords:
        title_keyword = keyword.title()
        patterns.append(f"How to Improve {title_keyword} Without Guesswork")
        patterns.append(f"{title_keyword} Tips That Actually Help Small Channels")

    deduped = []
    for pattern in patterns:
        if pattern not in deduped:
            deduped.append(pattern)

    return deduped[:8]


def build_description_elements(seed_keywords, priority_keywords):
    primary_seed = seed_keywords[0] if seed_keywords else "content strategy"
    primary_keyword = priority_keywords[0] if priority_keywords else primary_seed

    return [
        "Lead with a 1-2 sentence summary of the video promise.",
        f"Include the primary keyword naturally in the first paragraph: {primary_keyword}.",
        f"Reference a related audience interest or seed theme: {primary_seed}.",
        "Add 3-5 concise bullet points covering the main takeaways.",
        "Close with a clear next step, playlist mention, or subscribe call to action.",
    ]


def build_tag_clusters(seed_keywords, priority_keywords):
    clusters = []

    primary_cluster = []
    for keyword in priority_keywords[:5]:
        if keyword not in primary_cluster:
            primary_cluster.append(keyword)

    strategy_cluster = []
    for keyword in seed_keywords[:5]:
        normalized = keyword.strip().lower()
        if normalized and normalized not in strategy_cluster:
            strategy_cluster.append(normalized)

    audience_cluster = [
        "small channel growth",
        "creator workflow",
        "video publishing plan",
        "audience retention",
        "content planning",
    ]

    if primary_cluster:
        clusters.append({"cluster": "high_intent", "tags": primary_cluster})
    if strategy_cluster:
        clusters.append({"cluster": "seed_topics", "tags": strategy_cluster})
    clusters.append({"cluster": "creator_audience", "tags": audience_cluster})

    return clusters


def build_topic_ideas(seed_keywords, priority_keywords, analytics_data):
    topics = []
    audiences = [
        "new creators",
        "small channel owners",
        "consistent upload teams",
        "marketers building a YouTube presence",
        "creators improving channel performance",
    ]
    ctas = [
        "Ask viewers which tactic they want tested next.",
        "Invite viewers to share their biggest channel challenge.",
        "Point viewers to a related playlist for deeper guidance.",
        "Encourage viewers to subscribe for weekly growth ideas.",
        "Ask viewers to comment with their current content goal.",
    ]

    source_keywords = priority_keywords[:7] or seed_keywords[:5]
    if not source_keywords:
        source_keywords = ["content strategy", "channel analytics", "video promotion"]

    recent_titles = []
    if isinstance(analytics_data, dict):
        recent_videos = analytics_data.get("recent_videos", [])
        if isinstance(recent_videos, list):
            for item in recent_videos:
                if isinstance(item, dict) and item.get("title"):
                    recent_titles.append(item["title"])

    for index, keyword in enumerate(source_keywords[:7]):
        related_keywords = [keyword]
        for extra_keyword in source_keywords:
            if extra_keyword != keyword and extra_keyword not in related_keywords:
                related_keywords.append(extra_keyword)
            if len(related_keywords) >= 3:
                break

        reference_title = recent_titles[index] if index < len(recent_titles) else ""
        angle = f"Actionable breakdown focused on {keyword}"
        if reference_title:
            angle = f"Actionable breakdown inspired by recent channel themes like '{reference_title}'"

        topics.append(
            {
                "topic": f"{keyword.title()} for Sustainable Channel Growth",
                "angle": angle,
                "audience": audiences[index % len(audiences)],
                "keywords": related_keywords,
                "cta": ctas[index % len(ctas)],
            }
        )

    return topics


def generate_keyword_outputs():
    config = load_config()
    seed_keywords = config.get("default_keywords_seed", [])
    if not isinstance(seed_keywords, list):
        log_error("Invalid default_keywords_seed format. Expected a list.")
        seed_keywords = []

    seed_keywords = [keyword.strip().lower() for keyword in seed_keywords if isinstance(keyword, str) and keyword.strip()]

    analytics_path = get_output_path(config, "analytics", os.path.join("output", "channel_analytics.json"))
    seo_path = get_output_path(config, "seo", os.path.join("output", "seo_suggestions.json"))
    topics_path = get_output_path(config, "topics", os.path.join("output", "topic_ideas.json"))

    analytics_data = load_json_file(analytics_path, {})
    if not isinstance(analytics_data, dict):
        analytics_data = {}

    priority_keywords = build_priority_keywords(seed_keywords, analytics_data)
    seo_data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seed_keywords": seed_keywords,
        "high_priority_keywords": priority_keywords,
        "title_patterns": build_title_patterns(priority_keywords),
        "description_elements": build_description_elements(seed_keywords, priority_keywords),
        "tag_clusters": build_tag_clusters(seed_keywords, priority_keywords),
    }

    topic_data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "topics": build_topic_ideas(seed_keywords, priority_keywords, analytics_data),
    }

    save_json_file(seo_path, seo_data)
    save_json_file(topics_path, topic_data)


if __name__ == "__main__":
    try:
        generate_keyword_outputs()
    except Exception as exc:
        log_error(f"Fatal error: {exc}")
        raise