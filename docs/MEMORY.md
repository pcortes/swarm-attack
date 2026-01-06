# Memory System

The Swarm Attack Memory System provides persistent cross-session learning for agents. It enables agents to learn from past successes and failures, detect recurring patterns, and provide contextual recommendations.

## Architecture Overview

```
                    ┌─────────────────────┐
                    │    MemoryStore      │  ← Core persistence layer
                    │   (JSON storage)    │
                    └─────────┬───────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐   ┌─────────────────┐   ┌─────────────────┐
│PatternDetector│   │MemoryIndex      │   │SemanticSearch   │
│  (patterns)   │   │(inverted index) │   │(keyword search) │
└───────┬───────┘   └─────────────────┘   └─────────────────┘
        │
        ▼
┌─────────────────────┐
│RecommendationEngine │  ← Agent-facing API
│  (suggestions)      │
└─────────────────────┘
```

## Components

### MemoryStore (`store.py`)

The core persistence layer for memory entries. JSON-based storage with keyword matching.

```python
from swarm_attack.memory.store import MemoryStore, MemoryEntry

# Load existing store (creates if not exists)
store = MemoryStore.load()

# Add an entry
entry = MemoryEntry(
    category="schema_drift",
    feature_id="my-feature",
    content={"class_name": "MyClass", "drift_type": "missing_method"},
    tags=["drift", "MyClass"],
    outcome="failure",
)
store.add(entry)

# Query entries
results = store.query(category="schema_drift", feature_id="my-feature", limit=10)

# Save to disk
store.save()
```

**Memory Categories:**
| Category | Purpose |
|----------|---------|
| `schema_drift` | LLM-generated code violated existing patterns |
| `test_failure` | Test execution failures |
| `recovery_pattern` | Successful recovery from issues |
| `implementation_success` | Successful implementations |
| `bug_pattern` | Recurring bug patterns |

### PatternDetector (`patterns.py`)

Analyzes memory entries to detect recurring patterns across sessions.

```python
from swarm_attack.memory.patterns import PatternDetector

detector = PatternDetector(store)

# Detect schema drift patterns
drift_patterns = detector.detect_schema_drift_patterns(
    time_window_days=30,
    min_occurrences=3,
)

# Detect fix patterns
fix_patterns = detector.detect_fix_patterns(
    time_window_days=30,
    min_occurrences=2,
)

# Detect test failure clusters
clusters = detector.detect_failure_clusters(
    time_window_days=7,
)

# Unified pattern detection (returns DetectedPattern objects)
all_patterns = detector.detect_patterns(
    category="schema_drift",
    time_window_days=30,
    min_occurrences=3,
)
```

**Pattern Types:**
| Type | Description |
|------|-------------|
| `SchemaDriftPattern` | Recurring schema violations for a class |
| `FixPattern` | Commonly applied fixes |
| `FailureCluster` | Clusters of related test failures |
| `VerificationPattern` | Success/failure patterns from verifier |

### RecommendationEngine (`recommendations.py`)

Provides actionable recommendations based on historical patterns.

```python
from swarm_attack.memory.recommendations import RecommendationEngine

engine = RecommendationEngine(store, pattern_detector=detector)

# Get recommendations for a current issue
recommendations = engine.get_recommendations(
    current_issue={
        "error_type": "AttributeError",
        "context": {"class_name": "MyClass"},
        "tags": ["schema_drift"],
    },
    limit=3,
)

for rec in recommendations:
    print(f"Suggestion: {rec.suggestion}")
    print(f"Confidence: {rec.confidence:.2f}")
    print(f"Context: {rec.context}")

# Get recommendations for schema drift specifically
drift_recs = engine.get_schema_drift_recommendations(
    class_name="MyClass",
    limit=3,
)
```

### SemanticSearch (`search.py`)

Advanced search with weighted keyword matching.

```python
from swarm_attack.memory.search import SemanticSearch

search = SemanticSearch(store)

# Search with keyword weighting
results = search.search(
    query="AttributeError MyClass missing method",
    category="schema_drift",  # Optional: boost/filter by category
    limit=10,
)

for result in results:
    print(f"Entry: {result.entry.id}")
    print(f"Score: {result.score:.2f}")
    print(f"Matched: {result.matched_keywords}")
```

**Keyword Weights:**
| Keyword | Weight | Purpose |
|---------|--------|---------|
| `error`, `fail`, `exception` | 2.0x | High-priority error terms |
| `class`, `method`, `import` | 1.5x | Code structure terms |

**Scoring Factors:**
- **Category Boost**: 1.5x for matching category
- **Exact Match Boost**: 2.0x for exact phrase matches
- **Recency Factor**: 0.95 decay per 24 hours

### MemoryIndex (`index.py`)

Inverted index for O(1) keyword lookup (vs O(n) scanning).

```python
from swarm_attack.memory.index import MemoryIndex

# Index is built automatically from store
index = MemoryIndex(store)

# Fast keyword lookup
entry_ids = index.lookup("MyClass")

# Compound queries (intersection)
entry_ids = index.lookup_all(["error", "MyClass"])

# Rebuild index after bulk changes
index.rebuild()

# Persist index
index.save()
```

**Index Features:**
- Persists to `index.json` alongside store
- Auto-rebuilds on version mismatch
- Updates on entry add/delete
- Indexes: content, tags, category, feature_id

## Agent Integration

### CoderAgent

Receives historical recommendations before implementation.

```python
from swarm_attack.memory.store import MemoryStore
from swarm_attack.memory.recommendations import RecommendationEngine
from swarm_attack.agents.coder import CoderAgent

memory = MemoryStore.load()
engine = RecommendationEngine(memory)
coder = CoderAgent(config, memory_store=memory)

# Coder automatically:
# 1. Extracts class names from issue body
# 2. Queries memory for prior schema drift conflicts
# 3. Injects warnings into prompt
```

### VerifierAgent

Records success/failure patterns to memory.

```python
from swarm_attack.memory.patterns import VerificationPattern
from swarm_attack.agents.verifier import VerifierAgent

verifier = VerifierAgent(config, memory_store=memory)

# Verifier automatically records:
# - Success patterns (tests passed, what worked)
# - Failure patterns (tests failed, error messages)
# - Links patterns to fixes for future recommendations
```

## CLI Commands

### Basic Commands

```bash
# Show memory statistics
swarm-attack memory stats

# List entries (with optional filters)
swarm-attack memory list
swarm-attack memory list --category schema_drift
swarm-attack memory list --feature my-feature --limit 10

# Prune old entries
swarm-attack memory prune --older-than 30
```

### Persistence Commands

```bash
# Save memory to file (path is positional argument)
swarm-attack memory save /path/to/backup.json

# Load memory from file
swarm-attack memory load /path/to/backup.json

# Export to JSON (filtered)
swarm-attack memory export drift.json --category schema_drift

# Import from JSON (merge)
swarm-attack memory import drift.json
```

### Advanced Commands

```bash
# Compress memory (deduplicate/summarize)
swarm-attack memory compress

# Show analytics report
swarm-attack memory analytics

# Detect patterns
swarm-attack memory patterns
swarm-attack memory patterns --category schema_drift

# Get recommendations (category is positional, context is optional)
swarm-attack memory recommend schema_drift --context '{"class_name": "MyClass"}'

# Search entries
swarm-attack memory search "AttributeError missing method"
swarm-attack memory search "MyClass" --category schema_drift --limit 5
```

## Design Decisions

### PatternDetector Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `time_window_days` | 30 | Window for pattern detection |
| `min_occurrences` | 3 | Minimum occurrences for pattern |
| Confidence formula | `occurrences / (time_span_days * decay_factor)` | Higher = more confident |

### RecommendationEngine Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `limit` | 3 | Top N recommendations |
| Category filtering | By category + context similarity | Filters relevant history |
| Sorting | By confidence (highest first) | Most confident first |

### SemanticSearch Settings

| Setting | Default | Description |
|---------|---------|-------------|
| Keyword weights | error=2.0, fail=2.0, class=1.5 | Weighted scoring |
| Category boost | 1.5x | Same category boost |
| Recency decay | 0.95 per day | Exponential decay |
| Default limit | 10 | Max results |

### MemoryIndex Settings

| Setting | Default | Description |
|---------|---------|-------------|
| Version | "1.0" | Format version (auto-rebuild on mismatch) |
| Index location | `index.json` alongside store | Persistent file |
| Update strategy | On add/delete | Incremental updates |

## Configuration

Memory file location in `config.yaml`:

```yaml
memory:
  file_path: .swarm/memory/store.json  # Default location
```

## Testing

Run all memory tests:

```bash
# Unit tests (262 tests)
python -m pytest tests/unit/memory/ -v

# Integration tests (21 tests)
python -m pytest tests/integration/test_memory_e2e.py -v

# CLI tests (34 tests)
python -m pytest tests/unit/cli/test_memory_cli.py -v

# Agent integration tests
python -m pytest tests/unit/test_coder_recommendations.py tests/unit/test_verifier_patterns.py -v
```

## File Reference

| File | Purpose |
|------|---------|
| `swarm_attack/memory/__init__.py` | Public API exports |
| `swarm_attack/memory/store.py` | MemoryStore and MemoryEntry |
| `swarm_attack/memory/patterns.py` | PatternDetector and pattern types |
| `swarm_attack/memory/recommendations.py` | RecommendationEngine |
| `swarm_attack/memory/search.py` | SemanticSearch |
| `swarm_attack/memory/index.py` | MemoryIndex |
| `swarm_attack/memory/categories.py` | Category constants |
| `swarm_attack/memory/relevance.py` | Relevance scoring |
| `swarm_attack/memory/analytics.py` | Analytics and reporting |
| `swarm_attack/memory/compression.py` | Entry compression |
| `swarm_attack/memory/export.py` | Export/import utilities |
| `swarm_attack/cli/memory.py` | CLI commands |
