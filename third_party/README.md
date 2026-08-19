# third_party/

Landing area for **externally cloned repositories** that 3AGameFactory depends on
but does not vendor, for example:

- geometry and asset libraries such as `trimesh`
- engine-related material, shader, or asset-pack repositories
- third-party generation runtimes checked out from source

Clone each dependency into its own subdirectory:

```text
third_party/
├── trimesh/
├── <engine-material-repo>/
└── <runtime-repo>/
```

This folder is **git-ignored by default** except for this README. Every clone
keeps its own upstream licence; verify those terms before shipping generated
content.
