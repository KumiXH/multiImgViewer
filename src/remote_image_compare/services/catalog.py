from collections.abc import Mapping, Set

from remote_image_compare.domain.models import CompareMode
from remote_image_compare.domain.sorting import natural_key


def build_catalog(entries_by_source: Mapping[str, Set[str]], mode: CompareMode) -> list[str]:
    if not entries_by_source:
        return []

    ordered_sets = list(entries_by_source.values())
    if mode is CompareMode.COMMON:
        result = set.intersection(*map(set, ordered_sets))
    else:
        result = set(ordered_sets[0])
    return sorted(result, key=natural_key)
