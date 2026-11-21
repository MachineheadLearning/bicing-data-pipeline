# ADR-0004: AWS region — Europe (Stockholm) eu-north-1

- **Status:** Accepted
- **Date:** 2026-11-21

## Context

The report requires that the S3 bucket and the Snowflake account live in the same EU AWS region,
with eu-west-1 (Ireland) as the default. The AWS account was created through AWS's new
project-based sign-up, on the Free plan. That sign-up places each project in a region based on the
country of the contact address: US East (Ohio), Europe (Stockholm) or Asia Pacific (Sydney). The
region can't be changed without activating advanced features, which can't be reversed.

Snowflake offers AWS EU (Stockholm) at the same on-demand price as EU (Ireland): $2.60 per credit
on Standard, $3.90 on Enterprise, and $23 per TB per month of storage.

## Options considered

- **A.** Keep this account and use eu-north-1 for both S3 and Snowflake.
- **B.** Activate advanced features to unlock eu-west-1. This can't be undone, and its effect on
  the Free plan's credits is not documented.
- **C.** Open a second account through the classic sign-up in eu-west-1. It probably has no free
  plan or credits, and it means two accounts to manage.

## Decision

**A.** The S3 bucket and the Snowflake trial account are both created in **eu-north-1 (Europe,
Stockholm)**.

## Consequences

- The locked rule "same EU AWS region for S3 and Snowflake" still holds. Only the report's default
  region changes.
- Network latency doesn't matter for a batch pipeline. Keeping both services in the same region
  keeps data transfer between them free and fast.
- The Free plan stays in place, so the AWS card can't be charged, and the account closes after 6
  months or when its credits run out. After that, the repo stays fully runnable on DuckDB.
- The region is read from configuration (`AWS_REGION`) and is never hard-coded.
- IAM in project accounts can be used only for programmatic access. The pipeline user and the
  Snowflake storage-integration role (day 2) are programmatic, so this is not a blocker. Anything
  AWS's project policies block will show up on day 2.
