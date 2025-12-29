"""
Tests for LLM code extraction (BUG-2/BUG-6).

Ensures that code extraction from LLM responses strips explanations
and returns only valid, parseable code.
"""

import ast

import pytest

from swarm_attack.agents.coder import extract_code_from_response


class TestExtractCodeFromResponse:
    """Tests for extract_code_from_response function."""

    def test_extracts_only_code_blocks(self):
        """BUG-2: LLM explanations must not leak into extracted code."""
        response = '''
Here's the implementation:

```python
def foo():
    return 42
```

Now I'll explain what this does...
'''
        extracted = extract_code_from_response(response)
        assert "def foo" in extracted
        assert "explain" not in extracted.lower()
        ast.parse(extracted)  # Must be valid Python

    def test_extracts_multiple_code_blocks(self):
        """Multiple code blocks should be joined."""
        response = '''
First, the model:

```python
class User:
    def __init__(self, name):
        self.name = name
```

Then, the service:

```python
class UserService:
    def get_user(self, id):
        return User("test")
```

That's all!
'''
        extracted = extract_code_from_response(response)
        assert "class User" in extracted
        assert "class UserService" in extracted
        assert "First" not in extracted
        assert "That's all" not in extracted
        ast.parse(extracted)  # Must be valid Python

    def test_handles_empty_response(self):
        """Empty response should return empty string."""
        assert extract_code_from_response("") == ""
        assert extract_code_from_response("   ") == ""

    def test_handles_no_code_blocks(self):
        """Response without code blocks returns empty."""
        response = "Here's some explanation without any code."
        extracted = extract_code_from_response(response)
        assert extracted == ""

    def test_handles_different_language_fences(self):
        """Should handle various language specifiers."""
        response = '''
```py
x = 1
```
'''
        extracted = extract_code_from_response(response)
        assert "x = 1" in extracted

    def test_handles_bare_code_fence(self):
        """Should handle code fence without language specifier."""
        response = '''
```
def test():
    pass
```
'''
        extracted = extract_code_from_response(response)
        assert "def test" in extracted

    def test_preserves_code_formatting(self):
        """Should preserve indentation and formatting."""
        response = '''
```python
def foo():
    if True:
        return 42
    else:
        return 0
```
'''
        extracted = extract_code_from_response(response)
        assert "    if True:" in extracted
        assert "        return 42" in extracted
        ast.parse(extracted)
