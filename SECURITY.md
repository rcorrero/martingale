# Security Features

This document outlines the security measures implemented in the Martingale paper trading platform.

## Authentication & Authorization

### Password Security
- **Minimum Length**: 8 characters required
- **Complexity Requirements**: 
  - At least one uppercase letter (A-Z)
  - At least one lowercase letter (a-z)
  - At least one digit (0-9)
  - At least one special character (!@#$%^&*(),.?":{}|<>)
- **Hashing**: Passwords are hashed using Werkzeug's `generate_password_hash` (scrypt algorithm by default)
- **Storage**: Password hashes stored with 255-character field to accommodate algorithm changes

### Username Validation
- **Character Restrictions**: Only alphanumeric characters and underscores allowed
- **Length**: 3-20 characters
- **Reserved Names**: Common system names (admin, root, system, test, api, public, private) are blocked
- **Uniqueness**: Username uniqueness enforced at database level

### Rate Limiting
- **Login Attempts**: Maximum 5 failed login attempts per username
- **Time Window**: 5-minute lockout period after exceeding attempts
- **Reset**: Counter resets after successful login or window expiration
- **Protection**: Prevents brute-force password attacks

### CAPTCHA Protection
- **Implementation**: Google reCAPTCHA v2 (checkbox)
- **Registration**: Required when enabled via environment variable
- **Theme**: Dark theme to match terminal UI
- **Optional**: Can be disabled for development, enabled for production
- **Bot Prevention**: Prevents automated account creation

## Session Security

### Cookie Configuration
- **HttpOnly**: Session cookies cannot be accessed via JavaScript (XSS protection)
- **SameSite**: Set to 'Lax' for CSRF protection
- **Secure**: Enabled in production (HTTPS only)
- **Session Timeout**: 1 hour of inactivity before automatic logout

### CSRF Protection
- **Flask-WTF**: All forms protected with CSRF tokens
- **Token Validation**: Automatic validation on form submission
- **Time Limit**: Tokens valid for session duration (no separate expiry)

## Database Security

### SQL Injection Prevention
- **SQLAlchemy ORM**: All database queries use parameterized statements
- **Input Validation**: Username and password validators prevent malicious input
- **No Raw SQL**: Direct SQL execution avoided throughout application

### Password Storage
- **Never Plain Text**: Passwords never stored in plain text
- **One-Way Hashing**: Using scrypt (CPU and memory hard)
- **Salt**: Automatically salted by Werkzeug's hashing functions

## Input Validation

### Form Validation
- **WTForms Validators**: DataRequired, Length, EqualTo, Regexp
- **Custom Validators**: Password strength and username format checks
- **Server-Side**: All validation performed server-side (client-side is advisory only)

### Sanitization
- **Username**: Regex pattern matching prevents injection attacks
- **Symbols**: Trading symbols converted to uppercase and validated against allowed list
- **Quantities**: Converted to float with error handling

## Security Best Practices

### What's Implemented
✅ Strong password requirements  
✅ Password hashing with modern algorithm  
✅ Rate limiting on login  
✅ Session timeout  
✅ CSRF protection  
✅ SQL injection prevention  
✅ XSS protection (HttpOnly cookies)  
✅ Input validation and sanitization  
✅ Secure session configuration  
✅ CAPTCHA for registration (optional)  

### Future Enhancements (Optional)
- Email verification for new accounts
- Two-factor authentication (2FA)
- CAPTCHA for login (in addition to registration)
- Account lockout after repeated failures
- Audit logging for security events
- Password reset via email
- IP-based rate limiting
- Suspicious activity detection

## Production Deployment

### Environment Variables
Ensure the following are set in production:

```bash
SECRET_KEY=<strong-random-secret-key>
FLASK_ENV=production
DATABASE_URL=<postgresql-connection-string>

# Optional: Enable reCAPTCHA for bot protection
RECAPTCHA_ENABLED=true
RECAPTCHA_SITE_KEY=<your-recaptcha-site-key>
RECAPTCHA_SECRET_KEY=<your-recaptcha-secret-key>
```

### Getting reCAPTCHA Keys
1. Visit https://www.google.com/recaptcha/admin
2. Register a new site
3. Choose reCAPTCHA v2 (Checkbox)
4. Add your domain(s)
5. Copy the Site Key and Secret Key
6. Add to environment variables

### HTTPS Required
- Production configuration enforces `SESSION_COOKIE_SECURE=True`
- Deploy behind reverse proxy (nginx, Apache) with SSL/TLS
- Use Let's Encrypt or commercial certificate

### Database Hardening
- Use strong database passwords
- Restrict database access to application server only
- Enable connection encryption (SSL/TLS)
- Regular backups with encryption

## Security Incident Response

### If Compromised
1. **Immediate**: Revoke SECRET_KEY and regenerate
2. **Reset**: Force password reset for all affected users
3. **Investigate**: Check logs for unauthorized access
4. **Update**: Apply security patches immediately
5. **Notify**: Inform users if data was accessed

### Logging
- Failed login attempts logged with username
- Successful logins logged
- Rate limit triggers logged
- Registration events logged

## Reporting Security Issues

If you discover a security vulnerability, please email [your-email@example.com] with:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if known)

**Do not** create public GitHub issues for security vulnerabilities.

## Compliance

This application is designed for educational purposes (paper trading). If deploying for production use with real user data:

- Consider GDPR compliance (EU users)
- Implement data retention policies
- Add privacy policy and terms of service
- Ensure proper data encryption at rest
- Implement user data export/deletion features

## Security Testing

### Recommended Tools
- **OWASP ZAP**: Automated security scanner
- **Bandit**: Python security linter (included in CI)
- **SQLMap**: SQL injection testing
- **Burp Suite**: Manual penetration testing

### CI/CD Security
- GitHub Actions runs `bandit` security scanner on every commit
- Flake8 checks for code quality issues
- Dependencies should be regularly updated for security patches

---

**Last Updated**: 2025-01-XX  
**Version**: 1.0
