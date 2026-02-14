"""Contributor identity discovery and reconciliation.

Pure functions with no Qt dependency — fully testable in isolation.
"""

from __future__ import annotations

from sprint_snitch.models.data import CommitInfo, DiscoveredIdentity


def discover_identities(
    all_commits: dict[str, list[CommitInfo]],
) -> list[DiscoveredIdentity]:
    """Extract unique (name, email) pairs with commit counts.

    Parameters
    ----------
    all_commits:
        Mapping of repo URL → list of extracted commits.

    Returns
    -------
    list[DiscoveredIdentity]
        Sorted by commit count descending, then by name ascending.
    """
    counts: dict[tuple[str, str], int] = {}
    for commits in all_commits.values():
        for commit in commits:
            key = (commit.author_name, commit.author_email)
            counts[key] = counts.get(key, 0) + 1

    identities = [
        DiscoveredIdentity(name=name, email=email, commit_count=count)
        for (name, email), count in counts.items()
    ]
    identities.sort(key=lambda d: (-d.commit_count, d.name))
    return identities


def apply_identity_mapping(
    all_commits: dict[str, list[CommitInfo]],
    mapping: dict[str, tuple[str, str]],
) -> dict[str, list[CommitInfo]]:
    """Rewrite author_name/author_email on commits per the mapping.

    Parameters
    ----------
    all_commits:
        Mapping of repo URL → list of extracted commits.
    mapping:
        Maps original email → (new_name, new_email).  Emails not present
        in the mapping are left unchanged.

    Returns
    -------
    dict[str, list[CommitInfo]]
        The same dict (commits mutated in-place for efficiency).
    """
    if not mapping:
        return all_commits

    for commits in all_commits.values():
        for commit in commits:
            target = mapping.get(commit.author_email)
            if target is not None:
                commit.author_name, commit.author_email = target

    return all_commits
