# tests/test_repo_miner.py

import os
# from github import Github
import github
import pandas as pd
import pytest
from datetime import datetime, timedelta
from src.repo_miner import fetch_commits, fetch_issues, merge_and_summarize

# --- Helpers for dummy GitHub API objects ---

class DummyAuthor:
    def __init__(self, name, email, date):
        self.name = name
        self.email = email
        self.date = date

class DummyCommitCommit:
    def __init__(self, author, message):
        self.author = author
        self.message = message

class DummyCommit:
    def __init__(self, sha, author, email, date, message):
        self.sha = sha
        self.commit = DummyCommitCommit(DummyAuthor(author, email, date), message)

class DummyUser:
    def __init__(self, login):
        self.login = login

class DummyIssue:
    def __init__(self, id_, number, title, user, state, created_at, closed_at, comments, is_pr=False):
        self.id = id_
        self.number = number
        self.title = title
        self.user = DummyUser(user)
        self.state = state
        self.created_at = created_at
        self.closed_at = closed_at
        self.comments = comments
        # attribute only on pull requests
        self.pull_request = DummyUser("pr") if is_pr else None

class DummyRepo:
    def __init__(self, commits, issues):
        self._commits = commits
        self._issues = issues

    def get_commits(self):
        return self._commits

    def get_issues(self, state="all"):
        # filter by state
        if state == "all":
            return self._issues
        return [i for i in self._issues if i.state == state]

class DummyGithub:
    def __init__(self, token):
        self._repo = None
        assert token == "fake-token"
    def get_repo(self, repo_name):
        # ignore repo_name; return repo set in test fixture
        return gh_instance._repo

@pytest.fixture(autouse=True)
def patch_env_and_github(monkeypatch: pytest.MonkeyPatch):
    # Set fake token
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    # Patch Github class
    monkeypatch.setattr(github, "Github", DummyGithub)

# Helper global placeholder
gh_instance = DummyGithub("fake-token")

# --- Tests for fetch_commits ---
# An example test case
def test_fetch_commits_basic(monkeypatch: pytest.MonkeyPatch):
    # Setup dummy commits
    now = datetime.now()
    commits = [
        DummyCommit("sha1", "Alice", "a@example.com", now, "Initial commit\nDetails"),
        DummyCommit("sha2", "Bob", "b@example.com", now - timedelta(days=1), "Bug fix")
    ]
    gh_instance._repo = DummyRepo(commits, [])
    df = fetch_commits("any/repo")
    assert list(df.columns) == ["sha", "author", "email", "date", "message"]
    assert len(df) == 2
    assert df.iloc[0]["message"] == "Initial commit"

def test_fetch_commits_limit(monkeypatch: pytest.MonkeyPatch):
    # More commits than max_commits
    # Test that fetch_commits respects the max_commits limit.
    now = datetime.now()
    commits = [
        DummyCommit("sha1", "Alice", "a@example.com", now, "Initial commit\nDetails"),
        DummyCommit("sha2", "Bob", "b@example.com", now - timedelta(days=1), "Bug fix"),
        DummyCommit("sha3", "Cindy", "c@example.com", now, "More stuff\nDetails"),
        DummyCommit("sha4", "Dylan", "d@example.com", now - timedelta(days=1), "another Bug fix")
    ]
    gh_instance._repo = DummyRepo(commits, [])
    max_commits = 3
    df = fetch_commits("any/repo", max_commits)
    assert len(df) == max_commits

def test_fetch_commits_empty(monkeypatch: pytest.MonkeyPatch):
    # Test that fetch_commits returns empty DataFrame when no commits exist.
    commits = []
    gh_instance._repo = DummyRepo(commits, [])
    max_commits = 3
    df = fetch_commits("any/repo", max_commits)
    assert len(df) == 0

def test_fetch_issues_basic(monkeypatch):
    # Test that fetch issues returns a correct DataFrame with issues.
    now = datetime.now()
    issues = [
        DummyIssue(1, 101, "Issue A", "alice", "open", now, None, 0),
        DummyIssue(2, 102, "Issue B", "bob", "closed", now - timedelta(days=2), now, 2)
    ]
    gh_instance._repo = DummyRepo([], issues)
    df = fetch_issues("any/repo", state="all")
    assert {"id", "number", "title", "user", "state", "created_at", "open_duration_days", "closed_at", "comments"}.issubset(df.columns)
    assert len(df) == 2

def test_fetch_issues_date(monkeypatch):
    # Test that fetch issues parses dates correctly.
    now = datetime.now()
    issues = [
        DummyIssue(1, 101, "Issue A", "alice", "open", now, None, 0),
        DummyIssue(2, 102, "Issue B", "bob", "closed", now - timedelta(days=2), now, 2)
    ]
    gh_instance._repo = DummyRepo([], issues)
    df = fetch_issues("any/repo", state="all")
    # Check date normalization
    try:
        columns = list(df)
        created_date = df[columns[5]][0]
        closed_date = df[columns[7]][1]
        datetime.strptime(created_date, "%Y-%m-%d")
        datetime.strptime(closed_date, "%Y-%m-%d")
        assert True
    except ValueError:
        assert False

def test_fetch_issues_no_pr(monkeypatch):
    # Test that fetch issues excludes pull requests.
    now = datetime.now()
    issues = [
        DummyIssue(1, 101, "Issue A", "alice", "open", now, None, 0, is_pr=True),
        DummyIssue(2, 102, "Issue B", "bob", "closed", now - timedelta(days=2), now, 2)
    ]
    gh_instance._repo = DummyRepo([], issues)
    df = fetch_issues("any/repo", state="all")
    # Issue A is a pull request, should not be included
    assert len(df) == 1
    columns = list(df)
    assert df[columns[2]][0] == "Issue B"

def test_fetch_issues_duration(monkeypatch):
    # Test that fetch issues correctly computes open duration days.
    now = datetime.now()
    issues = [
        DummyIssue(2, 102, "Issue B", "bob", "closed", now - timedelta(days=2), now, 2)
    ]
    gh_instance._repo = DummyRepo([], issues)
    df = fetch_issues("any/repo", state="all")
    columns = list(df)
    days = df[columns[6]][0]
    assert days == timedelta(days=2)

def test_merge_and_summarize_output(capsys):
    # Prepare test DataFrames
    df_commits = pd.DataFrame({
        "sha": ["a", "b", "c", "d"],
        "author": ["X", "Y", "X", "Z"],
        "email": ["x@e", "y@e", "x@e", "z@e"],
        "date": ["2025-01-01T00:00:00", "2025-01-01T01:00:00",
                 "2025-01-02T00:00:00", "2025-01-02T01:00:00"],
        "message": ["m1", "m2", "m3", "m4"]
    })
    df_issues = pd.DataFrame({
        "id": [1,2,3],
        "number": [101,102,103],
        "title": ["I1","I2","I3"],
        "user": ["u1","u2","u3"],
        "state": ["closed","open","closed"],
        "created_at": ["2025-01-01T00:00:00","2025-01-01T02:00:00","2025-01-02T00:00:00"],
        "closed_at": ["2025-01-01T12:00:00",None,"2025-01-02T12:00:00"],
        "comments": [0,1,2]
    })
    # Run summarize
    merge_and_summarize(df_commits, df_issues)
    captured = capsys.readouterr().out
    # Check top committer
    assert "Top 5 committers" in captured
    assert "X: 2 commits" in captured
    # Check close rate
    assert "Issue close rate: 0.67" in captured
    # Check avg open duration
    assert "Avg. issue open duration:" in captured