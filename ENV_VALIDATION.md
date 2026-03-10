# Environment Configuration Checklist

## ✅ Django Core Settings

- [ ] `SECRET_KEY` - Generate using: `python -c "import secrets; print(secrets.token_urlsafe(50))"`
- [ ] `DEBUG` - Set to `False` for production
- [ ] `ALLOWED_HOSTS` - Include your Render app URL and frontend domain
- [ ] `DJANGO_SETTINGS_MODULE` - Should be `breakthru.settings.base`

## ✅ Database Connection (Supabase)

Your `.env` should use **ONE** of these methods:

### Method 1: Using DATABASE_URL (Recommended)
```
DATABASE_URL=postgresql://postgres:[PASSWORD]@[project-ref].[region].supabase.co:5432/postgres?sslmode=require
```

**Where to find it:**
1. Go to Supabase Dashboard → Project Settings → Database
2. Click "Connection String"
3. Choose "Node.js" from dropdown
4. Replace `[YOUR_PASSWORD]` with your actual password
5. Copy the full URL

### Method 2: Using Individual Variables
```
DB_ENGINE=django.db.backends.postgresql
DB_NAME=postgres
DB_USER=postgres
DB_PASSWORD=[YOUR-PASSWORD]
DB_HOST=[project-ref].[region].supabase.co
DB_PORT=5432
```

**Do NOT use both methods at the same time.** If DATABASE_URL is set, individual DB_* variables are ignored.

## ✅ Redis Connection (Upstash for WebSockets)

```
REDIS_HOST=[your-redis-host].upstash.io
REDIS_PORT=6379
REDIS_PASSWORD=[your-redis-password]
```

**Where to find it:**
1. Log in to [upstash.com](https://upstash.com)
2. Open your Redis database
3. Click "Details"
4. Get REDIS_HOST and REDIS_PASSWORD from REST API credentials

## ✅ CORS Configuration

```
CORS_ALLOW_ALL_ORIGINS=false
CORS_ALLOWED_ORIGINS=https://breakthru-dashboard.vercel.app,http://localhost:3000
```

## ✅ OpenAI API (for LangChain agents)

```
OPENAI_API_KEY=sk-[your-actual-key]
```

Get from: [platform.openai.com/api-keys](https://platform.openai.com/api-keys)

## ✅ Supabase Auth (Optional)

```
SUPABASE_URL=https://[project-ref].[region].supabase.co
SUPABASE_KEY=[anon-key]
SUPABASE_SERVICE_KEY=[service-key]
```

Get from: Supabase Dashboard → Project Settings → API

## 🚨 Common Mistakes

| ❌ Wrong | ✅ Correct |
|---------|-----------|
| `SUPABASE_URL="postgresql://..."` | Use `DATABASE_URL="postgresql://..."` for Django |
| Port 6543 (pgBouncer) | Use port **5432** for Django |
| Missing `?sslmode=require` | Include it for Supabase |
| Mixing DATABASE_URL + DB_* vars | Use **one method only** |
| `SUPABASE_KEY=Localhost:2004` | Use actual API key from dashboard |

## 🔍 How to Verify Your Connection

Run this command to test:

```bash
python manage.py migrate
```

If it works, your database connection is correct!

If you get an error, check:
- [ ] DATABASE_URL format is correct
- [ ] Password has no special characters that need escaping
- [ ] Redis is accessible (if using WebSockets)
- [ ] ALLOWED_HOSTS includes your domain

## 📝 Your .env.example vs Your .env

- **`.env.example`** - Template with placeholders (committed to git)
- **`.env`** - Actual secrets (should be in `.gitignore`)

Make sure `.env` is never committed to version control!
