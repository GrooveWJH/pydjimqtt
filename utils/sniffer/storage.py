"""JSON persistence for MQTT sniffer captures."""

import json
import time
from datetime import datetime
from pathlib import Path


def _topic_statistics(sniffer, topic: str) -> dict:
    stats = sniffer.topic_stats[topic]
    return {
        method: {
            "count": stats["message_counts"][method],
            "frequency_hz": sniffer.get_frequency(topic, method),
            "first_time": datetime.fromtimestamp(stats["first_time"][method]).isoformat()
            if method in stats["first_time"]
            else None,
            "last_time": datetime.fromtimestamp(stats["last_time"][method]).isoformat()
            if method in stats["last_time"]
            else None,
        }
        for method in sorted(stats["message_counts"].keys())
    }


def _write_json(path: Path, payload: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def save_to_directory(sniffer, base_dir: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(base_dir) / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)

    for topic in sniffer.topics:
        stats = sniffer.topic_stats[topic]
        if stats["total_count"] == 0:
            continue
        topic_name = topic.split("/")[-1] if "/" in topic else topic
        _write_json(
            output_dir / f"{topic_name}.json",
            {
                "metadata": {
                    "topic": topic,
                    "gateway_sn": sniffer.mqtt.gateway_sn,
                    "capture_time": datetime.now().isoformat(),
                    "runtime_seconds": time.time() - sniffer.start_time,
                    "total_messages": stats["total_count"],
                    "message_types": len(stats["message_counts"]),
                },
                "statistics": _topic_statistics(sniffer, topic),
                "latest_messages": stats["latest_messages"],
            },
        )

    _write_summary(sniffer, output_dir)
    return output_dir


def _write_summary(sniffer, output_dir: Path) -> None:
    summary = {
        "capture_info": {
            "gateway_sn": sniffer.mqtt.gateway_sn,
            "capture_time": datetime.now().isoformat(),
            "runtime_seconds": time.time() - sniffer.start_time,
            "topics": sniffer.topics,
        },
        "statistics": {
            topic.split("/")[-1]: {
                "full_topic": topic,
                "total_messages": sniffer.topic_stats[topic]["total_count"],
                "message_types": len(sniffer.topic_stats[topic]["message_counts"]),
                "methods": list(sniffer.topic_stats[topic]["message_counts"].keys()),
            }
            for topic in sniffer.topics
        },
    }
    _write_json(output_dir / "_summary.json", summary)
