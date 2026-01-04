"""
Helper functions for organizations app.
"""

from datetime import date
from dateutil.relativedelta import relativedelta
from django.utils.text import slugify
import uuid


def calculate_next_payment_date(billing_cycle: str, start_date: date = None) -> date:
    """
    Calculate the next payment date based on billing cycle and start date.

    """
    if start_date is None:
        start_date = date.today()

    if billing_cycle == "MONTHLY":
        # Add 1 month to start date
        next_payment = start_date + relativedelta(months=1)
    elif billing_cycle == "YEARLY":
        # Add 1 year to start date
        next_payment = start_date + relativedelta(years=1)
    else:
        raise ValueError(
            f"Invalid billing_cycle: {billing_cycle}. Must be 'MONTHLY' or 'YEARLY'."
        )

    return next_payment


def generate_schema_name(business_name: str) -> str:
    """
    Generate a valid PostgreSQL schema name from business name.

    PostgreSQL schema names must:
    - Be lowercase
    - Contain only alphanumeric characters and underscores
    - Be max 63 characters
    - Not start with a number

    Args:
        business_name: The business/organization name

    Returns:
        str: A valid schema name (e.g., "uber", "uber_tech", "uber_abc123")
    """
    # Create a slug from business name
    slug = slugify(business_name).lower().replace("-", "_")

    # Remove any non-alphanumeric characters except underscore
    schema_name = "".join(c if c.isalnum() or c == "_" else "" for c in slug)

    # Ensure it doesn't start with a number
    if schema_name and schema_name[0].isdigit():
        schema_name = f"org_{schema_name}"

    # If empty or too short, add prefix
    if not schema_name or len(schema_name) < 3:
        schema_name = f"org_{uuid.uuid4().hex[:8]}"

    # Truncate to 63 characters (PostgreSQL limit)
    if len(schema_name) > 63:
        schema_name = schema_name[:60]  # Leave room for uniqueness suffix

    # Add uniqueness suffix to avoid collisions
    unique_suffix = uuid.uuid4().hex[:8]
    schema_name = f"{schema_name}_{unique_suffix}"[:63]

    return schema_name


def generate_domain_name(business_name: str, base_domain: str = None) -> str:
    """
    Generate a domain name from business name.

    Args:
        business_name: The business/organization name
        base_domain: Base domain (e.g., "app.com").
                    If None, retrieves from Django settings.BASE_DOMAIN

    Returns:
        str: A domain name (e.g., "uber.app.com")
    """
    if base_domain is None:
        from django.conf import settings

        base_domain = settings.BASE_DOMAIN

    slug = slugify(business_name).lower()

    slug = "".join(c if c.isalnum() or c == "-" else "" for c in slug)

    if not slug:
        slug = f"org-{uuid.uuid4().hex[:8]}"

    # Combine with base domain
    domain = f"{slug}.{base_domain}"

    return domain
