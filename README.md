# TaskFlow - Multi-Tenant Task Management System

A multi-tenant SaaS application built with Django that enables organizations to manage tasks, boards, and team collaboration within completely isolated tenant environments. Each organization operates in its own PostgreSQL schema, ensuring complete data isolation while sharing the same application codebase.

---

## Documentation

### 1. Problem Understanding Summary

#### What I Understood

I built TaskFlow to solve the challenge of creating a scalable, secure, multi-tenant task management system. The core problem was building a SaaS platform where multiple organizations could use the same application instance while maintaining strict data isolation, security, and performance.

#### Key Challenges I Identified

1. **Data Isolation**: Ensuring one organization's data is completely invisible to another at the database level. Critical for security and compliance.

2. **Architectural Complexity**: Deciding which components belong in the shared schema versus tenant-specific schemas. This impacts analytics, query performance, and migrations.

3. **Permission Management**: Implementing a flexible permission system that works across tenant boundaries. Users need different roles (owner, admin, regular user) with appropriate access levels.

4. **Performance at Scale**: As tenants grow, I need efficient database queries, proper indexing, and background job processing that doesn't impact user operations.

---

### 2. Architecture & Design Document

#### High-Level Architecture

I use **Schema-Based Multi-Tenancy** via `django-tenants`. The public schema acts as a router, and each organization gets its own PostgreSQL schema for complete data isolation.

**Public Schema (Shared)**
- Stores `Organization`, `Domain`, `SubscriptionPlan`, `Subscription`, and `UserAccount` models
- Routes requests based on domain to the correct tenant schema
- Enables cross-organization analytics and unified authentication

**Tenant Schemas (Per Organization)**
- Each organization has a dedicated PostgreSQL schema
- Contains `Task`, `Board`, `AuditLog`, and `DailyStats` models
- Data is completely isolated between tenants

#### Request Flow

1. Request arrives with domain (e.g., `abc.localhost`)
2. `TenantMainMiddleware` extracts domain, looks up organization, switches to tenant schema
3. `JWTAuthentication` validates JWT token, checks user belongs to organization
4. View processes request in tenant schema context
5. Results returned to client

#### Key Components and Responsibilities

- **Organizations App**: Tenant model, domain routing, subscription management
- **Accounts App**: Centralized user accounts, JWT authentication, permissions
- **Task Manager App**: Tasks, boards, audit logs, daily statistics
- **Notifications App**: Background notification processing via Django-Q2

#### How Tenant Isolation is Enforced

1. **Database Level**: Each tenant has a separate PostgreSQL schema
2. **Middleware Level**: Automatically switches database connection to tenant schema
3. **Authentication Level**: Validates user belongs to current organization
4. **Application Level**: All queries filtered by organization
5. **UUID Security**: All primary keys use UUIDs to prevent IDOR attacks

#### Background Processing Approach

I use Django-Q2 for asynchronous task processing. Workers run in a separate process, using the database as the message broker. Notifications are queued when tasks are created and processed asynchronously.

#### Rate Limiting or Quota Strategy

- Anonymous users: 10 requests/minute (configurable)
- Authenticated users: 100 requests/minute (configurable)

---

### 3. Database Schema

#### Tables

**Public Schema (Shared)**
- `organizations_organization`: Tenant data
- `organizations_domain`: Domain to organization mapping
- `organizations_subscriptionplan`: Billing tiers
- `organizations_subscription`: Active subscriptions
- `accounts_useraccount`: Centralized user accounts

**Tenant Schema (Per Organization)**
- `task_manager_task`: Tasks with status, priority, assignments
- `task_manager_board`: Task organization
- `task_manager_auditlog`: Audit trail
- `task_manager_dailystats`: Pre-aggregated analytics for a particular day

#### Relationships

- `UserAccount` → `Organization` (ForeignKey)
- `Task` → `Board` (ForeignKey)
- `Task` → `UserAccount` (ForeignKey for creator, ForeignKey for assigned_to)
- `Board` → `UserAccount` (ForeignKey for creator)
- `AuditLog` → `UserAccount` (ForeignKey)

#### Indexes

**UserAccount**: `email` (unique), `(organization, email)`, `(organization, is_active)`

**Organization**: `business_name`, `owner_email`, `email_domain`, `(is_active, business_name)`, `(owner_email, is_active)`

**Subscription**: `subscription_plan`, `is_active`, `billing_cycle`, `stripe_id` (unique), `started_at`, `end_date`, `next_payment_date`, `(is_active, end_date)`, `(is_active, billing_cycle)`

**SubscriptionPlan**: `display_name`, `currency`, `(currency, price)`

**Task**: `task_id` (PK), `title`, `status`, `priority`, `board`, `created_by`, `assigned_to`, `due_date`, `created_at`, `(board, status, -created_at)`, `(priority, due_date)`, `(created_by, status)`, `(status, priority)`, `(assigned_to, status, priority)`

**Board**: `board_id` (PK), `name`, `created_by`, `created_at`

**AuditLog**: `audit_log_id` (PK), `user`, `action_type`, `created_at`, `(action_type, -created_at)`, `(user, -created_at)`

**DailyStats**: `daily_stats_id` (PK), `date`

#### How Tenant Data is Isolated

Each organization has its own PostgreSQL schema. The middleware automatically sets the `search_path` to the tenant's schema, so all queries only access that tenant's data. Even if you tried to query another tenant's data, PostgreSQL wouldn't find it because the schema isn't in the search path.

---

### 4. API Contracts

#### List of Endpoints

**Authentication** (`/api/v1/accounts/`)
- `POST /auth/login/` - Login, get JWT tokens
- `POST /auth/logout/` - Logout, blacklist token
- `POST /auth/refresh/` - Refresh access token
- `POST /auth/change-password/` - Change password

**Users** (`/api/v1/accounts/`)
- `GET /users/me/` - Get own profile
- `PATCH /users/me/` - Update own profile
- `GET /users/` - List users (Admin/Owner)
- `GET /users/<uuid>/` - Get user (Admin/Owner or self)
- `PATCH /users/<uuid>/` - Update user (Admin/Owner or self)
- `POST /users/create/` - Signup (email domain must match org)

**Boards** (`/api/v1/taskmanager/`)
- `GET /boards/` - List boards
- `POST /boards/create/` - Create board
- `GET /boards/<uuid>/` - Get board
- `PATCH /boards/<uuid>/` - Update board (creator only)
- `DELETE /boards/<uuid>/` - Delete board (creator only)

**Tasks** (`/api/v1/taskmanager/`)
- `GET /tasks/` - List tasks (filter: `board_id`, `status`, `priority`)
- `POST /tasks/create/` - Create task
- `GET /tasks/<uuid>/` - Get task
- `PATCH /tasks/<uuid>/` - Update task (creator only)
- `DELETE /tasks/<uuid>/` - Delete task (creator only)

**Audit Logs** (`/api/v1/taskmanager/`)
- `GET /audit-logs/` - List logs (filter: `action_type`, `user_id`) (Admin/Owner)
- `GET /audit-logs/<uuid>/` - Get log (Admin/Owner)

**Organizations** (`/api/v1/organization/`)
- `GET /subscription-plans/` - List plans (public)
- `GET /subscription-plans/<uuid>/` - Get plan (public)
- `POST /organization/create/` - Create organization (public)
- `GET /organization/` - Get organization (Admin/Owner)
- `PATCH /organization/` - Update organization (Owner)
- `GET /organization/subscription/` - Get subscription (Admin/Owner)
- `PATCH /organization/subscription/` - Update subscription (Owner)
- `GET /organization/subscription-status/` - Get status (Admin/Owner)

**Daily Stats** (`/api/v1/taskmanager/`)
- `GET /daily-stats/` - Get stats for date (query: `date=YYYY-MM-DD`) (Admin/Owner)

#### Request/Response Examples

All endpoints return JSON. Pagination uses `page` and `page_size` query parameters (default: 20, max: 100). Error responses include `error` or `detail` fields with descriptive messages.

#### Error Response Formats

- `400 Bad Request`: Validation errors with field names
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Permission denied
- `404 Not Found`: Resource not found
- `429 Too Many Requests`: Rate limit exceeded

---

### 5. Assumptions & Tradeoffs

#### What I Chose Not to Do and Why

1. **Row-Level Security**: I used schema-based isolation instead. It's more performant and simpler than checking tenant_id on every query.

2. **Soft Deletes**: Permanent deletes for simplicity. Audit logs track deletions for compliance.

3. **File Uploads**: Not implemented yet. Users can include file links in descriptions. Can add as feature later.

4. **Advanced Search**: Basic search filters are there, can be improved

5. **Task Dependencies**: Not implemented. Users can reference tasks in descriptions. Can add later.


#### Known Limitations

1. **Cross-Tenant Analytics**: Acts as a MIS, maintain `DailyStats` per tenant and can aggregate from public schema.

2. **Schema Migration Overhead**: Migrations must run on all tenant schemas. For many tenants, this takes time.

3. **User Centralization**: Users are in shared schema. If I wanted multi-org users, I'd need to refactor.

4. **Limited Job Monitoring**: Basic Django-Q2 monitoring. No comprehensive dashboard yet.

5. **No Auto Backup Strategy**: Each schema needs individual backup. Requires custom scripts.

6. **Basic Email Domain Validation**: Only exact domain matches.

---

### 6. Setup Instructions

#### How to Run the Project Locally

**Prerequisites**: Docker & Docker Compose (recommended) OR Python 3.10+ and PostgreSQL 16+

#### Docker Setup

1. **Clone the repository**:
    ```bash
   git clone <repository-url>
   cd TaskFlow
   ```

2. **Set environment variables** in `.env`:
   ```bash
   cp .env.example .env
   ```
   Then edit `.env` file with your configuration

3. **Start services**:
    ```bash
    docker-compose up --build
    ```

4. **Create first organization** via API or Django shell (see full setup docs for details)

5. **Access**: `http://<org-domain>.localhost:8000/api/v1/`

#### Local Development (Without Docker)

1. Set up virtual environment and install dependencies
2. Configure PostgreSQL database
3. Set `.env` with `DATABASE_HOST=localhost`
4. Run migrations: `python manage.py migrate_schemas --shared` then `--tenant`
5. Start workers: `python manage.py qcluster`
6. Start server: `python manage.py runserver`


## Additional Notes

- **Email Domain Validation**: Users can only signup if their email domain matches the organization's `email_domain`
- **Audit Logging**: All important actions are logged with user, IP, user agent, and metadata
- **Daily Statistics**: Pre-aggregated metrics for fast dashboard queries
- **Notifications**: Queued asynchronously via Django-Q2 when tasks are created
