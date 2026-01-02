"""Sample with hallucinated import - fake internal service module."""
from swarm_attack.services.github_client import (
    GitHubClientV3,
    create_authenticated_session,
    fetch_all_repositories
)


async def sync_repos():
    """Sync using non-existent GitHub client module."""
    session = create_authenticated_session()
    client = GitHubClientV3(session)
    repos = await fetch_all_repositories(client)
    return repos
