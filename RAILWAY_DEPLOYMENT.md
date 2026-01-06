# Railway Environment Variables Configuration

This file documents the required environment variables for deploying the backend on Railway.

## Required Environment Variables

### Core Django Settings
```
SECRET_KEY=your-secret-key-here-change-in-production
DEBUG=False
ALLOWED_HOSTS=.railway.app,yourdomain.com
```

### Database Configuration
```
DATABASE_URL=postgresql://user:password@host:port/dbname
```
Railway will automatically provide `DATABASE_URL` when you provision a PostgreSQL database.

### CORS and CSRF Settings
```
CORS_ALLOWED_ORIGINS=https://your-frontend.railway.app,https://yourdomain.com
CSRF_TRUSTED_ORIGINS=https://your-backend.railway.app,https://your-frontend.railway.app
```

### Email Configuration (Optional)
```
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
```

## Deployment Steps for Railway

### 1. Create New Project on Railway
- Go to https://railway.app
- Click "New Project"
- Select "Deploy from GitHub repo"
- Connect your repository

### 2. Add PostgreSQL Database
- In your Railway project, click "New"
- Select "Database" → "PostgreSQL"
- Railway will automatically set `DATABASE_URL`

### 3. Configure Environment Variables
Go to your service settings → Variables and add:
```
SECRET_KEY=<generate-a-strong-secret-key>
DEBUG=False
ALLOWED_HOSTS=.railway.app
CORS_ALLOWED_ORIGINS=https://your-frontend.railway.app
CSRF_TRUSTED_ORIGINS=https://your-backend.railway.app
```

### 4. Deploy
- Push your code to GitHub
- Railway will automatically detect and deploy
- Monitor logs for any errors

## Health Check
Railway will check the root endpoint `/` for health status.

## Static Files
Static files are served using WhiteNoise middleware (already configured).

## Migrations
Migrations run automatically on each deployment via the Procfile command.

## Port
Railway automatically sets the `PORT` environment variable. The application binds to `0.0.0.0:$PORT`.

## Logs
View logs in Railway dashboard → Deployments → View Logs
