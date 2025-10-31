# Deployment Checklist

## Pre-deployment

- [ ] Update `SECRET_KEY` in `.env` with a secure random key
- [ ] Set `FLASK_ENV=production` in `.env`
- [ ] Set `FLASK_DEBUG=False` in `.env`
- [ ] Review and update `INITIAL_CASH` amount if needed
- [ ] Ensure `.env` file is in `.gitignore` (should already be included)
- [ ] Test application locally with production settings

## Security

- [ ] Change default secret key
- [ ] Review file permissions
- [ ] Consider implementing rate limiting
- [ ] Add input validation for all user inputs
- [ ] Use HTTPS in production
- [ ] Review error handling to avoid information disclosure

## Production Setup

- [ ] Use a proper WSGI server (gunicorn, uWSGI)
- [ ] Set up reverse proxy (nginx, Apache)
- [ ] Configure SSL/TLS certificates
- [ ] Set up database (PostgreSQL, MySQL) instead of JSON files
- [ ] Configure logging
- [ ] Set up monitoring and health checks
- [ ] Configure backup strategy for user data

## Environment Variables

Required in production `.env`:
```
SECRET_KEY=your-super-secure-secret-key-here
FLASK_ENV=production
FLASK_DEBUG=False
FLASK_PORT=5001
INITIAL_CASH=100000
```

## Database Migration (Recommended for Production)

Consider migrating from JSON files to a proper database:

1. Install database driver (psycopg2 for PostgreSQL, PyMySQL for MySQL)
2. Add database configuration to `config.py`
3. Create database models using SQLAlchemy
4. Implement migration scripts
5. Update data access functions

## Monitoring

Consider adding:
- Application performance monitoring (APM)
- Error tracking (Sentry, Rollbar)
- Logging aggregation
- Health check endpoints
- Metrics collection

## Backup Strategy

- Regular backups of user data
- Test restore procedures
- Consider real-time data replication
- Document recovery procedures