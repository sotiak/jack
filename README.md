# Sotiak Mono

Sotiak Monoは、IosevkaをベースにBIZ UDゴシックを組み合わせた、Nerd Fonts対応のプログラミング用フォントです。

<picture>
  <source media="(prefers-color-scheme: dark)" srcset=".github/images/specimen-hero-dark.png">
  <img src=".github/images/specimen-hero-light.png" alt="Sotiak Monoの和文・欧文の見本" width="880">
</picture>

## Showcase

[書体見本サイト](https://sotiak.github.io/mono/) / [PDF（A4・4ページ）](https://sotiak.github.io/mono/specimen.pdf) / [HTMLソース](site/index.html)。Iosevka SS03との比較、字形の設計、代表文字を掲載しています。

[Texture Healingデモ](https://sotiak.github.io/mono/#texture)では、`calt` の分割比較、差分オーバーレイ、テキスト入力、スイープを操作できます。

<picture>
  <source media="(prefers-color-scheme: dark)" srcset=".github/images/specimen-weights-dark.png">
  <img src=".github/images/specimen-weights-light.png" alt="4スタイルと半角1対全角2のグリッド" width="880">
</picture>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset=".github/images/specimen-design-dark.png">
  <img src=".github/images/specimen-design-light.png" alt="r・g・j・W/w・t・Mの輪郭と設計" width="880">
</picture>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset=".github/images/specimen-features-dark.png">
  <img src=".github/images/specimen-features-light.png" alt="calt・ss01・ss19・ss20とTexture Healingの有効・無効比較" width="880">
</picture>

## Development

- Runtime, system library: Nix
- Python dependencies: uv

### Setup

```sh
direnv allow   # or run; nix develop
uv sync
```

### Build / Test

```sh
uv run build
uv run pytest
uv run fontbakery check-universal --skip-network --no-progress --configuration fontbakery.toml -j dist/SotiakMono-*.ttf
```

### Build configuration

`config.toml`でフォントビルド時のパラメータを設定できます。

### Release publishing

`pyproject.toml`で`project.version`を繰り上げてタグをpushします。 

## ライセンス

SIL Open Font License 1.1。Iosevka、BIZ UDゴシック、Nerd Fonts、0xProtoの帰属表示は[assets/licenses](assets/licenses)にあります。
