"""Sample with bare except - with re-raise but still problematic."""
import logging


def risky_function(data: str) -> str:
    """Bare except with logging - still catches too much."""
    try:
        result = data.encode("utf-8").decode("ascii")
        return result
    except:  # Bare except is still bad even with logging
        logging.error("An error occurred")
        raise  # Re-raising but already logged potentially sensitive info
