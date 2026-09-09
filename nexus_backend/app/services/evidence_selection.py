"""Select diverse evidence under the same budget used by the writer context."""

import hashlib
import re


def select_evidence(records, topics, *, max_records=24, max_characters=24000):
    unique = {}
    for record in sorted(records, key=lambda item: item.score, reverse=True):
        digest = hashlib.sha256(re.sub(r"\s+", "", record.excerpt).encode()).hexdigest()
        if not record.excerpt.strip():
            continue
        if digest in unique:
            kept = unique[digest]
            kept.purposes = list(dict.fromkeys([*kept.purposes, *record.purposes]))
        else:
            unique[digest] = record.model_copy(deep=True)
    candidates = list(unique.values())
    ordered = []
    seen = set()

    def include(record):
        key = (record.document_id, record.chunk_id)
        if key not in seen:
            seen.add(key)
            ordered.append(record)

    for topic in topics:
        match = next((row for row in candidates if topic in row.purposes), None)
        if match:
            include(match)
    for document_id in dict.fromkeys(row.document_id for row in candidates):
        include(next(row for row in candidates if row.document_id == document_id))
    for record in candidates:
        include(record)

    selected = []
    used = 0
    for record in ordered:
        # Keep complete compiler passages/table rows; the total context is bounded below.
        cost = (
            len(record.excerpt)
            + len(record.title)
            + len(record.citation_id)
            + sum(map(len, record.purposes))
            + 160
        )
        if used + cost > max_characters:
            continue
        selected.append(record)
        used += cost
        if len(selected) >= max_records:
            break
    return selected
