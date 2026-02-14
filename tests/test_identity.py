"""Tests for contributor identity discovery and reconciliation."""

from datetime import datetime

from sprint_snitch.git_analysis.identity import apply_identity_mapping, discover_identities
from sprint_snitch.models.data import CommitInfo, FileChange


def _commit(name="Alice", email="alice@co.com", sha="abc"):
    return CommitInfo(
        sha=sha,
        author_name=name,
        author_email=email,
        message="fix",
        timestamp=datetime(2025, 1, 10),
        files=[FileChange(path="main.py", lines_added=5, lines_removed=1, change_type="modified")],
        lines_added=5,
        lines_removed=1,
    )


# ---------------------------------------------------------------------------
# discover_identities
# ---------------------------------------------------------------------------


def test_discover_basic():
    all_commits = {
        "url1": [_commit("Alice", "alice@co.com"), _commit("Bob", "bob@co.com")],
    }
    identities = discover_identities(all_commits)
    assert len(identities) == 2
    emails = {i.email for i in identities}
    assert emails == {"alice@co.com", "bob@co.com"}


def test_discover_counts():
    all_commits = {
        "url1": [
            _commit("Alice", "alice@co.com", sha="a1"),
            _commit("Alice", "alice@co.com", sha="a2"),
            _commit("Alice", "alice@co.com", sha="a3"),
            _commit("Bob", "bob@co.com", sha="b1"),
        ],
    }
    identities = discover_identities(all_commits)
    alice = next(i for i in identities if i.email == "alice@co.com")
    bob = next(i for i in identities if i.email == "bob@co.com")
    assert alice.commit_count == 3
    assert bob.commit_count == 1


def test_discover_sorted_by_count_desc():
    all_commits = {
        "url1": [
            _commit("Bob", "bob@co.com", sha="b1"),
            _commit("Alice", "alice@co.com", sha="a1"),
            _commit("Alice", "alice@co.com", sha="a2"),
        ],
    }
    identities = discover_identities(all_commits)
    assert identities[0].email == "alice@co.com"
    assert identities[1].email == "bob@co.com"


def test_discover_across_repos():
    all_commits = {
        "url1": [_commit("Alice", "alice@co.com", sha="a1")],
        "url2": [_commit("Alice", "alice@co.com", sha="a2")],
    }
    identities = discover_identities(all_commits)
    assert len(identities) == 1
    assert identities[0].commit_count == 2


def test_discover_same_email_different_names():
    """Two different name+email combos are separate identities."""
    all_commits = {
        "url1": [
            _commit("Alice Smith", "alice@co.com"),
            _commit("alice-smith", "alice@noreply.github.com"),
        ],
    }
    identities = discover_identities(all_commits)
    assert len(identities) == 2


def test_discover_empty():
    assert discover_identities({}) == []
    assert discover_identities({"url1": []}) == []


# ---------------------------------------------------------------------------
# apply_identity_mapping
# ---------------------------------------------------------------------------


def test_apply_mapping_rewrites():
    c1 = _commit("alice-web", "alice@noreply.github.com", sha="c1")
    c2 = _commit("Alice Smith", "alice@co.com", sha="c2")
    all_commits = {"url1": [c1, c2]}

    mapping = {"alice@noreply.github.com": ("Alice Smith", "alice@co.com")}
    result = apply_identity_mapping(all_commits, mapping)

    # c1 should be rewritten
    assert result["url1"][0].author_name == "Alice Smith"
    assert result["url1"][0].author_email == "alice@co.com"
    # c2 should be unchanged
    assert result["url1"][1].author_name == "Alice Smith"
    assert result["url1"][1].author_email == "alice@co.com"


def test_apply_mapping_unmapped_passthrough():
    c1 = _commit("Bob", "bob@co.com")
    all_commits = {"url1": [c1]}

    mapping = {"alice@noreply.github.com": ("Alice", "alice@co.com")}
    apply_identity_mapping(all_commits, mapping)

    assert c1.author_name == "Bob"
    assert c1.author_email == "bob@co.com"


def test_apply_mapping_empty():
    c1 = _commit("Alice", "alice@co.com")
    all_commits = {"url1": [c1]}

    result = apply_identity_mapping(all_commits, {})

    assert result["url1"][0].author_name == "Alice"
    assert result["url1"][0].author_email == "alice@co.com"


def test_apply_mapping_across_repos():
    c1 = _commit("alice-web", "alice@noreply.github.com", sha="c1")
    c2 = _commit("alice-web", "alice@noreply.github.com", sha="c2")
    all_commits = {"url1": [c1], "url2": [c2]}

    mapping = {"alice@noreply.github.com": ("Alice Smith", "alice@co.com")}
    apply_identity_mapping(all_commits, mapping)

    assert c1.author_name == "Alice Smith"
    assert c1.author_email == "alice@co.com"
    assert c2.author_name == "Alice Smith"
    assert c2.author_email == "alice@co.com"


def test_apply_mapping_rename_only():
    """Mapping can rename while keeping the same email."""
    c1 = _commit("alice-web", "alice@co.com")
    all_commits = {"url1": [c1]}

    mapping = {"alice@co.com": ("Alice Smith", "alice@co.com")}
    apply_identity_mapping(all_commits, mapping)

    assert c1.author_name == "Alice Smith"
    assert c1.author_email == "alice@co.com"
