"""Sample with missing error handling - subprocess operations."""
import subprocess


def run_shell_command(cmd: str) -> str:
    """Run shell command - no error handling."""
    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True
    )  # No try/except - could raise CalledProcessError
    return result.stdout


def execute_script(script_path: str) -> int:
    """Execute script - no error handling."""
    process = subprocess.Popen(
        ["python", script_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )  # No try/except - FileNotFoundError possible
    process.wait()
    return process.returncode
