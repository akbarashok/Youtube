import os
from datetime import datetime, timezone

from process_video import ensure_file, load_json_file, log_error, save_json_file


CHANNEL_CONFIG_FILE = "channel_config.json"
DEFAULT_OUTPUT_FILE = os.path.join("output", "thumbnail_ideas.json")


def load_channel_config():
    return load_json_file(
        CHANNEL_CONFIG_FILE,
        {
            "default_keywords_seed": [],
            "output_files": {
                "seo": os.path.join("output", "seo_suggestions.json"),
                "topics": os.path.join("output", "topic_ideas.json"),
                "thumbnails": DEFAULT_OUTPUT_FILE,
            },
        },
    )


def get_output_path(config):
    output_files = config.get("output_files", {})
    return output_files.get("thumbnails", DEFAULT_OUTPUT_FILE)


def get_input_paths(config):
    output_files = config.get("output_files", {})
    return {
        "seo": output_files.get("seo", os.path.join("output", "seo_suggestions.json")),
        "topics": output_files.get("topics", os.path.join("output", "topic_ideas.json")),
    }


def normalize_thumbnail_text(text, fallback):
    value = (text or fallback or "Watch This").strip()
    words = value.split()

    if len(words) > 4:
        value = " ".join(words[:4])

    if len(value) > 32:
        value = value[:32].rstrip()

    return value.upper()


def build_topic_based_idea(topic_item, index):
    topic = (topic_item.get("topic") or f"Content Idea {index}").strip()
    angle = (topic_item.get("angle") or "Practical breakdown").strip()
    audience = (topic_item.get("audience") or "Creators looking to improve results").strip()
    keywords = topic_item.get("keywords", [])
    cta = (topic_item.get("cta") or "Watch for the full strategy").strip()

    primary_keyword = ""
    if isinstance(keywords, list) and keywords:
        primary_keyword = str(keywords[0]).strip()

    text_source = primary_keyword or topic
    thumbnail_text = normalize_thumbnail_text(text_source, topic)

    visual_direction = f"Close-up subject with bold contrast text, plus a simple visual cue that highlights {angle.lower()}."
    audience_hook = f"For {audience.lower()} who want clearer, faster takeaways."
    notes = f"Use the title promise and reinforce it with a direct CTA such as '{cta}'."

    return {
        "title": topic,
        "thumbnail_text": thumbnail_text,
        "visual_direction": visual_direction,
        "audience_hook": audience_hook,
        "notes": notes,
    }


def build_keyword_based_idea(keyword, index):
    cleaned_keyword = (keyword or f"Growth Idea {index}").strip()
    title = f"{cleaned_keyword.title()} Explained"
    thumbnail_text = normalize_thumbnail_text(cleaned_keyword, cleaned_keyword)
    visual_direction = f"Use a clean before-and-after layout with emphasis on '{cleaned_keyword}'."
    audience_hook = "Targets viewers who want actionable channel growth improvements."
    notes = "Keep the focal point singular, use high contrast, and avoid overcrowding the frame."

    return {
        "title": title,
        "thumbnail_text": thumbnail_text,
        "visual_direction": visual_direction,
        "audience_hook": audience_hook,
        "notes": notes,
    }


def dedupe_ideas(ideas):
    unique_ideas = []
    seen_titles = set()

    for idea in ideas:
        title = (idea.get("title") or "").strip().lower()
        if not title or title in seen_titles:
            continue
        seen_titles.add(title)
        unique_ideas.append(idea)

    return unique_ideas


def generate_thumbnail_ideas(config, seo_data, topics_data):
    ideas = []

    topics = topics_data.get("topics", []) if isinstance(topics_data, dict) else []
    if isinstance(topics, list):
        for index, topic_item in enumerate(topics[:6], start=1):
            if isinstance(topic_item, dict):
                ideas.append(build_topic_based_idea(topic_item, index))

    if len(ideas) < 6 and isinstance(seo_data, dict):
        keywords = seo_data.get("high_priority_keywords", [])
        if isinstance(keywords, list):
            for index, keyword in enumerate(keywords[:6], start=1):
                if isinstance(keyword, str):
                    ideas.append(build_keyword_based_idea(keyword, index))
                elif isinstance(keyword, dict):
                    value = keyword.get("keyword") or keyword.get("term") or keyword.get("phrase") or ""
                    ideas.append(build_keyword_based_idea(str(value), index))

    if not ideas:
        seed_keywords = config.get("default_keywords_seed", [])
        if isinstance(seed_keywords, list):
            for index, keyword in enumerate(seed_keywords[:6], start=1):
                ideas.append(build_keyword_based_idea(str(keyword), index))

    return dedupe_ideas(ideas)[:6]


def main():
    config = load_channel_config()
    paths = get_input_paths(config)
    output_path = get_output_path(config)

    seo_data = {}
    topics_data = {}

    if os.path.exists(paths["seo"]):
        seo_data = load_json_file(paths["seo"], {})
    else:
        ensure_file(paths["seo"], {})

    if os.path.exists(paths["topics"]):
        topics_data = load_json_file(paths["topics"], {})
    else:
        ensure_file(paths["topics"], {})

    output_data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ideas": generate_thumbnail_ideas(config, seo_data, topics_data),
    }

    save_json_file(output_path, output_data)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        log_error(f"Fatal error in thumbnail_ideas.py: {exc}")
        raise