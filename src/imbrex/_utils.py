from typing import Any

_MISSING = object()  # sentinel distinct from None


def _get_path(data: dict[str, Any], path: str, sentinel: object) -> Any:
    """Walk a dot-separated path through nested dicts and lists."""
    if not path:
        return data
    node: Any = data
    for part in path.split("."):
        if node is sentinel:
            return sentinel
        if isinstance(node, list):
            try:
                node = node[int(part)]
            except (ValueError, IndexError):
                return sentinel
        elif isinstance(node, dict):
            if part not in node:
                return sentinel
            node = node[part]
        else:
            return sentinel  # scalar — can't descend further
    return node


def _set_path(data: dict[str, Any], path: str, value: Any) -> None:
    """Write *value* at *path*, creating intermediate dicts as needed."""
    parts = path.split(".")
    node: Any = data
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = value
