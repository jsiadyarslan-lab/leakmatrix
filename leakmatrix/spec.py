"""OpenAPI/Swagger spec parsing -> flat list of operations."""

import json
from dataclasses import dataclass, field
from typing import Iterator, Optional

import requests

ID_PARAM_RE = ("id", "guid", "uuid", "number", "ref")


@dataclass
class Operation:
    method: str
    path: str          # full URL template, e.g. https://host/api/customers/{customerId}
    param_names: list = field(default_factory=list)   # id-like path params in order
    rel_path: str = ""  # path as written in the spec (for readable labels)

    @property
    def label(self) -> str:
        return f"{self.method.upper()} {self.rel_path or self.path}"


def _parse_spec_text(text: str) -> dict:
    """JSON first; YAML fallback when PyYAML is installed."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            import yaml  # optional dependency
        except ImportError:
            raise ValueError(
                "spec is not valid JSON; if it is YAML, install PyYAML: "
                "pip install pyyaml")
        data = yaml.safe_load(text)
        if not isinstance(data, dict):
            raise ValueError("spec did not parse into a JSON/YAML object")
        return data


def load_spec(source: str, timeout: int = 30) -> dict:
    """Load a spec from URL or local file path (JSON, or YAML with PyYAML)."""
    if source.startswith(("http://", "https://")):
        resp = requests.get(source, timeout=timeout,
                            headers={"User-Agent": "LeakMatrix/0.2"})
        resp.raise_for_status()
        return _parse_spec_text(resp.text)
    with open(source, "r", encoding="utf-8") as fh:
        return _parse_spec_text(fh.read())


def base_url_of(spec: dict, override: Optional[str] = None) -> str:
    if override:
        return override.rstrip("/")
    if spec.get("openapi", "").startswith("3"):
        servers = spec.get("servers") or [{"url": "/"}]
        return servers[0]["url"].rstrip("/")
    scheme = (spec.get("schemes") or ["https"])[0]
    host = spec.get("host", "localhost")
    base = spec.get("basePath", "")
    return f"{scheme}://{host}{base}".rstrip("/")


def _is_id_like(name: str) -> bool:
    n = name.lower()
    if n in ("id", "guid", "uuid"):
        return True
    return n.endswith(("id", "guid", "uuid")) or any(k in n for k in ID_PARAM_RE)


def _resolve_param(spec: dict, p):
    """Resolve {'$ref': '#/components/parameters/X'} to the actual object."""
    if not isinstance(p, dict):
        return None
    ref = p.get("$ref")
    if ref:
        if not str(ref).startswith("#/components/parameters/"):
            return None
        name = str(ref).rsplit("/", 1)[-1]
        return ((spec.get("components") or {}).get("parameters") or {}).get(name)
    return p


def iter_operations(spec: dict, base_url: str,
                    only_methods=("get",)) -> Iterator[Operation]:
    """Yield operations that carry at least one id-like path parameter.

    Handles OpenAPI3 path-item-level parameters and $ref parameter objects —
    both extremely common in real specs.

    Operation.path is the FULL URL template (base + path), ready to
    receive substitutions like /customers/{customerId}.
    """
    want = {m.lower() for m in only_methods}
    import re
    for path, item in (spec.get("paths") or {}).items():
        if not isinstance(item, dict):
            continue
        full = base_url + path if path.startswith("/") else base_url + "/" + path
        shared = [p for p in (item.get("parameters") or [])
                  if isinstance(p, dict)]
        for method, op in item.items():
            if method.lower() not in want or not isinstance(op, dict):
                continue
            id_params, seen = [], set()
            for raw in shared + list(op.get("parameters") or []):
                p = _resolve_param(spec, raw)
                if not p or p.get("in") != "path":
                    continue
                name = p.get("name", "")
                if name and name not in seen and _is_id_like(name):
                    seen.add(name)
                    id_params.append(name)
            for m in re.findall(r"{([^}]+)}", path):
                if m not in id_params and _is_id_like(m):
                    id_params.append(m)
            if id_params:
                yield Operation(method=method.upper(), path=full,
                                param_names=id_params, rel_path=path)
