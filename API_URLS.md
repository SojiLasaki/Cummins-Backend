# All API URLs for Frontend

**Base URL:** `http://localhost:8000` (or your backend host)

Prefix all paths below with: **`/api/`** except AI routes which use **`/api/ai/`**.

---

## Discovery & Auth (no auth for GET /api/ and auth endpoints)

| Method | URL |
|--------|-----|
| GET | `/api/` |
| POST | `/api/auth/login/` |
| POST | `/api/auth/refresh/` |

---

## Technicians

| Method | URL |
|--------|-----|
| GET | `/api/technicians/` |
| POST | `/api/technicians/` |
| GET | `/api/technicians/{id}/` |
| PUT | `/api/technicians/{id}/` |
| PATCH | `/api/technicians/{id}/` |
| DELETE | `/api/technicians/{id}/` |
| GET | `/api/technicians/{id}/tickets/` |
| GET | `/api/technicians/{id}/schedules/` |
| GET | `/api/technician/search/?q=...` |

---

## Tickets

| Method | URL |
|--------|-----|
| GET | `/api/tickets/` |
| POST | `/api/tickets/` |
| GET | `/api/tickets/{id}/` |
| PUT | `/api/tickets/{id}/` |
| PATCH | `/api/tickets/{id}/` |
| DELETE | `/api/tickets/{id}/` |
| GET | `/api/tickets/{id}/schedules/` |

---

## Schedules

| Method | URL |
|--------|-----|
| GET | `/api/schedules/` |
| POST | `/api/schedules/` |
| GET | `/api/schedules/{id}/` |
| PUT | `/api/schedules/{id}/` |
| PATCH | `/api/schedules/{id}/` |
| DELETE | `/api/schedules/{id}/` |

---

## Users & Admin

| Method | URL |
|--------|-----|
| GET | `/api/admin-users/` |
| GET | `/api/admin-users/{id}/` |
| GET | `/api/all-users/` |
| GET | `/api/all-users/{id}/` |
| GET | `/api/stations/` |
| GET | `/api/stations/{id}/` |
| GET | `/api/regions/` |
| GET | `/api/regions/{id}/` |

---

## Diagnostics

| Method | URL |
|--------|-----|
| GET | `/api/diagnostics/` |
| GET | `/api/diagnostics/{id}/` |
| GET | `/api/technician-reports/` |
| GET | `/api/technician-reports/{id}/` |
| POST | `/api/workflow/failure-detected/` |

---

## Orders

| Method | URL |
|--------|-----|
| GET | `/api/orders/` |
| POST | `/api/orders/` |
| GET | `/api/orders/{id}/` |
| PUT | `/api/orders/{id}/` |
| PATCH | `/api/orders/{id}/` |
| DELETE | `/api/orders/{id}/` |

---

## Customers

| Method | URL |
|--------|-----|
| GET | `/api/customers/` |
| POST | `/api/customers/` |
| GET | `/api/customers/{id}/` |
| PUT | `/api/customers/{id}/` |
| PATCH | `/api/customers/{id}/` |
| DELETE | `/api/customers/{id}/` |

---

## Assets

| Method | URL |
|--------|-----|
| GET | `/api/assets/` |
| POST | `/api/assets/` |
| GET | `/api/assets/{id}/` |
| PUT | `/api/assets/{id}/` |
| PATCH | `/api/assets/{id}/` |
| DELETE | `/api/assets/{id}/` |

---

## Inventory

| Method | URL |
|--------|-----|
| GET | `/api/inventory/` |
| GET | `/api/components/` |
| GET | `/api/components/{id}/` |
| GET | `/api/parts/` |
| GET | `/api/parts/{id}/` |

---

## Logs

| Method | URL |
|--------|-----|
| GET | `/api/logs/` |
| GET | `/api/logs/{id}/` |

---

## Manuals

| Method | URL |
|--------|-----|
| GET | `/api/manuals/` |
| GET | `/api/manuals/{id}/` |
| GET | `/api/tags/` |
| GET | `/api/tags/{id}/` |
| GET | `/api/images/` |
| GET | `/api/images/{id}/` |

---

## Staffs

| Method | URL |
|--------|-----|
| GET | `/api/staffs/` |
| GET | `/api/staffs/{id}/` |

---

## AI (`/api/ai/`)

| Method | URL |
|--------|-----|
| POST | `/api/ai/chat/` |
| GET | `/api/ai/agent_prompts/current/` |
| GET | `/api/ai/knowledge_documents/` |
| GET | `/api/ai/knowledge_documents/{id}/` |
| GET | `/api/ai/knowledge_chunks/` |
| GET | `/api/ai/knowledge_chunks/{id}/` |
| GET | `/api/ai/knowledge_entities/` |
| GET | `/api/ai/knowledge_entities/{id}/` |
| GET | `/api/ai/knowledge_relations/` |
| GET | `/api/ai/knowledge_relations/{id}/` |
| GET | `/api/ai/model_endpoints/` |
| GET | `/api/ai/model_endpoints/{id}/` |
| GET | `/api/ai/mcp_adapters/` |
| GET | `/api/ai/mcp_adapters/{id}/` |
| GET | `/api/ai/knowledge_graph/` |
| GET | `/api/ai/agent_actions/` |
| GET | `/api/ai/agent_actions/{id}/` |

---

## Copy-paste base + paths (JavaScript)

```javascript
const API_BASE = "http://localhost:8000/api";

// Auth
const AUTH = {
  login: `${API_BASE}/auth/login/`,
  refresh: `${API_BASE}/auth/refresh/`,
};

// Technicians & tickets & schedules
const TECHNICIANS = `${API_BASE}/technicians/`;
const technicianById = (id) => `${API_BASE}/technicians/${id}/`;
const technicianTickets = (id) => `${API_BASE}/technicians/${id}/tickets/`;
const technicianSchedules = (id) => `${API_BASE}/technicians/${id}/schedules/`;

const TICKETS = `${API_BASE}/tickets/`;
const ticketById = (id) => `${API_BASE}/tickets/${id}/`;
const ticketSchedules = (id) => `${API_BASE}/tickets/${id}/schedules/`;

const SCHEDULES = `${API_BASE}/schedules/`;
const scheduleById = (id) => `${API_BASE}/schedules/${id}/`;

// Others
const CUSTOMERS = `${API_BASE}/customers/`;
const ORDERS = `${API_BASE}/orders/`;
const DIAGNOSTICS = `${API_BASE}/diagnostics/`;
const STATIONS = `${API_BASE}/stations/`;
const REGIONS = `${API_BASE}/regions/`;
const AI_CHAT = `${API_BASE}/ai/chat/`;
```

All endpoints under `/api/` (except `GET /api/` and `POST /api/auth/login/`, `POST /api/auth/refresh/`) require header: **`Authorization: Bearer <access_token>`**.
