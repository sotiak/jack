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
uv run jack                  # build dist/
uv run pytest                # tests
uv run ruff check .
uv run ruff format --check .
uv run ty check
```

`uv run jack` reads `config.toml`. If `assets/inputs/` is missing or out of date, it fetches the pinned inputs automatically. Run `uv run jack-fetch` to force a re-fetch.

## Configuration

`config.toml` has the knobs: Japanese scale and stroke weight, italic angle, Nerd icons, slash-zero style, and the visible full-width space. The defaults are commented in the file.

## License

The generated fonts are released under the SIL Open Font License 1.1. Hack-derived parts keep their original notices. When redistributing the fonts, include `dist/BIZ-OFL.txt`, `dist/Hack.txt`, and the `dist/nerd/` directory. See those files for the full terms.
