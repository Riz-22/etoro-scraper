from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Union

def export_to_json(
    records: Iterable[Dict[str, Any]],
    output_path: Union[str, Path],
    indent: int = 2,
) -> Path:
    """
    Export records to a JSON file.

    The JSON representation is a list of objects, one per record.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    records_list: List[Dict[str, Any]] = list(records)

    with path.open("w", encoding="utf-8") as f:
        json.dump(records_list, f, indent=indent, ensure_ascii=False)

    return path