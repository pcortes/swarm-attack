"""Sample with hallucinated method - call to non-existent class method."""
from dataclasses import dataclass


@dataclass
class Agent:
    """Simple agent class."""
    name: str

    def run(self, context: dict) -> str:
        return f"Running {self.name}"


def execute_agent(agent: Agent, context: dict) -> str:
    """Execute agent with non-existent method call."""
    # Agent class does not have execute_with_retry method
    result = agent.execute_with_retry(context, max_retries=3)
    return result
