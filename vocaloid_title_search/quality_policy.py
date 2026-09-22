"""Publication policy shared by DB builds and release preparation."""
from dataclasses import asdict, dataclass
import math
from typing import Mapping


@dataclass(frozen=True)
class QualityPolicy:
    max_count_drop: float = 0.20
    max_coverage_drop: float = 0.10
    min_video_success_rate: float = 0.80

    def __post_init__(self) -> None:
        for name, value in asdict(self).items():
            if not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 1")


def compare_counts(current: Mapping[str, int], previous: Mapping[str, int], policy: QualityPolicy) -> tuple[dict[str, dict[str, int]], list[str]]:
    errors = []
    changes = {}
    for key in ("songs", "songs_with_composer", "songs_with_published_year", "niconico_unique_videos", "youtube_unique_videos"):
        old, new = previous.get(key, 0), current.get(key, 0)
        changes[key] = {"before": old, "after": new}
        if old and (old - new) / old > policy.max_count_drop:
            errors.append(f"{key} decreased beyond {policy.max_count_drop:.0%}: {old} -> {new}")
    for key in ("songs_with_composer", "songs_with_published_year"):
        old = previous.get(key, 0) / max(previous.get("songs", 0), 1)
        new = current.get(key, 0) / max(current.get("songs", 0), 1)
        if old - new > policy.max_coverage_drop:
            errors.append(f"{key} coverage decreased: {old:.1%} -> {new:.1%}")
    return changes, errors


def video_refresh_errors(metadata: Mapping[str, str], service: str, total: int, policy: QualityPolicy,
                         previous: Mapping[str, str] | None = None) -> list[str]:
    prefix = f"video_metadata_{service}_"
    errors = []
    try:
        success, failure, fallback = (int(metadata.get(prefix + key, "-1")) for key in ("success", "failure", "fallback"))
        if min(success, failure, fallback) < 0 or success + failure + fallback != total:
            return [f"{service} metadata result counts are inconsistent"]
        rate = success / total
        if not success or rate < policy.min_video_success_rate:
            errors.append(f"{service} metadata success rate {rate:.1%} is below {policy.min_video_success_rate:.0%}")
        if previous and previous.get(prefix + "total"):
            old_total = int(previous[prefix + "total"])
            old_success = int(previous.get(prefix + "success", "0"))
            if old_total and old_success / old_total - rate > policy.max_coverage_drop:
                errors.append(f"{service} metadata success rate decreased beyond {policy.max_coverage_drop:.0%}")
    except (ValueError, ZeroDivisionError):
        errors.append(f"{service} metadata result counts are invalid")
    return errors
