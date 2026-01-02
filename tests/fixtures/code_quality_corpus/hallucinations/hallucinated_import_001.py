"""Sample with hallucinated import - non-existent module."""
from swarm_attack.utils.nonexistent_module import fake_function


def use_fake():
    """Use a function that doesn't exist."""
    return fake_function()
