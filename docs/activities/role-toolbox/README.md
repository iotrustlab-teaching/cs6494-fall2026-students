# CPS Evidence Toolbox

Student-safe, browser-only practice for the October 19 HW3-to-CTF bridge. The
published `docs/` directory is served by GitHub Pages. No login, package
installation, or student code checkout is needed for this activity.

## Thirty-minute classroom run

1. **0-3 minutes:** Open the page and choose Network, Program, Operator, or
   Integrator. Each teammate may take one role; a three-person team can combine
   Operator and Integrator.
2. **3-13 minutes:** Use the self-contained fictional transfer-skid case. Network
   tests a policy against an unwanted write and an ordinary read. Program
   traces an authored ST path. Operator checks the age of displayed state.
   Integrator names the missing link between request and service.
3. **13-21 minutes:** Switch to the HW3 OpenPLC evidence path. This opens the
   existing personal workspace in a new tab; students use their own code,
   build, run, and saved evidence. The toolbox does not read or alter HW3.
4. **21-27 minutes:** Copy each role handoff to a teammate. Together, record a
   bounded claim and one discriminating next test.
5. **27-30 minutes:** Download notes if needed, then return to the official HW3
   assignment and submission instructions in Canvas.

The Rockwell path is displayed but disabled until a sanitized, rights-cleared,
non-builder-rehearsed read-only reference is approved. There is no direct
student Rockwell or CTF pilot access implied by this page.

## Evidence and privacy

- The transfer-skid packet, source, and process records are synthetic/authored.
  Its policy and freshness controls are local teaching calculations, not a
  deployed firewall or physical interlock.
- The HW3 path links to an existing compiled OpenPLC software simulation in
  SPHERE. The toolbox cannot observe its runtime and does not make claims
  about any particular student's run.
- Notes are saved only to this browser's local storage. Downloading notes is
  optional. Nothing on this page submits HW3 or a CTF answer.
- Do not paste access codes, passwords, personal identifiers, or protected
  facility records into notes. The published site is public.

## Verify

Run `scripts/role-toolbox-smoke.mjs` with Playwright and Chrome/Chromium
available. The script accepts the page URL as its argument; by default it tests
`http://127.0.0.1:8893/activities/role-toolbox/`. Set `PLAYWRIGHT_MODULE` to
an absolute Playwright module path and `CHROME_PATH` to a browser binary if
they are not installed in the usual locations. Run it against both a local
`docs/` server and the published Pages URL after deployment. It checks all
four roles, both evidence paths, policy/freshness/symbol tools, save/reload,
handoff validation, JSON export, and 320/390/768/1440-pixel layouts.

The Content Security Policy blocks network requests from this page; only a
deliberate click opens the separate HW3 tab. The intended CTF counterparts
shown in the interface are design targets, not released student tools.
