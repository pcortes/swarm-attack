"""Sample with hallucinated import - fake third-party package."""
from anthropic_extensions import ClaudeEnhancer, PromptOptimizer


class AIProcessor:
    """Uses non-existent anthropic extension package."""

    def __init__(self):
        self.enhancer = ClaudeEnhancer()
        self.optimizer = PromptOptimizer()

    def process(self, prompt: str) -> str:
        optimized = self.optimizer.optimize(prompt)
        return self.enhancer.enhance(optimized)
