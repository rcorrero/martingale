# reCAPTCHA Setup Guide

This guide explains how to set up Google reCAPTCHA for the Martingale application.

## What is reCAPTCHA?

reCAPTCHA is a free service from Google that protects your website from spam and abuse by distinguishing humans from bots. It helps prevent:
- Automated bot registrations
- Spam account creation
- Brute force attacks

## Implementation Details

The Martingale application uses **reCAPTCHA v2 (Checkbox)** with the following features:
- Dark theme to match the terminal UI
- Optional (can be disabled for development)
- Only required for registration (not login)
- SSL/TLS enabled by default

## Setup Instructions

### Step 1: Get reCAPTCHA Keys

1. **Visit the reCAPTCHA Admin Console**
   - Go to: https://www.google.com/recaptcha/admin
   - Sign in with your Google account

2. **Register a New Site**
   - Click the **+** button or "Register a new site"
   - Fill in the form:
     - **Label**: `Martingale` (or your preferred name)
     - **reCAPTCHA type**: Select **reCAPTCHA v2** → **"I'm not a robot" Checkbox**
     - **Domains**: Add your domains (one per line)
       - For development: `localhost` or `127.0.0.1`
       - For production: `yourdomain.com`
     - **Accept reCAPTCHA Terms of Service**
   - Click **Submit**

3. **Copy Your Keys**
   - After registration, you'll see two keys:
     - **Site Key**: Used in the frontend (visible in HTML)
     - **Secret Key**: Used in the backend (keep this private!)

### Step 2: Configure Environment Variables

1. **Update your `.env` file** (copy from `.env.example` if needed):
   ```bash
   # reCAPTCHA configuration
   RECAPTCHA_ENABLED=true
   RECAPTCHA_SITE_KEY=your_site_key_here
   RECAPTCHA_SECRET_KEY=your_secret_key_here
   ```

2. **Replace the placeholder values**:
   - `your_site_key_here` → Your actual Site Key
   - `your_secret_key_here` → Your actual Secret Key

### Step 3: Install Dependencies

If you haven't already installed the required package:

```bash
pip install flask-recaptcha
```

Or update from requirements.txt:

```bash
pip install -r requirements.txt
```

### Step 4: Test the Integration

1. **Start the application**:
   ```bash
   python app.py
   ```

2. **Navigate to registration page**:
   - Open browser: `http://localhost:5001/register`

3. **Verify reCAPTCHA appears**:
   - You should see the "I'm not a robot" checkbox
   - It should use the dark theme

4. **Test the verification**:
   - Try submitting without checking the box (should fail)
   - Check the box and submit (should succeed if other validations pass)

## Development vs Production

### Development Mode (RECAPTCHA_ENABLED=false)
- CAPTCHA is disabled for easier testing
- No need to set up reCAPTCHA keys
- Useful for local development

### Production Mode (RECAPTCHA_ENABLED=true)
- CAPTCHA is required for all registrations
- Must have valid reCAPTCHA keys configured
- Recommended for deployed applications

## Troubleshooting

### Issue: "ERROR for site owner: Invalid site key"
**Solution**: 
- Verify your Site Key is correct in `.env`
- Check that your domain is registered in reCAPTCHA admin
- For localhost, ensure you added `localhost` as a domain

### Issue: "Please complete the CAPTCHA verification" message keeps appearing
**Solution**:
- Check your Secret Key is correct in `.env`
- Verify your internet connection
- Check browser console for JavaScript errors
- Ensure reCAPTCHA script is loading (not blocked by ad blocker)

### Issue: CAPTCHA not appearing on page
**Solution**:
- Verify `RECAPTCHA_ENABLED=true` in `.env`
- Check that the reCAPTCHA script is loading in browser DevTools
- Clear browser cache
- Restart the Flask application

### Issue: "reCAPTCHA verification failed" in logs
**Solution**:
- The user didn't check the CAPTCHA box
- Network issue preventing verification
- Invalid Secret Key configuration

## Security Considerations

### Keep Secret Key Private
- ✅ Store in `.env` file (excluded from git)
- ✅ Use environment variables in production
- ❌ Never commit to source control
- ❌ Never expose in frontend code

### Site Key is Public
- The Site Key appears in HTML source
- This is expected and normal
- Only the Secret Key must be kept private

### Domain Configuration
- Only register domains you own
- Use specific domains in production (not wildcards)
- For testing, `localhost` and `127.0.0.1` are fine

## Advanced Configuration

### Using reCAPTCHA v3 (Score-based)
If you prefer invisible reCAPTCHA v3:

1. Register a new site with reCAPTCHA v3
2. Update `config.py`:
   ```python
   RECAPTCHA_V3 = True
   RECAPTCHA_SCORE_THRESHOLD = 0.5  # Adjust as needed
   ```

### Custom Theme
The default is dark theme. To use light theme, update `config.py`:
```python
RECAPTCHA_OPTIONS = {'theme': 'light'}
```

### Multiple Languages
reCAPTCHA automatically detects user language. To force a specific language:
```python
RECAPTCHA_LANGUAGE = 'en'  # or 'es', 'fr', etc.
```

## Testing reCAPTCHA

### Manual Testing
1. Try registering without solving CAPTCHA
2. Solve CAPTCHA and complete registration
3. Check server logs for verification messages

### Automated Testing
For CI/CD pipelines, disable CAPTCHA in test environment:
```bash
RECAPTCHA_ENABLED=false pytest
```

## Cost

Google reCAPTCHA is **free** for most use cases:
- Up to 1 million assessments per month
- No credit card required
- Enterprise version available for higher volume

## Additional Resources

- **Official Documentation**: https://developers.google.com/recaptcha
- **Admin Console**: https://www.google.com/recaptcha/admin
- **FAQ**: https://developers.google.com/recaptcha/docs/faq
- **Flask-ReCaptcha Docs**: https://github.com/mardix/flask-recaptcha

## Support

If you encounter issues with reCAPTCHA setup:
1. Check the troubleshooting section above
2. Review server logs for error messages
3. Test with browser DevTools console open
4. Verify environment variables are loaded correctly

---

**Last Updated**: 2025-10-31  
**Version**: 1.0
