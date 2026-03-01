"""
Tenant resolution middleware.
Resolves domain/tenant from X-Domain-Key header, subdomain, or API key.
"""

import logging

from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)


async def resolve_tenant(request: Request) -> str:
    """
    Resolve tenant/domain identifier from request.

    Priority:
    1. X-Domain-Key header
    2. X-Tenant-Key header
    3. Subdomain (e.g., plasticos.api.example.com)
    4. API key prefix (e.g., pk_plasticos_...)

    Args:
        request: FastAPI request

    Returns:
        Domain identifier

    Raises:
        HTTPException: If tenant cannot be resolved
    """
    # Check headers
    domain_key = request.headers.get("x-domain-key")
    if domain_key:
        logger.debug(f"Resolved tenant from X-Domain-Key: {domain_key}")
        return domain_key

    tenant_key = request.headers.get("x-tenant-key")
    if tenant_key:
        logger.debug(f"Resolved tenant from X-Tenant-Key: {tenant_key}")
        return tenant_key

    # Check subdomain
    host = request.headers.get("host", "")
    if "." in host:
        subdomain = host.split(".")[0]
        if subdomain not in ["www", "api"]:
            logger.debug(f"Resolved tenant from subdomain: {subdomain}")
            return subdomain

    # Check API key prefix
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer pk_"):
        api_key = auth_header.replace("Bearer ", "")
        parts = api_key.split("_")
        if len(parts) >= 3:
            domain = parts[1]
            logger.debug(f"Resolved tenant from API key prefix: {domain}")
            return domain

    raise HTTPException(
        status_code=400, detail="Could not resolve tenant. Provide X-Domain-Key header, subdomain, or API key."
    )
