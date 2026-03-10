# Supabase Integration Guide

## Setup Supabase for Cummins Backend

### 1. Create Supabase Project
- Go to [supabase.com](https://supabase.com)
- Sign up/login and create a new project
- Choose a region closest to your users
- Set a strong database password

### 2. Get Supabase Connection Details

#### Option A: Using Connection String (Recommended)
1. Navigate to **Project Settings** → **Database** → **Connection String**
2. Select **Node.js** to see the PostgreSQL connection URL
3. Copy and replace `[YOUR-PASSWORD]` with your database password
4. Add to `.env`:
```
DATABASE_URL=postgresql://postgres:[YOUR-PASSWORD]@[projects-ref].[region].supabase.co:5432/postgres?sslmode=require
```

#### Option B: Using Individual Variables
1. Get credentials from **Project Settings** → **Database**
   - **Host**: `[project-ref].[region].supabase.co`
   - **Database**: `postgres`
   - **User**: `postgres`
   - **Password**: The password you set during project creation
   - **Port**: `5432`

2. Add to `.env`:
```
DB_ENGINE=django.db.backends.postgresql
DB_NAME=postgres
DB_USER=postgres
DB_PASSWORD=your-supabase-password
DB_HOST=your-project.supabase.co
DB_PORT=5432
```

### 3. Run Django Migrations

After setting `DATABASE_URL` in `.env`, run:

```bash
python manage.py migrate
```

This will create all tables in your Supabase PostgreSQL database.

### 4. (Optional) Supabase Auth Integration

If you want to use Supabase's built-in authentication instead of JWT:

1. Get from **Project Settings** → **API**:
   - **URL**: Your Supabase project URL
   - **Anon Key**: Public API key for client-side access
   - **Service Key**: Secret key for server-side operations

2. Add to `.env`:
```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-key
```

3. Install Supabase Python client:
```bash
pip install supabase
```

4. Update [breakthru/settings/base.py](breakthru/settings/base.py) if using Supabase Auth.

### 5. Redis Setup for WebSockets

Supabase doesn't include Redis, so use **Upstash** (free tier available):

1. Go to [upstash.com](https://upstash.com)
2. Create a free Redis database
3. Get connection details from dashboard
4. Add to `.env`:
```
REDIS_HOST=your-redis-host.upstash.io
REDIS_PORT=6379
REDIS_PASSWORD=your-redis-password
```

### 6. Deploy on Render

1. Connect GitHub repo to Render
2. Add Environment Variables:
   - `DATABASE_URL` (from Supabase)
   - `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD` (from Upstash)
   - `SECRET_KEY`, `ALLOWED_HOSTS`, `OPENAI_API_KEY`

3. Set Build & Start Commands:
```bash
# Build
pip install -r requirements.txt && python manage.py migrate && python manage.py collectstatic --noinput

# Start
gunicorn breakthru.wsgi:application
```

### 7. Supabase Features You Can Use

- **Database**: PostgreSQL with all Django ORM support ✅
- **Auth**: Optional Supabase Auth (alternative to JWT)
- **Storage**: File uploads (configurable)
- **Realtime**: WebSockets (use with Channels/Redis)
- **Vector Search**: For AI features (pgvector extension available)

### 8. Troubleshooting

**SSL Error**: Make sure `sslmode=require` is in DATABASE_URL

**Connection Timeout**: Check Supabase project is running and firewall allows your IP

**Migration Errors**: Ensure database is empty before first migration

**WebSocket Issues**: Verify Redis is running and reachable

### Connection String Format

```
postgresql://[database_user]:[database_password]@[project_ref].[region].supabase.co:5432/[database_name]?sslmode=require
```

Replace:
- `[database_user]`: Usually `postgres`
- `[database_password]`: Your Supabase password
- `[project_ref]`: From your Supabase URL (e.g., `abc123xyz`)
- `[region]`: Your region (e.g., `us-east-1`)
- `[database_name]`: Usually `postgres`
