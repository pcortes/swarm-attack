"""Sample with hallucinated import - made up helper module."""
from swarm_attack.helpers.magic_utils import auto_validate, magic_parse


def process_data(data: dict) -> dict:
    """Process data using non-existent utilities."""
    validated = auto_validate(data)
    return magic_parse(validated)
