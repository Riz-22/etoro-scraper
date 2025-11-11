from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Union

def _flatten_value(value: Any) -> Any:
    """
    Flatten values that are not simple scalars into JSON strings
    so they can be written into CSV cells.
    """
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return value
    return json.dumps(value, ensure_ascii=False)

def export_to_csv(
    records: Iterable[Dict[str, Any]],
    output_path: Union[str, Path],
    fieldnames: Sequence[str],
) -> Path:
    """
    Export records to a CSV file.

    - fieldnames controls column order.
    - Non-scalar values are JSON-encoded into a string.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    records_list: List[Dict[str, Any]] = list(records)

    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for record in records_list:
            flat_row = {field: _flatten_value(record.get(field)) for field in fieldnames}
            writer.writerow(flat_row)

    return path