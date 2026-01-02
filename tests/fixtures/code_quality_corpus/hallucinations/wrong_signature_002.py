"""Sample with wrong signature - open with wrong parameters."""


def read_file(path: str) -> str:
    """Read file with wrong parameter."""
    # open doesn't have 'binary' parameter, should be mode='rb'
    with open(path, binary=True) as f:
        content = f.read()
    return content
