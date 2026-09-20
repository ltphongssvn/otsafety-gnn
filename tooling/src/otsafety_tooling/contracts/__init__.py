# tooling/src/otsafety_tooling/contracts/__init__.py
"""Contracts: the single definition of every record this repository emits.

Each module defines frozen Pydantic models for one kind of record (a branch
report, and later verdicts and run records). Producers build these models and
readers validate against them, so a record that contradicts its own contract
cannot be written, and a renamed field fails loudly instead of disappearing.
"""
