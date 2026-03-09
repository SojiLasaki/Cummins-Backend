# Render Deployment Guide

## Environment Variables for Render

Set the following environment variables in your Render dashboard:

### Required Variables
```
SECRET_KEY=generate-a-new-secure-key-using-python-secrets
DEBUG=False
ALLOWED_HOSTS=your-render-app.onrender.com,breakthru-dashboard.vercel.app
DJANGO_SETTINGS_MODULE=breakthru.settings.base
```

### Database (PostgreSQL)
```
DATABASE_URL=postgresql://user:password@your-db-host:5432/cummins_db
```
Or use Render's PostgreSQL add-on and it will auto-provide DATABASE_URL.

### Redis (for WebSockets/Channels)
```
REDIS_HOST=your-redis-host
REDIS_PORT=6379
REDIS_PASSWORD=your-redis-password
```
Or use Render's Redis add-on.

### AI/LLM Integration
```
OPENAI_API_KEY=sk-your-openai-api-key
```

### CORS Settings (optional)
```
CORS_ALLOW_ALL_ORIGINS=false
CORS_ALLOWED_ORIGINS=https://breakthru-dashboard.vercel.app,http://localhost:3000
```

## Render Deployment Steps

1. **Connect your GitHub repo** to Render
2. **Create a Web Service**:
   - Branch: `main`
   - Build Command: 
     ```bash
     pip install -r requirements.txt && python manage.py migrate && python manage.py collectstatic --noinput
     ```
   - Start Command:
     ```bash
     gunicorn breakthru.wsgi:application
     ```

3. **Add Environment Variables**:
   - Set all variables listed in your `.env.example`
   - Use Render's PostgreSQL and Redis add-ons for automatic DATABASE_URL and REDIS_* variables

4. **Deploy**:
   - Push to GitHub
   - Render automatically deploys on push

## Security Requirements

Create a secure SECRET_KEY:
```python
import secrets
print(secrets.token_urlsafe(50))
```

Add to your `.env`:
```
SECRET_KEY=<generated-key>
```

## Database Migrations

Render will handle migrations via the build command:
```bash
python manage.py migrate
```

## Static Files

Django will collect static files during build:
```bash
python manage.py collectstatic --noinput
```

## Frontend Connection

Your Vercel frontend should use the Render app URL:
```
VITE_API_BASE_URL=https://your-render-app.onrender.com
```

Must match the URL in ALLOWED_HOSTS.

## Troubleshooting

**DisallowedHost error**: Make sure your Render URL is in ALLOWED_HOSTS environment variable.

**Static files not loading**: Run:
```bash
python manage.py collectstatic --noinput --clear
```

**WebSocket issues**: Ensure Redis is running and CHANNEL_LAYERS is configured in settings.
