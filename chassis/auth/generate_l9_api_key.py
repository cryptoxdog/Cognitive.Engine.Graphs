#!/usr/bin/env python3
"""
--- L9_META ---
l9_schema: 1
origin: chassis
engine: graph
layer: [api, auth]
tags: [chassis, auth, keygen]
owner: platform-team
status: active
--- /L9_META ---

Generate L9_API_KEY and optionally store in AWS Secrets Manager.

Usage:
    # Generate and print key only
    python tools/generate_l9_api_key.py

    # Generate and store in AWS Secrets Manager
    python tools/generate_l9_api_key.py --store

    # One-liner (no script needed)
    python -c "import secrets; print(secrets.token_urlsafe(48))"

AWS Secret:
    Name: clawdbot/l9-api
    Format: {"L9_API_KEY": "<generated-token>"}
    Region: us-east-1 (default, override with AWS_DEFAULT_REGION)
    Used by: Clawdbot when calling cognitive engine API
"""

from __future__ import annotations

import argparse
import json
import secrets
import sys

SECRET_NAME = "clawdbot/l9-api"
SECRET_DESCRIPTION = "L9 Cognitive Engine API key for Clawdbot integration"
TOKEN_BYTES = 48  # 48 bytes → 64 chars base64url


def generate_key() -> str:
    """Generate a cryptographically secure API key."""
    return secrets.token_urlsafe(TOKEN_BYTES)


def store_in_aws(key: str, region: str = "us-east-1") -> None:
    """Store key in AWS Secrets Manager as JSON."""
    try:
        import boto3
        from botocore.exceptions import ClientError
    except ImportError:
        print("ERROR: boto3 not installed. Run: pip install boto3", file=sys.stderr)
        sys.exit(1)

    client = boto3.client("secretsmanager", region_name=region)
    secret_value = json.dumps({"L9_API_KEY": key})

    try:
        # Try to update existing secret
        client.put_secret_value(
            SecretId=SECRET_NAME,
            SecretString=secret_value,
        )
        print(f"Updated existing secret: {SECRET_NAME}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            # Create new secret
            client.create_secret(
                Name=SECRET_NAME,
                Description=SECRET_DESCRIPTION,
                SecretString=secret_value,
                Tags=[
                    {"Key": "project", "Value": "l9-constellation"},
                    {"Key": "consumer", "Value": "clawdbot"},
                    {"Key": "env", "Value": "production"},
                ],
            )
            print(f"Created new secret: {SECRET_NAME}")
        else:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate L9 API key")
    parser.add_argument(
        "--store",
        action="store_true",
        help=f"Store in AWS Secrets Manager as {SECRET_NAME}",
    )
    parser.add_argument(
        "--region",
        default="us-east-1",
        help="AWS region (default: us-east-1)",
    )
    args = parser.parse_args()

    key = generate_key()

    print(f"Generated L9_API_KEY: {key}")
    print()
    print("# Add to .env for local development:")
    print(f"L9_API_KEY={key}")
    print()
    print("# Add to Coolify environment variables:")
    print(f"L9_API_KEY={key}")
    print()
    print(f"# AWS Secrets Manager format (secret name: {SECRET_NAME}):")
    print(json.dumps({"L9_API_KEY": key}, indent=2))

    if args.store:
        print()
        store_in_aws(key, region=args.region)


# --- secure-env.sh addition ---
# Add the following block to your secure-env.sh retrieval list:
#
# # L9 Cognitive Engine API Key (consumed by Clawdbot)
# L9_API_KEY=$(aws secretsmanager get-secret-value \
#     --secret-id clawdbot/l9-api \
#     --query 'SecretString' \
#     --output text | python3 -c "import sys,json; print(json.load(sys.stdin)['L9_API_KEY'])")
# export L9_API_KEY


if __name__ == "__main__":
    main()
