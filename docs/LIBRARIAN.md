# Open Source Librarian Agent

A specialized research agent for external library documentation with evidence-backed responses and verified GitHub permalinks.

## Overview

The Librarian agent provides research capabilities for external open-source libraries. Unlike general web searches, the Librarian:

- **Verifies claims** with GitHub permalinks using commit SHAs
- **Classifies requests** into 4 types for optimized research strategies
- **Never fabricates** - admits uncertainty when evidence is insufficient
- **Uses tiered models** - Haiku for search, Sonnet for synthesis

## Quick Start

```bash
# Basic research query
swarm-attack research "How does React Query handle caching?"

# Quick lookup focused on specific library (options before query)
swarm-attack research --library tenacity --depth quick "retry logic"

# Thorough implementation search with type override
swarm-attack research --library httpx --depth thorough --type implementation "connection pooling"
```

## CLI Options

| Option | Short | Description |
|--------|-------|-------------|
| `--depth` | `-d` | Research depth: quick, medium (default), thorough |
| `--library` | `-l` | Focus on specific library (e.g., 'langchain', 'pydantic') |
| `--type` | `-t` | Override request type: conceptual, implementation, context, comprehensive |

## Request Types

| Type | Trigger Patterns | Tools Used |
|------|------------------|------------|
| **CONCEPTUAL** | "How do I...", "Best practice for..." | WebSearch, context7 |
| **IMPLEMENTATION** | "Show me source of...", "How does X implement..." | gh clone, Read, git blame |
| **CONTEXT** | "Why was this changed?", "History of..." | gh issues/prs, git log |
| **COMPREHENSIVE** | Complex/ambiguous requests | ALL tools in parallel |

## Output Format

```json
{
  "answer": "Markdown formatted response with explanations",
  "citations": [
    {
      "url": "https://github.com/owner/repo/blob/abc123/src/file.ts#L42-L50",
      "context": "The useQuery hook implementation",
      "lines": "L42-L50",
      "commit_sha": "abc123"
    }
  ],
  "confidence": 0.85,
  "tools_used": ["WebSearch", "Bash", "Read"],
  "request_type": "implementation"
}
```

## Evidence Quality Protocol

### GitHub Permalinks

All code citations use verified GitHub permalinks with commit SHAs:

```
https://github.com/{owner}/{repo}/blob/{sha}/{path}#L{start}-L{end}
```

**Why commit SHAs?** Branch names and tags change. Commit SHAs are immutable.

### Uncertainty Handling

When evidence is insufficient, the Librarian:

- Explicitly states "I could not verify this"
- Returns lower confidence score (< 0.5)
- Does NOT fabricate citations

## API Reference

```python
from swarm_attack.agents.librarian import LibrarianAgent, RequestType

agent = LibrarianAgent(config)
result = agent.run({
    "query": "How does React Query handle caching?",
    "libraries": ["tanstack-query"],  # Optional
    "depth": "thorough",              # quick, medium, thorough
    "request_type": "conceptual",     # Optional override
})

if result.success:
    print(result.output["answer"])
    for cite in result.output["citations"]:
        print(f"  - {cite['url']}")
```

## Cost Projections

| Request Type | Estimated Cost |
|--------------|----------------|
| CONCEPTUAL (quick) | ~$0.02 |
| IMPLEMENTATION | ~$0.03 |
| COMPREHENSIVE | ~$0.15-0.25 |
