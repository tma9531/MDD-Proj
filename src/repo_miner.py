#!/usr/bin/env python3
"""
repo_miner.py

A command-line tool to:
  1) Fetch and normalize commit data from GitHub

Sub-commands:
  - fetch-commits
"""

from datetime import datetime
import os
import argparse
import pandas as pd
import github

def fetch_commits(repo_name: str, max_commits: int = None) -> pd.DataFrame:
    """
    Fetch up to `max_commits` from the specified GitHub repository.
    Returns a DataFrame with columns: sha, author, email, date, message.
    """
    # 1) Read GitHub token from environment
    github_token = os.getenv("GITHUB_TOKEN")

    # 2) Initialize GitHub client and get the repo
    client = github.Github(github_token)
    repo = client.get_repo(repo_name)

    # 3) Fetch commit objects (paginated by PyGitHub)
    commits = repo.get_commits()

    # 4) Normalize each commit into a record dict
    count = 0
    for commit in commits:
        count += 1
    if max_commits == None:
        max_commits = count
    num_of_commits = min(count, max_commits)

    commit_records = []
    for i in range(num_of_commits):
        # each commit is a dict
        commit_data = {
            "sha": commits[i].sha,
            "author": commits[i].commit.author.name,
            "email": commits[i].commit.author.email,
            "date": commits[i].commit.author.date,
            "message": commits[i].commit.message.split("\n")[0]
        }
        commit_records.append(commit_data)

    # 5) Build DataFrame from records
    return pd.DataFrame(commit_records)

def fetch_issues(repo_name: str, state: str = "all", max_issues: int = None) -> pd.DataFrame:
    """
    Fetch up to `max_issues` from the specified GitHub repository (issues only).
    Returns a DataFrame with columns: id, number, title, user, state, created_at, closed_at, comments.
    """
    # 1) Read GitHub token
    github_token = os.getenv("GITHUB_TOKEN")

    # 2) Initialize client and get the repo
    client = github.Github(github_token)
    repo = client.get_repo(repo_name)

    # 3) Fetch issues, filtered by state ('all', 'open', 'closed')
    issues = repo.get_issues(state=state)

    # 4) Normalize each issue (skip PRs)
    issue_records = []
    for idx, issue in enumerate(issues):
        if max_issues and idx >= max_issues:
            break
        # Skip pull requests
        if issue.pull_request != None:
            continue

        # Append records
        created_date = issue.created_at.strftime("%Y-%m-%d")
        if issue.closed_at != None:
            closed_date = issue.closed_at.strftime("%Y-%m-%d")
            duration = issue.closed_at - issue.created_at
        else:
            closed_date = None
            duration = None

        issue_data = {
            "id": issue.id,
            "number": issue.number,
            "title": issue.title,
            "user": issue.user,
            "state": issue.state,
            "created_at": created_date,
            "open_duration_days": duration,
            "closed_at": closed_date,
            "comments": issue.comments
        }
        issue_records.append(issue_data)

    # 5) Build DataFrame
    return pd.DataFrame(issue_records)
    
def main():
    """
    Parse command-line arguments and dispatch to sub-commands.
    """
    parser = argparse.ArgumentParser(
        prog="repo_miner",
        description="Fetch GitHub commits/issues and summarize them"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Sub-command: fetch-commits
    c1 = subparsers.add_parser("fetch-commits", help="Fetch commits and save to CSV")
    c1.add_argument("--repo", required=True, help="Repository in owner/repo format")
    c1.add_argument("--max",  type=int, dest="max_commits",
                    help="Max number of commits to fetch")
    c1.add_argument("--out",  required=True, help="Path to output commits CSV")

    # Sub-command: fetch-issues
    c2 = subparsers.add_parser("fetch-issues", help="Fetch issues and save to CSV")
    c2.add_argument("--repo",  required=True, help="Repository in owner/repo format")
    c2.add_argument("--state", choices=["all","open","closed"], default="all",
                    help="Filter issues by state")
    c2.add_argument("--max",   type=int, dest="max_issues",
                    help="Max number of issues to fetch")
    c2.add_argument("--out",   required=True, help="Path to output issues CSV")

    args = parser.parse_args()

    # Dispatch based on selected command
    if args.command == "fetch-commits":
        df = fetch_commits(args.repo, args.max_commits)
        df.to_csv(args.out, index=False)
        print(f"Saved {len(df)} commits to {args.out}")

    elif args.command == "fetch-issues":
        df = fetch_issues(args.repo, args.state, args.max_issues)
        df.to_csv(args.out, index=False)
        print(f"Saved {len(df)} issues to {args.out}")

if __name__ == "__main__":
    main()