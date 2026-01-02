"""Sample with copy-paste code smell - duplicated error handling."""
import json
import logging
from typing import Optional, Dict


def load_user_config(path: str) -> Optional[Dict]:
    """Load user config with duplicated error handling."""
    try:
        with open(path) as f:
            data = json.load(f)
        if not data:
            logging.error(f"Empty config file: {path}")
            return None
        if "version" not in data:
            logging.error(f"Missing version in config: {path}")
            return None
        logging.info(f"Loaded config from: {path}")
        return data
    except FileNotFoundError:
        logging.error(f"Config file not found: {path}")
        return None
    except json.JSONDecodeError as e:
        logging.error(f"Invalid JSON in config {path}: {e}")
        return None
    except Exception as e:
        logging.error(f"Failed to load config {path}: {e}")
        return None


def load_app_config(path: str) -> Optional[Dict]:
    """Load app config with same duplicated error handling."""
    try:
        with open(path) as f:
            data = json.load(f)
        if not data:
            logging.error(f"Empty config file: {path}")
            return None
        if "version" not in data:
            logging.error(f"Missing version in config: {path}")
            return None
        logging.info(f"Loaded config from: {path}")
        return data
    except FileNotFoundError:
        logging.error(f"Config file not found: {path}")
        return None
    except json.JSONDecodeError as e:
        logging.error(f"Invalid JSON in config {path}: {e}")
        return None
    except Exception as e:
        logging.error(f"Failed to load config {path}: {e}")
        return None


def load_env_config(path: str) -> Optional[Dict]:
    """Load env config with yet another copy of error handling."""
    try:
        with open(path) as f:
            data = json.load(f)
        if not data:
            logging.error(f"Empty config file: {path}")
            return None
        if "version" not in data:
            logging.error(f"Missing version in config: {path}")
            return None
        logging.info(f"Loaded config from: {path}")
        return data
    except FileNotFoundError:
        logging.error(f"Config file not found: {path}")
        return None
    except json.JSONDecodeError as e:
        logging.error(f"Invalid JSON in config {path}: {e}")
        return None
    except Exception as e:
        logging.error(f"Failed to load config {path}: {e}")
        return None
