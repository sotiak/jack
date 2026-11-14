# jack

Python 3.14 アプリケーションの開発環境です。Nix は Python ランタイムとシステム依存を、
uv は Python パッケージと開発ツールを管理します。

## 開発環境に入る

direnv と nix-direnv が導入済みであれば、プロジェクト直下で一度だけ次を実行します。

```bash
direnv allow
```

direnv を使わない場合は Nix の開発シェルに入ります。

```bash
nix develop
```

どちらの場合も、Python は Nix が提供する 3.14 系、`uv` は Nix の開発シェル内のものが使われます。
uv による Python 本体のダウンロードは無効化されています。

## 依存関係のインストール

```bash
uv sync
```

`pyproject.toml` と `uv.lock` に従って `.venv` が作成されます。`uv.lock` は Git 管理対象です。

## 開発コマンド

```bash
uv run ruff check .
uv run ruff format .
uv run ty check
uv run pytest
```

`uv run pytest` は `pytest-cov` によるカバレッジ表示付きで実行されます。

新規コードには型アノテーションを付けてください。ty は `pyproject.toml` の
`[tool.ty.environment]` で Python 3.14 を対象に型チェックします。

## 依存ライブラリの追加・更新

```bash
uv add <package>          # 実行時依存
uv add --dev <package>    # 開発時依存
uv lock                   # 依存関係の再解決
uv sync                   # ロックファイルに合わせて環境を更新
```

依存関係を変更したら `uv.lock` もコミットしてください。

## Nix と uv の責務分担

- **Nix**: Python 3.14、uv、およびシステムライブラリを提供します。Python パッケージは管理しません。
- **uv**: `pyproject.toml` / `uv.lock` に基づいて、実行時依存と開発ツール
  （Ruff、ty、pytest、pytest-cov）を `.venv` にインストールします。

Python のバージョンは `flake.nix`、`.python-version`、`pyproject.toml` の
`requires-python` で 3.14 系に揃えています。
