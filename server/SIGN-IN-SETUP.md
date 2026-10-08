# Optional email and SMS sign-in

Password sign-in continues to work. After deploying the new server, users with an enrolled Microsoft/Google/other TOTP authenticator can enable password-free authenticator sign-in in Profile and security → Manage sign-in methods. Enabling it requires their current password and a fresh authenticator or recovery code. Signing in uses their account email and a fresh six-digit authenticator code. This is an optional single-factor alternative; recovery-code sign-in still requires a password.

Email/SMS delivery is prepared but OFF by default. No provider credentials are included and no real messages were sent during testing.

## Activate later through GitHub

1. Set up a Twilio Verify service. Enable SMS for the countries you need. For email, connect a verified SendGrid sender and email template to that Verify service, following [Twilio's email setup](https://www.twilio.com/docs/verify/email).
2. In repository Settings → Secrets and variables → Actions, add secrets `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, and `TWILIO_VERIFY_SERVICE_SID`. Keep them in secrets, never in source files or release descriptions.
3. Add repository variables `SIGNIN_EMAIL` and `SIGNIN_SMS`, each exactly `true` or `false`. Enable only channels configured in your Verify service.
4. Run Actions → Deploy account and sync server. The workflow applies the additive `signin-migration.sql`, preserves the authenticator encryption key, saves optional delivery configuration and deploys the Worker. If all three Twilio secrets are absent, it skips delivery setup and preserves existing Worker settings.
5. Sign in with a password. Save your email/phone in Profile and security, then open Manage sign-in methods and verify the saved contact using its received code. Phone numbers must include the country code, for example +27821234567.
6. Sign out and choose Email code or SMS code. Enter your account email, choose Send code, then enter the received code. If 2FA is enabled, also enter a fresh authenticator or recovery code.

Use a test account and your own approved destinations to verify delivery before enabling it for everyone. Provider billing and sending limits are managed in Twilio. No provider account or subscription has been created for you.

## Behavior

- Codes are bound to an account, saved contact, purpose and ten-minute challenge. Contact enrollment is also bound to the signed-in session.
- Unverified profile details cannot be used for code sign-in. Changing a contact invalidates that contact's verification. Password changes clear optional sign-in enrollments, which must then be enabled again.
- Requests and guesses are rate-limited by IP and account. Only one check can consume a challenge. Expired codes, disabled accounts, revoked challenges and reused codes are rejected.
- Email/SMS sign-in does not bypass existing authenticator 2FA. Authenticator-only sign-in must be explicitly enabled per account and requires a TOTP code, not a recovery code.
- Disabling/replacing the authenticator also disables authenticator-only sign-in.
- To turn off delivery later, set the relevant repository variable to `false` and rerun the server workflow with the three secrets still present. Individual users can disable their code sign-in in Manage sign-in methods.

Integration references: [Start a verification](https://www.twilio.com/docs/verify/api/verification), [Check a verification](https://www.twilio.com/docs/verify/api/verification-check).
