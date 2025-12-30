"""StateGatherer for aggregating repository state from all data sources."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional


@dataclass
class GitState:
    """Git repository state."""
    
    current_branch: str
    status: str
    modified_files: list[str]
    recent_commits: list[str]
    ahead: int
    behind: int
    
    @classmethod
    def empty(cls) -> GitState:
        """Create empty GitState for error cases."""
        return cls(
            current_branch="",
            status="",
            modified_files=[],
            recent_commits=[],
            ahead=0,
            behind=0,
        )


@dataclass
class FeatureSummary:
    """Summary of a feature's state."""
    
    feature_id: str
    phase: str
    issue_count: int = 0
    completed_issues: int = 0


@dataclass
class BugSummary:
    """Summary of a bug investigation."""
    
    bug_id: str
    phase: str
    description: str = ""


@dataclass
class PRDSummary:
    """Summary of a PRD."""
    
    name: str
    title: str = ""
    status: str = "unknown"


@dataclass
class SpecSummary:
    """Summary of a spec."""
    
    name: str
    has_draft: bool = False
    has_final: bool = False
    review_status: str = "unknown"


@dataclass
class SuiteMetrics:
    """Test suite state metrics (BUG-13/14: renamed from TestSuiteMetrics)."""

    total_tests: int
    test_files: list[str] = field(default_factory=list)


# BUG-13/14: Backward compatibility aliases (not class definitions, so pytest won't collect)
TestSuiteMetrics = SuiteMetrics
TestState = SuiteMetrics


@dataclass
class GitHubState:
    """GitHub repository state."""
    
    open_prs: list[dict[str, Any]] = field(default_factory=list)
    open_issues: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class InterruptedSession:
    """An interrupted/paused session."""
    
    session_id: str
    feature_id: str
    state: str
    timestamp: datetime


@dataclass
class RepoStateSnapshot:
    """Complete snapshot of repository state."""
    
    git: GitState
    features: list[FeatureSummary]
    bugs: list[BugSummary]
    prds: list[PRDSummary]
    specs: list[SpecSummary]
    tests: SuiteMetrics
    github: Optional[GitHubState]
    interrupted_sessions: list[InterruptedSession]
    cost_today: float
    cost_weekly: float
    timestamp: datetime


class StateGatherer:
    """Aggregates state from all repository data sources."""
    
    def __init__(self, config: Any) -> None:
        """Initialize with configuration.
        
        Args:
            config: SwarmConfig instance with project settings.
        """
        self.config = config
        self._root = Path.cwd()
    
    def gather(self, include_github: bool = False) -> RepoStateSnapshot:
        """Gather complete repository state snapshot.
        
        Args:
            include_github: Whether to query GitHub API.
            
        Returns:
            Complete RepoStateSnapshot with all gathered state.
        """
        git_state = self.gather_git_state()
        features = self.gather_features()
        bugs = self.gather_bugs()
        prds = self.gather_prds()
        specs = self.gather_specs()
        tests = self.gather_tests()
        interrupted = self.gather_interrupted_sessions()
        cost_today, cost_weekly = self.calculate_costs()
        
        github_state = None
        if include_github:
            github_state = self.gather_github()
        
        return RepoStateSnapshot(
            git=git_state,
            features=features,
            bugs=bugs,
            prds=prds,
            specs=specs,
            tests=tests,
            github=github_state,
            interrupted_sessions=interrupted,
            cost_today=cost_today,
            cost_weekly=cost_weekly,
            timestamp=datetime.now(),
        )
    
    def gather_git_state(self) -> GitState:
        """Gather git repository state.
        
        Returns:
            GitState with branch, status, commits, ahead/behind info.
        """
        try:
            # Get current branch
            branch = self._run_git_command(["git", "rev-parse", "--abbrev-ref", "HEAD"])
            branch = branch.strip()
            
            # Get status
            status = self._run_git_command(["git", "status", "--porcelain"])
            
            # Parse modified files
            modified_files = []
            for line in status.strip().split("\n"):
                if line:
                    # Format is "XY filename" where XY is status codes
                    parts = line.split(maxsplit=1)
                    if len(parts) > 1:
                        modified_files.append(parts[1])
            
            # Get recent commits
            log_output = self._run_git_command(
                ["git", "log", "--oneline", "-n", "10"]
            )
            recent_commits = [
                line.strip() for line in log_output.strip().split("\n") if line.strip()
            ]
            
            # Get ahead/behind
            ahead, behind = self._get_ahead_behind()
            
            return GitState(
                current_branch=branch,
                status=status,
                modified_files=modified_files,
                recent_commits=recent_commits,
                ahead=ahead,
                behind=behind,
            )
        except (subprocess.SubprocessError, OSError):
            return GitState.empty()
    
    def _run_git_command(self, cmd: list[str]) -> str:
        """Run a git command and return output.
        
        Args:
            cmd: Command and arguments.
            
        Returns:
            Command stdout.
            
        Raises:
            subprocess.SubprocessError: If command fails.
        """
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=self._root,
        )
        if result.returncode != 0:
            raise subprocess.SubprocessError(result.stderr)
        return result.stdout
    
    def _get_ahead_behind(self) -> tuple[int, int]:
        """Get commits ahead/behind upstream.
        
        Returns:
            Tuple of (ahead, behind) counts.
        """
        try:
            output = self._run_git_command(
                ["git", "rev-list", "--left-right", "--count", "@{upstream}...HEAD"]
            )
            parts = output.strip().split()
            if len(parts) >= 2:
                return int(parts[1]), int(parts[0])
        except (subprocess.SubprocessError, ValueError, IndexError):
            pass
        return 0, 0
    
    def gather_features(self) -> list[FeatureSummary]:
        """Gather feature states from .swarm/state/*.json.
        
        Returns:
            List of FeatureSummary objects.
        """
        features = []
        state_dir = self._root / ".swarm" / "state"
        
        try:
            for state_file in state_dir.glob("*.json"):
                try:
                    data = json.loads(state_file.read_text())
                    issues = data.get("issues", [])
                    completed = sum(
                        1 for i in issues 
                        if i.get("status") == "completed" or i.get("completed")
                    )
                    
                    features.append(FeatureSummary(
                        feature_id=data.get("feature_id", state_file.stem),
                        phase=data.get("phase", "UNKNOWN"),
                        issue_count=len(issues),
                        completed_issues=completed,
                    ))
                except (json.JSONDecodeError, OSError):
                    # Skip corrupted files
                    continue
        except (FileNotFoundError, OSError):
            pass
        
        return features
    
    def gather_bugs(self) -> list[BugSummary]:
        """Gather bug states from .swarm/bugs/*/state.json.
        
        Returns:
            List of BugSummary objects.
        """
        bugs = []
        bugs_dir = self._root / ".swarm" / "bugs"
        
        try:
            for state_file in bugs_dir.glob("*/state.json"):
                try:
                    data = json.loads(state_file.read_text())
                    bugs.append(BugSummary(
                        bug_id=data.get("bug_id", state_file.parent.name),
                        phase=data.get("phase", "UNKNOWN"),
                        description=data.get("description", ""),
                    ))
                except (json.JSONDecodeError, OSError):
                    continue
        except (FileNotFoundError, OSError):
            pass
        
        return bugs
    
    def gather_prds(self) -> list[PRDSummary]:
        """Gather PRDs from .claude/prds/*.md.
        
        Returns:
            List of PRDSummary objects.
        """
        prds = []
        prds_dir = self._root / ".claude" / "prds"
        
        try:
            for prd_file in prds_dir.glob("*.md"):
                try:
                    content = prd_file.read_text()
                    title, status = self._parse_frontmatter(content)
                    
                    prds.append(PRDSummary(
                        name=prd_file.stem,
                        title=title or prd_file.stem,
                        status=status,
                    ))
                except OSError:
                    continue
        except (FileNotFoundError, OSError):
            pass
        
        return prds
    
    def _parse_frontmatter(self, content: str) -> tuple[str, str]:
        """Parse YAML frontmatter from markdown.
        
        Args:
            content: Markdown content with optional frontmatter.
            
        Returns:
            Tuple of (title, status).
        """
        title = ""
        status = "unknown"
        
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                frontmatter = parts[1]
                for line in frontmatter.strip().split("\n"):
                    if ":" in line:
                        key, value = line.split(":", 1)
                        key = key.strip().lower()
                        value = value.strip().strip('"\'')
                        if key == "title":
                            title = value
                        elif key == "status":
                            status = value
        
        return title, status
    
    def gather_specs(self) -> list[SpecSummary]:
        """Gather specs from specs/*/ directories.
        
        Returns:
            List of SpecSummary objects.
        """
        specs = []
        specs_dir = self._root / "specs"
        
        try:
            for spec_dir in specs_dir.iterdir():
                if spec_dir.is_dir():
                    has_draft = (spec_dir / "spec-draft.md").exists()
                    has_final = (spec_dir / "spec-final.md").exists()
                    
                    # Determine review status
                    if has_final:
                        review_status = "approved"
                    elif has_draft:
                        review_status = "pending"
                    else:
                        review_status = "unknown"
                    
                    specs.append(SpecSummary(
                        name=spec_dir.name,
                        has_draft=has_draft,
                        has_final=has_final,
                        review_status=review_status,
                    ))
        except (FileNotFoundError, OSError):
            pass
        
        return specs
    
    def gather_tests(self) -> SuiteMetrics:
        """Gather test state using pytest --collect-only.

        Returns:
            SuiteMetrics with test counts.
        """
        try:
            result = subprocess.run(
                ["pytest", "--collect-only", "-q"],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=self._root,
            )
            
            output = result.stdout
            total_tests = 0
            test_files = []
            
            # Parse "collected X items"
            match = re.search(r"collected (\d+) items?", output)
            if match:
                total_tests = int(match.group(1))
            
            # Parse test file names
            for line in output.split("\n"):
                line = line.strip()
                if line.startswith("<Module "):
                    # Extract module name
                    match = re.search(r"<Module (.+?)>", line)
                    if match:
                        test_files.append(match.group(1))
                elif "::" in line and line.endswith(">"):
                    # Alternative format: test_file.py::TestClass::test_method
                    parts = line.split("::")
                    if parts and parts[0] not in test_files:
                        test_files.append(parts[0])
            
            return SuiteMetrics(
                total_tests=total_tests,
                test_files=test_files,
            )
        except (subprocess.SubprocessError, OSError, subprocess.TimeoutExpired):
            return SuiteMetrics(total_tests=0, test_files=[])
    
    def gather_github(self) -> Optional[GitHubState]:
        """Gather GitHub state via gh CLI.
        
        Returns:
            GitHubState or None if unavailable.
        """
        try:
            # Get open PRs
            prs_result = subprocess.run(
                ["gh", "pr", "list", "--json", "number,title,state"],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=self._root,
            )
            
            open_prs = []
            if prs_result.returncode == 0 and prs_result.stdout.strip():
                try:
                    open_prs = json.loads(prs_result.stdout)
                except json.JSONDecodeError:
                    pass
            
            # Get open issues
            issues_result = subprocess.run(
                ["gh", "issue", "list", "--json", "number,title,state"],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=self._root,
            )
            
            open_issues = []
            if issues_result.returncode == 0 and issues_result.stdout.strip():
                try:
                    open_issues = json.loads(issues_result.stdout)
                except json.JSONDecodeError:
                    pass
            
            return GitHubState(
                open_prs=open_prs,
                open_issues=open_issues,
            )
        except (subprocess.SubprocessError, OSError, subprocess.TimeoutExpired):
            return None
    
    def gather_interrupted_sessions(self) -> list[InterruptedSession]:
        """Find interrupted/paused sessions.
        
        Returns:
            List of InterruptedSession objects.
        """
        sessions = []
        sessions_dir = self._root / ".swarm" / "sessions"
        
        try:
            for session_file in sessions_dir.glob("**/*.json"):
                try:
                    data = json.loads(session_file.read_text())
                    state = data.get("state", "")
                    
                    # Only include paused/interrupted sessions
                    if state in ("PAUSED", "INTERRUPTED", "paused", "interrupted"):
                        timestamp = data.get("timestamp") or data.get("updated_at")
                        if isinstance(timestamp, str):
                            try:
                                timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                            except ValueError:
                                timestamp = datetime.now()
                        else:
                            timestamp = datetime.now()
                        
                        sessions.append(InterruptedSession(
                            session_id=data.get("session_id", session_file.stem),
                            feature_id=data.get("feature_id", "unknown"),
                            state=state,
                            timestamp=timestamp,
                        ))
                except (json.JSONDecodeError, OSError):
                    continue
        except (FileNotFoundError, OSError):
            pass
        
        return sessions
    
    def calculate_costs(self) -> tuple[float, float]:
        """Calculate today's and weekly costs.
        
        Returns:
            Tuple of (today_cost, weekly_cost).
        """
        today_cost = 0.0
        weekly_cost = 0.0
        
        events_dir = self._root / ".swarm" / "events"
        today = datetime.now().date()
        week_ago = today - timedelta(days=7)
        
        try:
            for event_file in events_dir.glob("*.jsonl"):
                try:
                    with open(event_file) as f:
                        for line in f:
                            try:
                                event = json.loads(line)
                                cost = event.get("cost", 0.0)
                                timestamp = event.get("timestamp", "")
                                
                                if isinstance(timestamp, str) and timestamp:
                                    try:
                                        event_date = datetime.fromisoformat(
                                            timestamp.replace("Z", "+00:00")
                                        ).date()
                                        
                                        if event_date == today:
                                            today_cost += cost
                                        if event_date >= week_ago:
                                            weekly_cost += cost
                                    except ValueError:
                                        pass
                            except json.JSONDecodeError:
                                continue
                except OSError:
                    continue
        except (FileNotFoundError, OSError):
            pass
        
        return today_cost, weekly_cost