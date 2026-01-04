# TaskFlow - Multi-Tenant Task Management System

A production-ready, multi-tenant task management system built with Django, featuring schema-based tenant isolation, JWT authentication, and comprehensive task management capabilities.

## Table of Contents

1. [Overview](#overview)
2. [Architecture & Design](#architecture--design)
3. [Database Schema](#database-schema)
4. [Models](#models)
5. [API Endpoints](#api-endpoints)
6. [Authentication & Security](#authentication--security)
7. [Permissions & Access Control](#permissions--access-control)
8. [Shared vs Tenant Apps](#shared-vs-tenant-apps)
9. [Setup Instructions](#setup-instructions)
10. [Background Processing](#background-processing)
11. [Logging](#logging)

---

## Overview

TaskFlow is a multi-tenant SaaS application that allows organizations to manage tasks, boards, and team collaboration within isolated tenant environments. Each organization operates in its own PostgreSQL schema, ensuring complete data isolation while sharing the same application codebase.

### Key Features

- **Multi-Tenant Architecture**: Schema-based isolation using `django-tenants`
- **JWT Authentication**: Secure token-based authentication with UUID primary keys
- **Task Management**: Create, update, delete tasks with status and priority tracking
- **Board Organization**: Organize tasks into boards
- **Scheduled Tasks**: Schedule tasks for future execution with recurrence patterns
- **Audit Logging**: Comprehensive audit trail for compliance and debugging
- **Subscription Management**: Built-in subscription and billing system
- **Email Domain Restriction**: Organization-specific email domain validation for signups

---

## Architecture & Design

### High-Level Architecture

The system uses **Schema-Based Multi-Tenancy** via the `django-tenants` library:

1. **Public Schema (Landlord)**:
   - Acts as the router and registry
   - Stores `Organization` (Tenant), `Domain`, `SubscriptionPlan`, and `Subscription` models
   - Routes requests based on domain/subdomain to the correct tenant schema

2. **Tenant Schemas (Apartments)**:
   - Each organization gets a dedicated PostgreSQL schema
   - Business logic is shared, but data is strictly isolated
   - Contains tenant-specific models: `Task`, `Board`, `ScheduledTask`, `AuditLog`

### Request Flow

```
Request → TenantMainMiddleware (determines tenant from domain)
        → AuthenticationMiddleware (authenticates user from shared schema)
        → UserOrganizationMiddleware (validates user belongs to organization)
        → SubscriptionCheckMiddleware (validates subscription)
        → View (processes request in tenant context)
```

### Background Processing Strategy

Instead of an asynchronous task queue (Celery), we implemented a **Database-Polling Pattern**:

1. **Queue**: A `ScheduledTask` table acts as the queue
2. **Scheduler**: A system `cron` job runs every 2 minutes inside the container
3. **Worker**: A custom Django Management Command (`process_tasks`) wakes up, iterates through every tenant schema, and processes tasks that are due

---

## Database Schema

### Global Tables (Public Schema)

| Table | Description |
| :--- | :--- |
| **Organization** | Tenant metadata (schema name, business name, owner email, subscription) |
| **Domain** | Maps URL (e.g., `tenant-a.localhost`) to an Organization |
| **SubscriptionPlan** | Available billing tiers (FREE, STARTER, PRO, ENTERPRISE) |
| **Subscription** | Active subscriptions for organizations |
| **UserAccount** | User accounts (UUID primary key, belongs to one organization) |

### Tenant Tables (Replicated in every Tenant Schema)

| Table | Description |
| :--- | :--- |
| **Task** | Tasks with status, priority, due dates, assignments |
| **Board** | Boards for organizing tasks |
| **ScheduledTask** | Queue for future task creation |
| **AuditLog** | Audit trail for all important actions |

---

## Models

### Shared Schema Models

#### `Organization` (Tenant Model) (`organizations` app)
- **Primary Key**: `organization_id` (UUID)
- **Fields**: `business_name`, `owner_email`, `billing_email`, `billing_address`, `contact_number`, `email_domain`, `subscription`, `is_active`
- **Purpose**: Represents a tenant/organization. Extends `TenantMixin` from django-tenants

#### `Domain` (`organizations` app)
- **Purpose**: Maps domain names to organizations for routing requests
- **Extends**: `DomainMixin` from django-tenants

#### `SubscriptionPlan` (`organizations` app)
- **Primary Key**: `subscription_plan_id` (UUID)
- **Fields**: `display_name`, `description`, `price`, `currency`, `max_users`, `max_tasks`
- **Tiers**: FREE, STARTER, PRO, ENTERPRISE

#### `Subscription` (`organizations` app)
- **Primary Key**: `subscription_id` (UUID)
- **Fields**: `subscription_plan`, `is_active`, `started_at`, `end_date`, `expired_at`, `billing_cycle`, `stripe_id`, `next_payment_date`, `last_payment_date`
- **Purpose**: Tracks active subscriptions for organizations

#### `UserAccount` (`accounts` app)
- **Primary Key**: `user_id` (UUID)
- **Fields**: 
  - `email` (unique globally, indexed)
  - `first_name`, `last_name`
  - `organization` (ForeignKey to Organization - user belongs to exactly one organization)
  - `is_org_owner` (full access to billing/settings for their organization)
  - `is_admin` (can manage other users in their organization)
  - `is_staff` (can access Django admin)
  - `is_active` (can login)
  - `is_restricted` (read-only mode)
  - `date_joined`, `last_login`
- **Extends**: `AbstractBaseUser`, `PermissionsMixin`
- **Authentication**: Email-based authentication
- **Purpose**: Centralized user accounts for analytics and unified authentication. Each user belongs to exactly one organization.

### Tenant Schema Models

#### `Task` (`task_manager` app)
- **Primary Key**: `task_id` (UUID)
- **Fields**:
  - `title`, `description`
  - `status` (PENDING, IN_PROGRESS, COMPLETED, CANCELLED, ON_HOLD)
  - `priority` (LOW, MEDIUM, HIGH, URGENT)
  - `board` (ForeignKey to Board)
  - `created_by` (ForeignKey to UserAccount)
  - `assigned_to` (ManyToMany to UserAccount)
  - `due_date`, `completed_at`, `created_at`, `updated_at`
- **Properties**: `is_overdue` - Checks if task is past due date

#### `Board` (`task_manager` app)
- **Primary Key**: `board_id` (UUID)
- **Fields**: `name`, `description`, `created_by`, `created_at`, `updated_at`
- **Purpose**: Organizes tasks into boards

#### `ScheduledTask` (`task_manager` app)
- **Primary Key**: `scheduled_task_id` (UUID)
- **Fields**:
  - `title`, `description`, `status`
  - `scheduled_time` (when task should be processed)
  - `recurrence_pattern` (ONCE, DAILY, WEEKLY, MONTHLY)
  - `processing_status` (0=Pending, 1=Processed, 2=Failed)
  - `failure_reason`, `created_by`, `created_at`, `processed_at`
- **Purpose**: Queue for background task processing

#### `AuditLog` (`task_manager` app)
- **Primary Key**: `audit_log_id` (UUID)
- **Fields**:
  - `user` (ForeignKey to UserAccount, nullable)
  - `action_type` (TASK_CREATED, TASK_UPDATED, TASK_DELETED, TASK_ASSIGNED, TASK_COMPLETED, BOARD_CREATED, BOARD_UPDATED, BOARD_DELETED, SCHEDULED_TASK_CREATED)
  - `description`, `metadata` (JSONField)
  - `ip_address`, `user_agent`
  - `created_at`
- **Purpose**: Audit trail for compliance and debugging

---

## API Endpoints

All endpoints (except organization creation) must be accessed via a Tenant Domain (e.g., `http://tenant-a.localhost:8000/api/v1/...`).

### Base URL Structure
- **API Version**: `v1`
- **Base Path**: `/api/v1/`
- **App Prefixes**:
  - Accounts: `/api/v1/accounts/`
  - Task Manager: `/api/v1/taskmanager/`
  - Organizations: `/api/v1/organization/`

### Authentication Endpoints (`/api/v1/accounts/`)

| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| **POST** | `/auth/login/` | Login and obtain JWT Access & Refresh tokens | No |
| **POST** | `/auth/logout/` | Logout and blacklist refresh token | Yes |
| **POST** | `/auth/refresh/` | Get a new Access token using Refresh token | No |
| **POST** | `/auth/change-password/` | Change user's own password | Yes |

### User Management Endpoints (`/api/v1/accounts/`)

| Method | Endpoint | Description | Auth Required | Permission |
| :--- | :--- | :--- | :--- | :--- |
| **GET** | `/users/me/` | Get own user profile | Yes | Any authenticated user |
| **PATCH** | `/users/me/` | Update own user profile | Yes | Any authenticated user |
| **GET** | `/users/` | List all users in organization | Yes | Admin/Owner |
| **GET** | `/users/<uuid:user_id>/` | Get specific user details | Yes | Admin/Owner or self |
| **PATCH** | `/users/<uuid:user_id>/` | Update user (can update own) | Yes | Admin/Owner or self |
| **POST** | `/users/create/` | Signup new user (email domain must match org) | No | Public (with email domain validation) |

### Board Endpoints (`/api/v1/taskmanager/`)

| Method | Endpoint | Description | Auth Required | Permission |
| :--- | :--- | :--- | :--- | :--- |
| **GET** | `/boards/` | List all boards in organization | Yes | Any authenticated user |
| **POST** | `/boards/create/` | Create a new board | Yes | Any authenticated user |
| **GET** | `/boards/<uuid:board_id>/` | Get board details | Yes | Any authenticated user |
| **PATCH** | `/boards/<uuid:board_id>/` | Update board | Yes | Creator only |
| **DELETE** | `/boards/<uuid:board_id>/` | Delete board | Yes | Creator only |

### Task Endpoints (`/api/v1/taskmanager/`)

| Method | Endpoint | Description | Auth Required | Permission |
| :--- | :--- | :--- | :--- | :--- |
| **GET** | `/tasks/` | List tasks (filterable by `board_id`, `status`, `priority`) | Yes | Any authenticated user |
| **POST** | `/tasks/create/` | Create a new task | Yes | Any authenticated user |
| **GET** | `/tasks/<uuid:task_id>/` | Get task details | Yes | Any authenticated user |
| **PATCH** | `/tasks/<uuid:task_id>/` | Update task (partial update supported) | Yes | Creator only |
| **DELETE** | `/tasks/<uuid:task_id>/` | Delete task | Yes | Creator only |

**Query Parameters for `/tasks/`:**
- `board_id` (UUID): Filter by board
- `status` (string): Filter by status (PENDING, IN_PROGRESS, COMPLETED, CANCELLED, ON_HOLD)
- `priority` (string): Filter by priority (LOW, MEDIUM, HIGH, URGENT)

### Scheduled Task Endpoints (`/api/v1/taskmanager/`)

| Method | Endpoint | Description | Auth Required | Permission |
| :--- | :--- | :--- | :--- | :--- |
| **GET** | `/scheduled-tasks/` | List own scheduled tasks (filterable by `processing_status`) | Yes | Any authenticated user |
| **POST** | `/scheduled-tasks/create/` | Create a scheduled task | Yes | Any authenticated user |
| **GET** | `/scheduled-tasks/<uuid:scheduled_task_id>/` | Get scheduled task details | Yes | Creator only |

**Query Parameters for `/scheduled-tasks/`:**
- `processing_status` (integer): Filter by processing status (0=Pending, 1=Processed, 2=Failed)

### Audit Log Endpoints (`/api/v1/taskmanager/`)

| Method | Endpoint | Description | Auth Required | Permission |
| :--- | :--- | :--- | :--- | :--- |
| **GET** | `/audit-logs/` | List audit logs (filterable by `action_type`, `user_id`) | Yes | Admin/Owner |
| **GET** | `/audit-logs/<uuid:audit_log_id>/` | Get audit log details | Yes | Admin/Owner |

**Query Parameters for `/audit-logs/`:**
- `action_type` (string): Filter by action type
- `user_id` (UUID): Filter by user

### Organization Endpoints (`/api/v1/organization/`)

| Method | Endpoint | Description | Auth Required | Permission |
| :--- | :--- | :--- | :--- | :--- |
| **GET** | `/subscription-plans/` | List all subscription plans | No | Public |
| **GET** | `/subscription-plans/<uuid:subscription_plan_id>/` | Get subscription plan details | No | Public |
| **POST** | `/organizations/` | Create new organization (public signup) | No | Public |
| **GET** | `/organization/` | Get current organization details | Yes | Admin/Owner |
| **PATCH** | `/organization/` | Update organization details | Yes | Owner only |
| **GET** | `/organization/subscription/` | Get organization subscription | Yes | Admin/Owner |
| **PATCH** | `/organization/subscription/` | Update subscription (cancel or update stripe_id) | Yes | Owner only |
| **GET** | `/organization/subscription-status/` | Get subscription status | Yes | Admin/Owner |

**Subscription Update Actions:**
- `{"action": "cancel"}` - Cancel subscription
- `{"action": "update_stripe_id", "stripe_id": "..."}` - Update Stripe subscription ID

---

## Authentication & Security

### JWT Authentication Strategy

**The Vulnerability: JWT & Integer IDs**

During initial design using `SimpleJWT` and standard Integer IDs (`user_id`), we identified a critical vulnerability:
- **Scenario**: If User A has `id=2` in Organization A, and a different User B has `id=2` in Organization B.
- **The Attack**: A malicious user could take a valid JWT token from Organization A (containing `user_id: 2`) and send it to Organization B's domain.
- **Result**: The system would decode the token, see `user_id: 2`, and mistakenly authenticate the request as User B in Organization B. This allowed cross-organization impersonation.

### Solution: UUID Primary Keys

We implemented **UUID** for all primary keys:
- **Global Uniqueness**: Makes ID collisions impossible across organizations
- **Security**: An ID from Organization A simply will not exist in Organization B's database, eliminating IDOR (Insecure Direct Object Reference) vulnerability at the database level
- **Centralized Users**: With users in the shared schema, UUID ensures global uniqueness across all organizations

### JWT Token Structure

- **Access Token**: Short-lived (default: 60 minutes), contains `user_id` (UUID)
- **Refresh Token**: Longer-lived (default: 1 day), used to obtain new access tokens
- **Token Blacklisting**: Global token blacklisting via `rest_framework_simplejwt.token_blacklist` (tokens reference shared schema users)
- **Custom Authentication**: `JWTAuthentication` class checks `is_restricted` flag in addition to `is_active`

### Email Domain Restriction

Organizations can restrict user signups to specific email domains:
- Each organization has an `email_domain` field (e.g., `company.com`)
- Users can only signup if their email domain matches the organization's `email_domain`
- Prevents unauthorized users from joining organizations

---

## Permissions & Access Control

### Permission Classes

#### `IsOrganizationAdminOrOwner`
- **Purpose**: Allows access to admin or owner users
- **Checks**: `is_admin=True` OR `is_org_owner=True`
- **Used For**: Viewing resources (user lists, audit logs, organization details)
[]


### Resource-Level Permissions

- **Tasks/Boards**: Creator can update/delete their own resources
- **Scheduled Tasks**: Users can only view their own scheduled tasks
- **Audit Logs**: Admin/Owner only
- **User Management**: Admin/Owner can view all users, users can view/update themselves
- **Organization**: Owner can update, Admin/Owner can view

---

## Shared vs Tenant Apps

### Design Decision: Where Do Apps Live?

This is a critical architectural decision in multi-tenant applications. Here's how TaskFlow is structured:

#### **SHARED_APPS** (Public Schema)
- `django_tenants` - Core multi-tenancy framework
- `organizations` - Contains tenant model (`Organization`), domain routing, subscription plans
- `accounts` - User accounts (centralized for analytics and unified authentication)
- `django.contrib.contenttypes` - Required for Django's content types framework
- `django.contrib.sessions` - Session management (shared across tenants)
- `django.contrib.messages` - Django messages framework
- `django.contrib.staticfiles` - Static file serving
- `django.contrib.admin` - Django admin interface

**Why Shared?**
- These models need to exist in the public schema to route requests and manage tenants
- `Organization` and `Domain` are the core tenant routing mechanisms
- Subscription plans are shared across all tenants
- **User accounts are shared** for centralized analytics and unified authentication

#### **TENANT_APPS** (Per-Tenant Schema)
- `django.contrib.contenttypes` - Required in each tenant schema
- `django.contrib.messages` - Messages per tenant
- `django.contrib.admin` - Admin per tenant
- `rest_framework` - API framework (endpoints are tenant-specific)
- `task_manager` - Tasks, boards, scheduled tasks, audit logs (isolated per tenant)

**Why Tenant?**
- **Data Isolation**: Tasks and business data must be completely isolated per tenant
- **Security**: Each tenant's data is strictly separated
- **Scalability**: Each tenant's data grows independently
- **Compliance**: Complete data separation for regulatory compliance

### Why `accounts` is in SHARED_APPS

**Design Decision**: User accounts live in the shared schema (public schema).

**Reasons:**
1. **Centralized Analytics**: All users in one place enables cross-organization analytics and reporting
2. **Unified Authentication**: Single authentication source simplifies user management and SSO capabilities
3. **Organization Relationship**: Each user belongs to exactly one organization (enforced via ForeignKey)
4. **UUID Security**: With UUID primary keys, user IDs are globally unique, preventing IDOR attacks
5. **Query Efficiency**: Centralized user queries are more efficient than querying across multiple tenant schemas
6. **Organization Isolation**: Users are filtered by organization at the application level, ensuring data isolation

**How It Works:**
- Users are stored in the public schema with an `organization` ForeignKey
- Authentication validates that the user belongs to the current organization (from request.tenant)
- All user queries are filtered by organization to maintain data isolation
- JWT tokens include `user_id` which is validated against the shared user table
- Organization context is validated during authentication to prevent cross-organization access

---

## Setup Instructions

### Prerequisites

- Docker & Docker Compose
- Python 3.10+ (for local development)
- PostgreSQL 16+ (handled by Docker)

### Environment Configuration

1. **Copy environment file:**
    ```bash
    # Linux/Mac
    cp .env.example .env
    
    # Windows
    copy .env.example .env
    ```


2. **Generate Secret Key:**
   ```bash
   python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
   ```

### Running Locally

1. **Start the Application:**
    ```bash
    docker-compose up --build
    ```
   This runs the `start.sh` script which:
   - Checks database connection
   - Sets up cron jobs
   - Applies migrations (shared and tenant schemas)
   - Starts the Django server

2. **Create Your First Organization:**
   
   **Option A: Via API (Recommended)**
   ```bash
   curl -X POST http://localhost:8000/api/v1/organization/organizations/ \
     -H "Content-Type: application/json" \
     -d '{
       "business_name": "My Company",
       "owner_email": "owner@mycompany.com",
       "password": "securepassword123",
       "billing_email": "billing@mycompany.com",
       "billing_address": "123 Main St, City, Country",
       "email_domain": "mycompany.com",
       "subscription_plan_id": "<uuid-of-free-plan>",
       "billing_cycle": "MONTHLY",
       "end_date": "2025-12-31"
     }'
   ```

   **Option B: Via Django Shell**
    ```bash
    docker-compose exec web python manage.py shell
    ```
    ```python
   from organizations.models import Organization, Domain, SubscriptionPlan, Subscription
   from django.utils import timezone
   from datetime import timedelta
   
   # Create subscription plan
   plan = SubscriptionPlan.objects.create(
       display_name="FREE",
       price=0.00,
       currency="USD",
       max_users=5,
       max_tasks=100
   )
   
   # Create subscription
   subscription = Subscription.objects.create(
       subscription_plan=plan,
       billing_cycle="MONTHLY",
       end_date=timezone.now().date() + timedelta(days=365),
       next_payment_date=timezone.now().date() + timedelta(days=30),
       stripe_id="",
       is_active=True
   )
   
   # Create organization
   org = Organization.objects.create(
       business_name="My Company",
       owner_email="owner@mycompany.com",
       billing_email="billing@mycompany.com",
       billing_address="123 Main St",
       email_domain="mycompany.com",
       subscription=subscription,
       schema_name="my_company",
       is_active=True
   )
   
   # Create domain
   Domain.objects.create(
       domain="my-company.localhost",
       tenant=org,
       is_primary=True
   )
   
   # Create owner user in shared schema
   from accounts.models import UserAccount
   
   UserAccount.objects.create_user(
       email="owner@mycompany.com",
       password="securepassword123",
       organization=org,
       is_org_owner=True,
       is_staff=True,
       is_active=True
   )
   ```

3. **Verify Cron is Running:**
    ```bash
    docker-compose exec web service cron status
    # Output: [ ok ] cron is running.
    ```

4. **Access the Application:**
   - **API**: `http://my-company.localhost:8000/api/v1/`
   - **Django Admin**: `http://my-company.localhost:8000/admin/`
   - **Login**: Use the owner email and password you created


---

## Background Processing

### Scheduled Task Processing

The system uses a cron-based approach for processing scheduled tasks:

1. **Cron Job**: Runs every 2 minutes (`*/2 * * * *`)
2. **Management Command**: `process_tasks` iterates through all tenant schemas
3. **Processing**: Creates `Task` objects from `ScheduledTask` entries where `scheduled_time <= now()` and `processing_status = 0`

### Management Command

```bash
python manage.py process_tasks
```

This command:
- Iterates through all active tenant schemas
- Finds pending scheduled tasks (`processing_status=0`)
- Processes tasks that are due (`scheduled_time <= now()`)
- Creates `Task` objects and updates `ScheduledTask` status
- Creates audit logs and updates organization usage

### Cron Setup

The `start.sh` script automatically:
- Removes old cron jobs
- Adds new cron jobs from `CRONJOBS` setting
- Starts the cron service

---

## Logging

The application uses Python's `logging` module with a production-ready configuration:

### Log Files

- **`logs/django.log`**: All INFO level and above logs (rotates at 10MB, keeps 5 backups)
- **`logs/django_errors.log`**: ERROR level and above logs (rotates at 10MB, keeps 5 backups)
- **Console**: DEBUG level in development, INFO in production

### Loggers

- **Django**: Framework logs
- **django.request**: Request errors
- **django.server**: Server logs
- **django.db.backends**: Database query warnings
- **accounts**: Account-related logs
- **task_manager**: Task management logs
- **organizations**: Organization-related logs

### Log Format

- **Console**: Simple format with level, timestamp, module, and message
- **File**: Verbose format with level, timestamp, module, process ID, thread ID, and message

---

## Additional Notes

### Email Domain Validation

When creating users via `/api/v1/accounts/users/create/`:
- The user's email domain must match the organization's `email_domain`
- This prevents unauthorized users from joining organizations
- Example: If organization's `email_domain` is `company.com`, only emails ending in `@company.com` can signup


### Audit Logging

All important actions are logged to `AuditLog`:
- Task creation, updates, deletion, completion
- Board creation, updates, deletion
- Scheduled task creation
- Includes user, IP address, user agent, and metadata
