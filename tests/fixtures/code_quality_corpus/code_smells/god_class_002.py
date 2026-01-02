"""Sample with god class code smell - utility class doing too much."""
import os
import json
import hashlib
import base64
import re
from typing import Any, Dict, List, Optional
from datetime import datetime


class UtilityBag:
    """A utility bag that has become a god class."""

    # ========== STRING UTILITIES ==========
    @staticmethod
    def to_snake_case(s: str) -> str:
        return re.sub(r'(?<!^)(?=[A-Z])', '_', s).lower()

    @staticmethod
    def to_camel_case(s: str) -> str:
        parts = s.split('_')
        return parts[0] + ''.join(p.title() for p in parts[1:])

    @staticmethod
    def truncate(s: str, length: int) -> str:
        return s[:length] + "..." if len(s) > length else s

    @staticmethod
    def slugify(s: str) -> str:
        return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')

    # ========== FILE UTILITIES ==========
    @staticmethod
    def read_json(path: str) -> Dict:
        with open(path) as f:
            return json.load(f)

    @staticmethod
    def write_json(path: str, data: Dict) -> None:
        with open(path, 'w') as f:
            json.dump(data, f)

    @staticmethod
    def file_exists(path: str) -> bool:
        return os.path.exists(path)

    @staticmethod
    def get_file_size(path: str) -> int:
        return os.path.getsize(path)

    # ========== HASH UTILITIES ==========
    @staticmethod
    def md5(s: str) -> str:
        return hashlib.md5(s.encode()).hexdigest()

    @staticmethod
    def sha256(s: str) -> str:
        return hashlib.sha256(s.encode()).hexdigest()

    # ========== ENCODING UTILITIES ==========
    @staticmethod
    def base64_encode(s: str) -> str:
        return base64.b64encode(s.encode()).decode()

    @staticmethod
    def base64_decode(s: str) -> str:
        return base64.b64decode(s.encode()).decode()

    # ========== DATE UTILITIES ==========
    @staticmethod
    def now_iso() -> str:
        return datetime.now().isoformat()

    @staticmethod
    def parse_date(s: str) -> datetime:
        return datetime.fromisoformat(s)

    @staticmethod
    def days_between(d1: datetime, d2: datetime) -> int:
        return abs((d2 - d1).days)

    # ========== COLLECTION UTILITIES ==========
    @staticmethod
    def flatten(nested: List[List]) -> List:
        return [item for sublist in nested for item in sublist]

    @staticmethod
    def chunk(items: List, size: int) -> List[List]:
        return [items[i:i + size] for i in range(0, len(items), size)]

    @staticmethod
    def unique(items: List) -> List:
        return list(set(items))

    @staticmethod
    def group_by(items: List[Dict], key: str) -> Dict[str, List]:
        groups = {}
        for item in items:
            k = item.get(key)
            if k not in groups:
                groups[k] = []
            groups[k].append(item)
        return groups

    # ========== VALIDATION UTILITIES ==========
    @staticmethod
    def is_email(s: str) -> bool:
        return bool(re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', s))

    @staticmethod
    def is_url(s: str) -> bool:
        return s.startswith('http://') or s.startswith('https://')

    @staticmethod
    def is_uuid(s: str) -> bool:
        return bool(re.match(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
            s, re.I
        ))

    # ========== MATH UTILITIES ==========
    @staticmethod
    def clamp(value: float, min_val: float, max_val: float) -> float:
        return max(min_val, min(max_val, value))

    @staticmethod
    def percentage(part: float, whole: float) -> float:
        return (part / whole * 100) if whole else 0

    @staticmethod
    def average(values: List[float]) -> float:
        return sum(values) / len(values) if values else 0
