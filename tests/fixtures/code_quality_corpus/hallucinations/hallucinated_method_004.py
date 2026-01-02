"""Sample with hallucinated method - string method that doesn't exist."""


def format_output(text: str) -> str:
    """Format output using non-existent string method."""
    # str has no to_snake_case method
    snake = text.to_snake_case()
    return snake
