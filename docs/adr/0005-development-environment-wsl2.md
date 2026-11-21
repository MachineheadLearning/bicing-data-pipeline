# ADR-0005: Development environment — WSL2 Ubuntu on Windows

- **Status:** Accepted
- **Date:** 2026-11-15

## Context

The author develops on Windows 10. The locked setup assumes a Linux-style workflow: a `Makefile` for
one-command entry points, shell commands, and Airflow in Docker Compose with folders shared into the
containers. CI runs on Ubuntu (GitHub Actions). Docker Desktop is installed and already uses WSL2,
but no general-purpose Linux system is installed in WSL (only Docker's internal `docker-desktop` one).

## Options considered

- **A. WSL2 Ubuntu.** The repo is cloned in the Linux file system. Claude Code, `make`, `uv` and
  `docker compose` run inside Ubuntu, and VS Code connects to it.
- **B. Native Windows** with Docker Desktop. `make` would need extra tools, folders shared from
  Windows into Docker are slow, and Windows line endings (CRLF) break shell scripts.

## Decision

**A.** All development happens inside WSL2 Ubuntu. The repo lives under the Linux home directory
(for example `~/projects/bicing-data-pipeline`), not under `/mnt/c`.

## Consequences

- The environment matches CI and the commands in the README, so a reviewer on macOS or Linux can
  run them unchanged.
- Docker Desktop must use the WSL 2 based engine, with WSL integration turned on for Ubuntu.
- Git sign-in and identity are configured again inside Ubuntu (SSH key, noreply email). The
  earlier clone on the Windows file system is not used.
- Windows users who clone the repo are told in the README to use WSL2. Native Windows is not
  supported.
