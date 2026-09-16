# OpenPLC v3 runtime

The prepared SPHERE environment runs the baseline program in a generic OpenPLC
v3 container. The course program is mounted at runtime; it is not baked into
the image.

```text
ghcr.io/iotrustlab-teaching/openplc-v3:b5d41356
```

For reproducible deployment, use the immutable reference:

```text
ghcr.io/iotrustlab-teaching/openplc-v3@sha256:ba613b4b00a3561e0acc0caf884c2187d5c008023625989b89c6006d4af3aaf1
```

The image contains upstream OpenPLC v3 commit
`b5d41356dab4aeadca0dd7ca64ba542f870b595d`, targets `linux/amd64`, and is
licensed under GPL-3.0-only. Its OCI source metadata points to the
[upstream OpenPLC v3 repository](https://github.com/thiagoralves/OpenPLC_v3).

The student-visible controller source is
[`representations/controller.st`](representations/controller.st). SPHERE
deployment, course identity, packet capture, and evidence collection are
separate from the generic runtime image.
