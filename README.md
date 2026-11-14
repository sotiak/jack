# Back

Hack + BIZ UDゴシック font.

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
uv run ruff check .
uv run ruff format --check .
uv run ty check
```

`uv run build` reads `config.toml`. If `assets/inputs/` is missing or out of date, it fetches the pinned inputs automatically. Delete `assets/inputs/` to force a re-fetch.

## Font inputs and automation

`assets/sources.toml` pins the download versions and archive digests. The ignored
`assets/inputs/.lock` records the input configuration; extracted files are checked for
presence, not rehashed on every build. Renovate updates font and dependency pins, including
`flake.lock`. CI builds and tests the fonts without committing `dist/`. On a version tag,
it publishes the generated fonts and checksums as a release archive.

## Configuration

`config.toml` has the knobs: Japanese scale and stroke weight, italic angle, Nerd icons, slash-zero style, and the visible full-width space. The defaults are commented in the file.

## License

The generated fonts are released under the SIL Open Font License 1.1. Hack-derived parts keep their original notices. When redistributing the fonts, include `dist/BIZ-OFL.txt`, `dist/Hack.txt`, and the `dist/nerd/` directory. See those files for the full terms.
