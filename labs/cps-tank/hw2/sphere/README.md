# Self-service SPHERE lifecycle

HW2 is an individual assignment. Every student creates an isolated copy of the
same fixed course topology: one OpenPLC controller node and one process/evidence
node on a private experiment link. Course staff pin the model and provisioning
payload; students control when their own eight-hour allocation starts and when
it is released.

## Local prerequisites

Install and authenticate the `mrg` CLI as described in the
[course SPHERE account setup](../../../quickstart/sphere-account-setup.md).
The lifecycle wrapper also requires `python3`, `ssh-keygen`, and `expect` on
your workstation. Windows users should run it from the course-supported WSL
environment.

## Create your environment

From this HW2 directory on your workstation:

```bash
./sphere/hw2-sphere create
```

The command derives a unique name from `mrg whoami`, creates an eight-hour
realization from the pinned course model, creates a personal XDC, attaches it,
and installs the released course payload. It accepts no host, address, program,
topology, or attack parameters. Re-running `create` safely resumes your own
fixed environment if setup was interrupted.

## Enter the process node

```bash
./sphere/hw2-sphere status
./sphere/hw2-sphere connect
```

After `connect`, you are on the process node. Continue with:

```bash
hw2-prepare
cd ~/cs6494-hw2/hw2
./preflight.sh --require-sphere
```

## Release resources

Download your evidence first. Then leave the process-node shell and run on your
workstation:

```bash
./sphere/hw2-sphere release
```

The wrapper only releases the realization and XDC derived from your authenticated
SPHERE username. Allocations also expire automatically after eight hours, but
release yours as soon as you finish so resources remain available to classmates.

## Boundaries

- Use only the resource names produced by the wrapper.
- Do not attach your XDC to another student's realization.
- Do not change the pinned model revision or shared provisioning payload.
- If creation reports exhausted capacity, release any stale allocation and try
  later; report a repeated failure to course staff.
- A new allocation is a fresh environment. Evidence is not preserved unless you
  download it before releasing or expiry.
