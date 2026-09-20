# tooling/src/otsafety_tooling/github/__init__.py
"""GitHub, as the repository's host: settings and, later, branch protection.

Separate from otsafety_tooling.git, which works on the local repository. Modules
here reach GitHub only through a small port, so their logic is tested against
an in-memory repository and runs against `gh api` in production.
"""
