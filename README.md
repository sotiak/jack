# Back

The four TTFs in `dist/` are Regular, Italic, Bold, and Bold Italic. Install them and choose **Back** in your editor or terminal.

## Development

Nix provides Python 3.14, uv, and the system libraries. uv manages the Python packages.

```sh
direnv allow   # or: nix develop
uv sync
```

## Build and test

```sh
uv run jack                  # build dist/
uv run pytest                # tests
uv run ruff check .
uv run ruff format --check .
uv run ty check
```

`uv run jack` reads `config.toml`. If `assets/inputs/` is missing or out of date, it fetches the pinned inputs automatically. Run `uv run jack-fetch` to force a re-fetch.

## Inputs

`assets/sources.toml` pins:

- Hack 3.003 — GitHub release zip, SHA-256
- BIZ UD Gothic — npm `@fontsource/biz-udgothic` 5.3.0, npm SRI
- Nerd Fonts 3.3.0 — GitHub release `NerdFontsSymbolsOnly.zip`, SHA-256

Renovate updates these versions and digests. On `renovate/**` pull requests, CI rebuilds `dist/` and `output.sha256` after the tests pass. For a manual update:

```sh
rm -rf assets/inputs
uv run jack-fetch
uv run jack
```

To add a Python dependency, use `uv add` or `uv add --dev`, then commit `uv.lock`.

## Configuration

`config.toml` has the knobs: Japanese scale and stroke weight, italic angle, Nerd icons, slash-zero style, and the visible full-width space. The defaults are commented in the file.

## Layout

```text
src/jack/            build, fetch, italic, specimen
assets/sources.toml  pinned font inputs
assets/inputs/       downloaded fonts (ignored)
assets/licenses/     input font licenses
config.toml          build settings
dist/                generated fonts and previews
```

## License

The generated fonts are released under the SIL Open Font License 1.1. Hack-derived parts keep their original notices. When redistributing the fonts, include `dist/BIZ-OFL.txt`, `dist/Hack.txt`, and the `dist/nerd/` directory. See those files for the full terms.
