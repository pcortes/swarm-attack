"""Sample with wrong signature - subprocess.run with wrong parameters."""
import subprocess


def run_command(cmd: str) -> str:
    """Run command with wrong parameter."""
    # subprocess.run doesn't have 'return_output' parameter
    result = subprocess.run(cmd, shell=True, return_output=True)
    return result.stdout
