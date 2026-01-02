"""Sample with long method code smell - complex parsing logic."""
from typing import Optional


def parse_log_entry(line: str) -> Optional[dict]:
    """Parse a log entry - way too long."""
    if not line:
        return None
    if line.startswith("#"):
        return None
    if len(line) < 10:
        return None

    # Try to split by common delimiters
    parts = None
    if "|" in line:
        parts = line.split("|")
    elif "\t" in line:
        parts = line.split("\t")
    elif "," in line:
        parts = line.split(",")
    else:
        parts = line.split()

    if len(parts) < 3:
        return None

    # Parse timestamp
    timestamp = parts[0].strip()
    if not timestamp:
        return None
    if len(timestamp) < 8:
        return None

    # Parse level
    level = parts[1].strip().upper()
    if level not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
        level = "INFO"

    # Parse message
    message = " ".join(parts[2:]).strip()
    if not message:
        return None

    # Parse metadata
    metadata = {}
    if "[" in message and "]" in message:
        start = message.index("[")
        end = message.index("]")
        meta_str = message[start + 1:end]
        for item in meta_str.split(";"):
            if "=" in item:
                k, v = item.split("=", 1)
                metadata[k.strip()] = v.strip()
        message = message[:start].strip()

    # Build result
    result = {
        "timestamp": timestamp,
        "level": level,
        "message": message,
        "metadata": metadata,
        "raw": line,
        "length": len(line),
        "word_count": len(message.split()),
    }

    return result
