# Project Documentation: Multi-Tenant Task Manager

## 1. Problem Understanding & Scope

### **System Flow**
The system is designed as a product for **multiple tenants/organizations**.
* **Tenancy:** Each tenant (organization) has its own isolated environment.
* **Users:** Each tenant maintains its own list of users.
* **Tasks:** Users can Create, Read, Update, and Delete (CRUD) tasks specific to their organization.
* **Visibility:** A user can *only* view the tasks belonging to their specific organization.

### **Architecture Choice**
To maintain strict data isolation and correctly identify the context of each request (ensuring the database schema is the right one), I selected the **`django-tenants`** package. This allows me to route requests based on the domain (e.g., `tenant-a.localhost`) directly to the correct PostgreSQL schema.

---

## 2. Authentication Strategy & Security (Crucial Design Decision)

### **The Vulnerability: JWT & Integer IDs**
During the initial design using `SimpleJWT` and standard Integer IDs (`user_id`), I identified a critical vulnerability:
* **Scenario:** If User A has `id=2` in Tenant A, and a different User B has `id=2` in Tenant B.
* **The Attack:** A malicious user could take a valid JWT token from Tenant A (containing `user_id: 2`) and send it to Tenant B's domain.
* **Result:** The system would decode the token, see `user_id: 2`, and mistakenly authenticate the request as User B in Tenant B. This allowed cross-tenant impersonation.

### **Evaluated Solutions**
I considered three approaches to fix this:

1.  **Store `tenant_id` in Token Payload:**
    * *Pros:* Only one signing key; easy to implement.
    * *Cons:* High vulnerability if the token is leaked or manipulated; relies on application logic to check the ID.
2.  **Separate Signing Keys per Tenant:**
    * *Pros:* Strict cryptographic isolation.
    * *Cons:* Enterprise-level complexity to manage and rotate keys for every new tenant.
3.  **Use UUIDs (Selected Approach):**
    * *Pros:* Global uniqueness makes ID collisions impossible. An ID from Tenant A simply will not exist in Tenant B's database.
    * *Optimization:* I specifically chose **UUIDv7**. It is time-based, ensuring that database indexing remains fast (unlike random UUIDv4).

### **Final Decision**
I implemented **UUIDv7** for all primary keys. This eliminates the IDOR (Insecure Direct Object Reference) vulnerability at the database level while maintaining high performance.

---

## 3. Architecture & Design

### **High-Level Architecture**
The project uses **Schema-Based Multi-Tenancy** via the `django-tenants` library.

1.  **The Landlord (Public Schema):**
    * Acts as the router and registry.
    * Stores `Client` (Tenant) and `Domain` information.

2.  **The Apartments (Tenant Schemas):**
    * Each tenant gets a dedicated PostgreSQL schema.
    * Business logic is shared, but data is strictly siloed.

### **Background Processing Strategy**
Instead of an asynchronous task queue (Celery), I implemented a **Database-Polling Pattern**:
1.  **Queue:** A `ScheduledTask` table acts as the queue.
2.  **Scheduler:** A system `cron` job runs every minute inside the container.
3.  **Worker:** A custom Django Management Command (`process_tasks`) wakes up, iterates through every tenant schema, and processes tasks that are due.

---

## 4. Database Schema

### **Global Tables (Public Schema)**
| Table | Description |
| :--- | :--- |
| **Client** | Stores tenant metadata (Schema Name, Company Name). |
| **Domain** | Maps the URL (e.g., `tenant-a.localhost`) to a Client. |

### **Tenant Tables (Replicated in every Tenant Schema)**
| Table | Fields | Description |
| :--- | :--- | :--- |
| **User** | **UUIDv7 (PK)**, Username, Password | Users are isolated per tenant. |
| **Task** | `title`, `description`, `status`, `created_by` | The active tasks visible in the dashboard. |
| **ScheduledTask** | `title`, `scheduled_time`, `processing_status`, `failure_reason` | The "Waiting Room" for future tasks. Statuses: `0` (Pending), `1` (Success), `2` (Fail). |

---

## 5. API Endpoints

All endpoints (except Admin) must be accessed via a Tenant Domain (e.g., `http://tenant-a.localhost:8000/...`).

### **Authentication**

| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| **POST** | `/api/register/` | Register a new user in the current tenant. | No |
| **POST** | `/api/login/` | Obtain JWT Access & Refresh tokens. | No |
| **POST** | `/api/token/refresh/` | Get a new Access token using a Refresh token. | No |

### **Task Management (Immediate)**

| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| **GET** | `/api/tasks/` | List all tasks for the logged-in user's tenant. | **Yes** |
| **POST** | `/api/tasks/` | Create a new task immediately. | **Yes** |
| **GET** | `/api/tasks/<uuid>/` | Retrieve details of a specific task. | **Yes** |
| **PUT** | `/api/tasks/<uuid>/` | Fully update a task (requires all fields). | **Yes** |
| **PATCH** | `/api/tasks/<uuid>/` | Partially update a task (e.g., just status). | **Yes** |
| **DELETE** | `/api/tasks/<uuid>/` | Delete a specific task. | **Yes** |

### **Background Jobs (Scheduled)**

| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| **POST** | `/api/tasks/schedule/` | Schedule a task to run in the future. <br> **Body:** `{ "title": "...", "scheduled_time": "ISO-8601" }` | **Yes** |

---

## 6. Setup Instructions

### **Prerequisites**
* Docker & Docker Compose

### **Running Locally**
1.  **Start the Application:**
    ```bash
    docker-compose up --build
    ```
    *This runs the `start.sh` script which installs cron jobs, applies migrations, and starts the Django server.*

2.  **Create Tenants (First Run Only):**
    ```bash
    docker-compose exec web python manage.py shell
    ```
    ```python
    from customers.models import Client, Domain
    
    # 1. Create Public Tenant (Required)
    public = Client.objects.create(schema_name='public', name='Public Tenant')
    Domain.objects.create(domain='localhost', tenant=public)

    # 2. Create Company A
    tenant_a = Client.objects.create(schema_name='tenant_a', name='Company A')
    Domain.objects.create(domain='tenant-a.localhost', tenant=tenant_a)
    ```

3.  **Verify Cron is Running:**
    ```bash
    docker-compose exec web service cron status
    # Output: [ ok ] cron is running.
    ```
