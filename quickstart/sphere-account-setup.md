# CS 6494 SPHERE account setup

> **DRAFT — publish only after the `cs6494` organization is active and one
> student-shaped test succeeds.**

Course staff will create your SPHERE class account from a verified email
address. Compute and experiment access may be added later. You may see an empty
course project before resources are assigned; that is normal.

## Activate your class account

1. Watch the verified email account you supplied to course staff for a SPHERE
   verification message. Check spam/quarantine if it does not arrive.
2. Open the verification link once and set your own strong password.
3. Save the SPHERE username shown in the message or account page. It may be a
   generated course username and may not equal your Utah UID.
4. Sign in at <https://launch.sphere-testbed.net> with that SPHERE username and
   password. **Do not choose CILogon for this class account.**
5. Report only your SPHERE username through the private course check-in. Never
   send course staff your password.

## Verify activation

After staff announces approval, configure the CLI and log in:

```bash
mrg config set server grpc.sphere-testbed.net
mrg login <YOUR_SPHERE_USERNAME>
mrg whoami
```

Successful `mrg whoami` is the account checkpoint. Whether an empty course
project is already visible depends on the current Class UI workflow; compute is
not expected yet.

If you do not know the password, use Launch account recovery for the exact email
address course staff registered. Do not create another account.

## Problems

- **Verification email missing:** check spam/quarantine, then privately report
  the address used; do not register yourself again.
- **Verification link reports a missing property or username:** capture the exact
  message and send it to course staff; this failure has occurred in Class UI.
- **CILogon returns you to registration or cannot find the account:** switch to
  password login or account recovery. Current class accounts are not linkable to
  CILogon through Launch.
- **Login fails:** do not re-register. Approval or email verification may still
  be pending; report your generated SPHERE username.
- **Launch is empty or access is denied:** the account is likely pending or
  frozen; report your username and the exact message.
- **No course project is listed:** acceptable during account onboarding; staff
  will announce when project-backed compute is ready.
