# CS 6494 SPHERE account setup

Course staff will create your SPHERE class account from a verified email
address and add the activated account to the course project. You may see an
empty course project before access is enabled; that is normal. HW2 compute is
not preassigned: after access is enabled, you create and release your own fixed
course environment with the provided wrapper.

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

`mrg` is the command-line client for SPHERE's underlying Merge testbed
services. It verifies your account and is also used by the released HW2
lifecycle wrapper to create and release your own fixed course environment.
The login commands below do **not** allocate compute by themselves.

Before using the commands below:

1. Download the correct binary for your operating system and CPU from the
   [latest official `mrg` release](https://gitlab.com/mergetb/portal/cli/-/releases/permalink/latest).
2. Make the binary executable and place it somewhere on your `PATH` as `mrg`.
3. Confirm the installation with `mrg --version`. The official
   [Merge account setup](https://mergetb.org/docs/experimentation/getting-started/)
   and [`mrg` CLI reference](https://mergetb.org/docs/experimentation/cli-reference/)
   provide platform-independent background and command documentation.

After staff announces account approval, configure the client and log in:

```bash
mrg config set server grpc.sphere-testbed.net
mrg login <YOUR_SPHERE_USERNAME>
mrg whoami
```

Successful `mrg whoami` is the account checkpoint. HW2 is an individual
assignment: after course project access is enabled, you will use the fixed
[`hw2-sphere` lifecycle wrapper](../labs/cps-tank/hw2/sphere/README.md) to
create, enter, and release your own isolated allocation. Do not create or attach
resources manually outside that wrapper.

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
- **No `cs6494hw2` project is listed:** your account is not yet active in the
  course project; report your SPHERE username to staff.
