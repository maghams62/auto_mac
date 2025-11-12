# Redirect URL Configuration

This document explains how to use the redirect URL feature for OAuth callbacks and general redirects.

## Overview

The redirect URL system provides a centralized endpoint (`/redirect`) for handling:
- OAuth callbacks from external providers
- General redirects within the application
- Authentication flows

## Configuration

### Default Redirect URL

The default redirect URL is configured in `config.yaml`:

```yaml
oauth:
  redirect_base_url: "${REDIRECT_BASE_URL:-http://localhost:3000}"
  redirect_path: "/redirect"
  
ui:
  redirect_url: "${REDIRECT_URL:-http://localhost:3000/redirect}"
```

### Environment Variables

You can override the redirect URL using environment variables:

- `REDIRECT_BASE_URL`: Base URL for constructing redirect URLs (default: `http://localhost:3000`)
- `REDIRECT_URL`: Full redirect URL (default: `http://localhost:3000/redirect`)

## Usage

### Getting the Redirect URL

You can retrieve the configured redirect URL via the API:

```bash
curl http://localhost:8000/api/auth/redirect-url
```

Response:
```json
{
  "redirect_url": "http://localhost:3000/redirect",
  "base_url": "http://localhost:3000",
  "path": "/redirect"
}
```

### OAuth Callback Flow

1. **Configure OAuth Provider**: Use the redirect URL when setting up OAuth providers:
   ```
   http://localhost:3000/redirect
   ```

2. **OAuth Provider Redirects**: After user authorization, the provider redirects to:
   ```
   http://localhost:3000/redirect?code=AUTHORIZATION_CODE&state=STATE_VALUE
   ```

3. **Backend Processing**: The frontend automatically sends the code to `/api/auth/callback` for processing.

4. **Completion**: User is redirected to the home page or a specified destination.

### Simple Redirects

You can also use the redirect page for simple redirects:

```
http://localhost:3000/redirect?to=/profile
```

**Security**: Only redirects to the same origin or relative paths are allowed to prevent open redirect vulnerabilities.

## API Endpoints

### POST `/api/auth/callback`

Processes OAuth callbacks with authorization codes.

**Request Body:**
```json
{
  "code": "authorization_code",
  "state": "optional_state_value",
  "redirect_uri": "http://localhost:3000/redirect"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Authentication successful. Redirecting...",
  "redirect_to": "/"
}
```

### GET `/api/auth/redirect-url`

Returns the configured redirect URL for OAuth provider configuration.

**Response:**
```json
{
  "redirect_url": "http://localhost:3000/redirect",
  "base_url": "http://localhost:3000",
  "path": "/redirect"
}
```

## Implementation Notes

### Frontend (`/app/redirect/page.tsx`)

- Handles OAuth callbacks with `code` parameter
- Processes OAuth errors
- Supports simple redirects with `to` parameter
- Validates redirect destinations for security

### Backend (`/api/auth/callback`)

- Currently provides a placeholder implementation
- TODO: Implement actual OAuth token exchange based on provider
- TODO: Store tokens securely
- TODO: Validate state parameter for CSRF protection

## Production Deployment

When deploying to production:

1. Update `config.yaml` with your production domain:
   ```yaml
   oauth:
     redirect_base_url: "https://yourdomain.com"
   ```

2. Add your production domain to allowed redirect domains:
   ```yaml
   oauth:
     allowed_redirect_domains:
       - "yourdomain.com"
   ```

3. Set environment variables:
   ```bash
   export REDIRECT_BASE_URL="https://yourdomain.com"
   export REDIRECT_URL="https://yourdomain.com/redirect"
   ```

## Security Considerations

- Redirect URLs are validated to prevent open redirect attacks
- Only same-origin redirects or relative paths are allowed
- OAuth state parameter should be validated for CSRF protection (TODO)
- Tokens should be stored securely (TODO)

## Examples

### Google OAuth Setup

1. In Google Cloud Console, add redirect URI:
   ```
   http://localhost:3000/redirect
   ```

2. When initiating OAuth flow, redirect to:
   ```
   https://accounts.google.com/o/oauth2/v2/auth?
     client_id=YOUR_CLIENT_ID&
     redirect_uri=http://localhost:3000/redirect&
     response_type=code&
     scope=email profile&
     state=RANDOM_STATE
   ```

3. Google redirects back to `/redirect` with code, which is automatically processed.

### Discord OAuth Setup

Similar to Google, use:
```
https://discord.com/api/oauth2/authorize?
  client_id=YOUR_CLIENT_ID&
  redirect_uri=http://localhost:3000/redirect&
  response_type=code&
  scope=identify email&
  state=RANDOM_STATE
```

### Spotify API Setup

1. **In Spotify Developer Dashboard** (https://developer.spotify.com/dashboard):
   - Create a new app or select an existing one
   - Go to "Edit Settings"
   - Under "Redirect URIs", add:
     ```
     http://127.0.0.1:3000/redirect
     ```
     **Important**: Spotify requires loopback IP (`127.0.0.1`) for HTTP redirects, not `localhost`. This is required for security compliance.
   - Save your changes

2. **Get your credentials**:
   - Client ID: Found on your app's dashboard page
   - Client Secret: Click "Show Client Secret" on your app's dashboard page

3. **Set environment variables**:
   ```bash
   export SPOTIFY_CLIENT_ID="your_client_id_here"
   export SPOTIFY_CLIENT_SECRET="your_client_secret_here"
   export SPOTIFY_REDIRECT_URI="http://127.0.0.1:3000/redirect"  # Optional, uses default if not set
   ```

4. **When initiating Spotify OAuth flow**, redirect to:
   ```
   https://accounts.spotify.com/authorize?
     client_id=YOUR_CLIENT_ID&
     redirect_uri=http://127.0.0.1:3000/redirect&
     response_type=code&
     scope=user-read-playback-state user-modify-playback-state user-read-currently-playing streaming user-read-email user-read-private&
     state=RANDOM_STATE
   ```

5. **Spotify redirects back** to `/redirect` with code, which is automatically processed.

**Note**: The redirect URI in your Spotify app settings must **exactly match** the one you use in the authorization URL (including `http://` vs `https://` and port numbers).

