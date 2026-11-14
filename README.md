# Jack

Jack (Japanese Hack) is a programming font combining Hack and BIZ UD Gothic.

## Development

- Runtime, system library: Nix
- Python dependencies: uv

### Setup

```sh
direnv allow   # or: nix develop
uv sync
```

## Build and test

```sh
uv run build                 # build dist/
uv run pytest                # tests
nix fmt                      # format Nix and Python
pre-commit run --all-files    # format, lint, and type check
```

Entering the development shell automatically installs the hooks defined in `flake.nix`
with git-hooks.nix. The generated `.pre-commit-config.yaml` is ignored by Git.
Run commits inside the development shell. The hooks run the same formatter as `nix fmt`,
Ruff lint, and ty. If formatting changes files, stage those changes and commit again.
CI runs the same hooks.

`uv run build` reads `config.toml`. If `assets/inputs/` is missing or out of date, it fetches the pinned inputs automatically. Delete `assets/inputs/` to force a re-fetch.

## Font inputs and automation

`assets/sources.toml` pins the download versions and archive digests. The ignored
`assets/inputs/.lock` records the input configuration; extracted files are checked for
presence, not rehashed on every build. Renovate updates font and dependency pins, including
`flake.lock`. CI builds and tests the fonts without committing `dist/`.

`pyproject.toml` is the release version. Tag the commit `v<version>`; CI fails when the tag
and package version differ. The full version goes into the font name table (Unique ID and
Version). `head.fontRevision` encodes it as `major + minor/100 + patch/10000`
(for example, `1.10.2` becomes `1.1002`, rounded to 16.16 fixed-point).
Major must be 0–32767; minor and patch must each be 0–99, without leading zeros.
On a version tag, CI publishes the generated fonts and checksums as a release archive.

## Configuration

`config.toml` has the knobs: Japanese scale and stroke weight, italic angle, Nerd icons, slash-zero style, and the visible full-width space. The defaults are commented in the file.

## License

The generated fonts are released under the SIL Open Font License 1.1. Hack-derived parts keep their original notices. When redistributing the fonts, include `dist/BIZ-OFL.txt`, `dist/Hack.txt`, and the `dist/nerd/` directory. See those files for the full terms.
