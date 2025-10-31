# Quick Deployment Guide for Martingale

## Option 1: Deploy to Heroku (Recommended for beginners)

### Prerequisites
1. Install [Heroku CLI](https://devcenter.heroku.com/articles/heroku-cli)
2. Create a [Heroku account](https://signup.heroku.com/)

### Steps
1. **Login to Heroku**
   ```bash
   heroku login
   ```

2. **Create a new Heroku app**
   ```bash
   heroku create your-app-name
   ```

3. **Set environment variables**
   ```bash
   heroku config:set SECRET_KEY=$(python -c 'import secrets; print(secrets.token_hex(32))')
   heroku config:set FLASK_ENV=production
   heroku config:set INITIAL_CASH=100000
   ```

4. **Deploy**
   ```bash
   git add .
   git commit -m "Prepare for deployment"
   git push heroku main
   ```

5. **Open your app**
   ```bash
   heroku open
   ```

## Option 2: Deploy to Railway

### Prerequisites
1. Create a [Railway account](https://railway.app/)
2. Install Railway CLI (optional)

### Steps
1. **Connect your GitHub repository to Railway**
   - Go to [Railway](https://railway.app/)
   - Click "Start a New Project"
   - Select "Deploy from GitHub repo"
   - Choose your repository

2. **Set environment variables in Railway dashboard**
   - `SECRET_KEY`: Generate a secure random key
   - `FLASK_ENV`: `production`
   - `INITIAL_CASH`: `100000`

3. **Deploy automatically**
   - Railway will automatically build and deploy your app

## Option 3: Deploy to Render

### Prerequisites
1. Create a [Render account](https://render.com/)

### Steps
1. **Create a new Web Service**
   - Connect your GitHub repository
   - Choose "Web Service"

2. **Configure the service**
   - Build Command: `pip install -r requirements-prod.txt`
   - Start Command: `gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:$PORT app:app`

3. **Set environment variables**
   - `SECRET_KEY`: Generate a secure random key
   - `FLASK_ENV`: `production`
   - `INITIAL_CASH`: `100000`

## Option 4: Deploy to DigitalOcean App Platform

### Prerequisites
1. Create a [DigitalOcean account](https://www.digitalocean.com/)

### Steps
1. **Create a new App**
   - Go to DigitalOcean App Platform
   - Connect your GitHub repository

2. **Configure the app**
   - Runtime: Python
   - Build Command: `pip install -r requirements-prod.txt`
   - Run Command: `gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:$PORT app:app`

3. **Set environment variables**
   - `SECRET_KEY`: Generate a secure random key
   - `FLASK_ENV`: `production`
   - `INITIAL_CASH`: `100000`

## Important Notes

### Before Deployment
1. **Generate a secure SECRET_KEY**:
   ```python
   import secrets
   print(secrets.token_hex(32))
   ```

2. **Test locally with production settings**:
   ```bash
   export FLASK_ENV=production
   export SECRET_KEY=your-generated-key
   python app.py
   ```

### After Deployment
1. **Test all features**: Registration, login, trading, charts
2. **Monitor logs**: Check for any errors in production
3. **Set up custom domain** (optional): Most platforms support custom domains

### Security Considerations
- Never commit your production `.env` file
- Use strong, unique SECRET_KEY
- Monitor for unusual activity
- Consider implementing rate limiting
- Regular backups of user data

### Scaling Considerations
- Current setup uses JSON files for data storage
- For heavy usage, consider migrating to a proper database (PostgreSQL)
- Monitor memory usage as user data grows
- Consider implementing user data cleanup policies

## Troubleshooting

### Common Issues
1. **App won't start**: Check logs for missing environment variables
2. **WebSocket issues**: Ensure your platform supports WebSocket connections
3. **Static files not loading**: Check static file serving configuration
4. **Port binding errors**: Ensure you're using the PORT environment variable

### Getting Logs
- **Heroku**: `heroku logs --tail`
- **Railway**: Check the deployment logs in dashboard
- **Render**: Check logs in the service dashboard
- **DigitalOcean**: Check runtime logs in app dashboard