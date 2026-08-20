# Keycloak & Windows Active Directory Integration Plan

## Goal
Enable Enterprise Single Sign-On (SSO) and User Authentication for **Meeting Transcribe** by connecting **Keycloak** to **Windows Active Directory (AD DS)** over LDAPS (port 636) and securing the FastAPI backend with OpenID Connect (OIDC) JWT tokens.

> [!NOTE]
> This plan is saved for future implementation. Do not execute immediately.

---

## 1. Keycloak On-Premise Setup (Docker)

1. Deploy Keycloak 24+ container locally / on-premise:
   ```bash
   docker run -d --name keycloak \
     -p 8080:8080 \
     -e KEYCLOAK_ADMIN=admin \
     -e KEYCLOAK_ADMIN_PASSWORD=admin_password \
     quay.io/keycloak/keycloak:24.0.0 start-dev
   ```
2. **Create Realm**: `meeting-transcribe-realm`
3. **Create Client**: `meeting-transcribe-app`
   - Access Type: `public` (Standard OIDC + PKCE for Web Single Page Apps)
   - Valid Redirect URIs: `http://localhost:8000/*`
   - Web Origins: `http://localhost:8000`

---

## 2. Active Directory LDAPS User Federation

1. In Keycloak Admin Console ➔ **User Federation** ➔ Add **ldap**:
   - **Vendor**: Active Directory
   - **Connection URL**: `ldaps://ad.company.local:636`
   - **Users DN**: `OU=Users,DC=company,DC=local`
   - **Bind DN**: `CN=KeycloakServiceAccount,OU=ServiceAccounts,DC=company,DC=local`
   - **Bind Credential**: `<ServiceAccountPassword>`
   - **Edit Mode**: READ_ONLY
   - **Sync Registrations**: OFF
   - **Truststore**: Path to corporate Root CA certificate.
2. **Group Mappers**:
   - Map Windows AD groups (e.g. `CN=MeetingTranscribeUsers`) to Keycloak client roles.
3. **Optional Windows Desktop Single Sign-On (Kerberos / SPNEGO)**:
   - Configure **Kerberos Realm**: `COMPANY.LOCAL`
   - Attach Kerberos keytab file to Keycloak so domain-joined Windows PCs log in without typing passwords.

---

## 3. Backend FastAPI Integration (`backend/auth.py`)

1. Install `python-jose` and `httpx` in virtual environment.
2. Implement OIDC Bearer token verification middleware in `backend/auth.py`:
   - Fetch Keycloak JWKS (JSON Web Key Set) from `http://keycloak:8080/realms/meeting-transcribe-realm/protocol/openid-connect/certs`.
   - Verify JWT signatures, token expiration, issuer, and client audience.
   - Inject `current_user` (`preferred_username`, `email`, `roles`) into API route dependencies (`Depends(get_current_user)`).

---

## 4. Frontend OIDC Integration (`frontend/js/auth.js`)

1. Include `keycloak.js` client adapter in `frontend/index.html`.
2. Initialize Keycloak authentication check before mounting app:
   ```javascript
   const keycloak = new Keycloak({
       url: 'http://localhost:8080',
       realm: 'meeting-transcribe-realm',
       clientId: 'meeting-transcribe-app'
   });

   keycloak.init({ onLoad: 'login-required', pkceMethod: 'S256' }).then(authenticated => {
       if (authenticated) {
           window.authToken = keycloak.token;
           // Automatically refresh token before expiration
           setInterval(() => keycloak.updateToken(70), 60000);
       }
   });
   ```
3. Pass `Authorization: Bearer ${window.authToken}` header on all API fetch requests.

---

## 5. Verification & Testing Plan

1. Verify Keycloak syncs Active Directory domain users and groups.
2. Test user login on `http://localhost:8000` with standard Windows AD credentials.
3. Test unauthenticated request rejection (`HTTP 401 Unauthorized`).
4. Test token auto-refresh before expiry.
