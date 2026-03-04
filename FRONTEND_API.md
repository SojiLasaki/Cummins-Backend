# Frontend API Guide

Base URL when running locally: **`http://localhost:8000`** (or your backend host). All API routes are under **`/api/`**.

## Discovery (no auth)

```http
GET /api/
```

Returns JSON with `api_base`, `auth`, `endpoints`, and `auth_required`. Use this to build URLs in the frontend.

## Authentication

- **Login (get access token):**  
  `POST /api/auth/login/`  
  Body: `{ "username": "...", "password": "..." }`  
  Response: `{ "access": "<jwt>", "refresh": "<jwt>" }`

- **Refresh token:**  
  `POST /api/auth/refresh/`  
  Body: `{ "refresh": "<refresh_token>" }`  
  Response: `{ "access": "<new_jwt>" }`

- **Authenticated requests:**  
  Send header:  
  `Authorization: Bearer <access_token>`

All endpoints below (except `GET /api/` and auth) require this header.

## Technicians

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/api/technicians/` | List technicians (supports `?status=`, `?specialization=`, `?station=`, `?search=`, `?ordering=`) |
| GET | `/api/technicians/{id}/` | One technician |
| GET | `/api/technicians/{id}/tickets/` | Tickets assigned to this technician |
| GET | `/api/technicians/{id}/schedules/` | Schedules for this technician |
| POST | `/api/technicians/` | Create (body: username, email, first_name, last_name, password, specialization, ...) |
| PUT/PATCH | `/api/technicians/{id}/` | Update |
| DELETE | `/api/technicians/{id}/` | Delete |

**List item shape:** `id`, `profile_id` (UUID, use to match `ticket.assigned_technician_profile_id`), `assigned_tickets_count`, `first_name_display`, `last_name_display`, `username_display`, `email_display`, `status`, `specialization`, `station`, `station_name`, ...

## Tickets

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/api/tickets/` | List tickets (`?assigned_technician=<uuid_or_pk>`, `?status=`, `?search=`, `?ordering=`) |
| GET | `/api/tickets/{id}/` | One ticket |
| GET | `/api/tickets/{id}/schedules/` | Schedules for this ticket |
| POST | `/api/tickets/` | Create ticket (auto-assigns technician when possible) |
| PUT/PATCH | `/api/tickets/{id}/` | Update |
| DELETE | `/api/tickets/{id}/` | Delete |

**List/detail shape:** `id`, `ticket_id`, `assigned_technician_id`, `assigned_technician_profile_id`, `assigned_technician_first_name`, `assigned_technician_last_name`, `customer`, `title`, `description`, `issue_description`, `status`, `priority`, `severity`, `created_at`, `assigned_at`, `parts`, `diagnostic_reports`, ...  
If no technician is assigned, `assigned_technician_id` and `assigned_technician_profile_id` are `null`; first/last name are `""`.

## Schedules

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/api/schedules/` | List (`?technician=`, `?customer=`, `?ticket=`, `?from_date=`, `?to_date=`, `?ordering=`) |
| GET | `/api/schedules/{id}/` | One schedule |
| POST | `/api/schedules/` | Create |
| PUT/PATCH | `/api/schedules/{id}/` | Update |
| DELETE | `/api/schedules/{id}/` | Delete |

**Create body:** `customer` (UUID), `technician` (pk), `ticket` (UUID, optional), `scheduled_time` (ISO datetime), `duration` (e.g. `"01:00:00"`), `description`.  
**List item shape:** `id`, `scheduled_time`, `duration`, `description`, `technician_id`, `technician_profile_id`, `technician_display_name`, `customer_id`, `customer_display_name`, `ticket_id`, `ticket_ticket_id`, `created_at`, `updated_at`.

## CORS and credentials

- Backend allows credentials (`CORS_ALLOW_CREDENTIALS = True`). Use `credentials: "include"` only if you send cookies; for JWT-only, `Authorization` is enough.
- Allowed origins in dev include `http://localhost:5173`, `http://localhost:3000`, `http://localhost:8080`, etc. For production set `CORS_ALLOWED_ORIGINS` or use env `CORS_ALLOW_ALL_ORIGINS=false`.

## Example (fetch)

```javascript
const API_BASE = "http://localhost:8000/api";

// 1. Login
const loginRes = await fetch(`${API_BASE}/auth/login/`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ username: "user", password: "pass" }),
});
const { access } = await loginRes.json();

// 2. List technicians
const techRes = await fetch(`${API_BASE}/technicians/`, {
  headers: { Authorization: `Bearer ${access}` },
});
const technicians = await techRes.json();

// 3. List tickets for a technician (by profile_id from technicians list)
const profileId = technicians[0].profile_id;
const ticketsRes = await fetch(
  `${API_BASE}/tickets/?assigned_technician=${profileId}`,
  { headers: { Authorization: `Bearer ${access}` } }
);
const tickets = await ticketsRes.json();

// 4. List schedules for a technician
const schedRes = await fetch(
  `${API_BASE}/schedules/?technician=${profileId}`,
  { headers: { Authorization: `Bearer ${access}` } }
);
const schedules = await schedRes.json();
```

## Linking data in the UI

- **Ticket → Technician:** Use `ticket.assigned_technician_profile_id` and match to `technician.profile_id`, or use `ticket.assigned_technician_id` and link to `/api/technicians/{id}/`.
- **Technician → Tickets:** Use `GET /api/technicians/{id}/tickets/` or `GET /api/tickets/?assigned_technician={profile_id}`.
- **Technician → Schedules:** Use `GET /api/technicians/{id}/schedules/` or `GET /api/schedules/?technician={profile_id}`.
- **Ticket → Schedules:** Use `GET /api/tickets/{id}/schedules/` or `GET /api/schedules/?ticket={ticket_id}`.
