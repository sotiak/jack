{
  description = "Sotiak Mono font build environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";
    flake-utils.url = "github:numtide/flake-utils";
    treefmt-nix = {
      url = "github:numtide/treefmt-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    git-hooks = {
      url = "github:cachix/git-hooks.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    {
      nixpkgs,
      flake-utils,
      treefmt-nix,
      git-hooks,
      ...
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        python = pkgs.python314;
        fontName = "Sotiak Mono";
        fontStem = builtins.replaceStrings [ " " ] [ "" ] fontName;
        formatter =
          (treefmt-nix.lib.evalModule pkgs {
            projectRootFile = "flake.nix";
            programs.nixfmt.enable = true;
            settings.formatter.python = {
              command = "${pkgs.uv}/bin/uv";
              options = [
                "run"
                "--python"
                "${python}/bin/python3"
                "--locked"
                "ruff"
                "format"
              ];
              includes = [ "*.py" ];
            };
          }).config.build.wrapper;
        preCommit = git-hooks.lib.${system}.run {
          src = ./.;
          hooks = {
            format = {
              enable = true;
              name = "Format (Nix + Python)";
              entry = "${formatter}/bin/treefmt --fail-on-change";
              pass_filenames = false;
              always_run = true;
            };
            lint = {
              enable = true;
              name = "Lint (Ruff)";
              entry = "${pkgs.uv}/bin/uv run --python ${python}/bin/python3 --locked ruff check .";
              pass_filenames = false;
              always_run = true;
            };
            typecheck = {
              enable = true;
              name = "Type check (ty)";
              entry = "${pkgs.uv}/bin/uv run --python ${python}/bin/python3 --locked ty check";
              pass_filenames = false;
              always_run = true;
            };
          };
        };
      in
      {
        inherit formatter;

        apps = {
          capture-showcase = {
            type = "app";
            program = "${
              pkgs.writeShellApplication {
                name = "capture-showcase";
                excludeShellChecks = [ "SC2016" ];
                runtimeInputs = [
                  pkgs.charm-freeze
                  pkgs.librsvg
                  pkgs.fontconfig
                  pkgs.coreutils
                  pkgs.bash
                ];
                text = ''
                  [ -f dist/${fontStem}-Regular.ttf ] || {
                    echo "dist/${fontStem}-Regular.ttf not found; run uv run build first" >&2
                    exit 1
                  }
                  mkdir -p .github/images
                  work=$(mktemp -d)
                  trap 'rm -rf "$work"' EXIT

                  cat >"$work/fonts.conf" <<EOF
                  <?xml version="1.0"?>
                  <!DOCTYPE fontconfig SYSTEM "fonts.dtd">
                  <fontconfig>
                    <dir>$PWD/dist</dir>
                    <cachedir>$work/fonts</cachedir>
                  </fontconfig>
                  EOF
                  export FONTCONFIG_FILE="$work/fonts.conf"
                  fc-cache -f >/dev/null

                  freeze README.md --lines 1,18 --wrap 72 \
                    --font.family "${fontName}" --font.size 12 \
                    --theme github --background "#ffffff" --padding 16 \
                    -o .github/images/readme.png

                  freeze scripts/logo.txt \
                    --font.family "${fontName}" --font.size 22 \
                    --background "#ffffff" --padding 28 --theme github \
                    -o .github/images/logo.png
                '';
              }
            }/bin/capture-showcase";
          };
        };

        devShells.default = pkgs.mkShell {
          packages = [
            python
            pkgs.uv
            pkgs.pre-commit
            pkgs.nil
            pkgs.nixd
            pkgs.ttfautohint
          ];

          # Pillow's wheel uses zlib and loads libfribidi for Raqm text layout.
          # fontbakery's compiled checks need libstdc++.
          env = {
            UV_PYTHON = "${python}/bin/python3";
            UV_PYTHON_DOWNLOADS = "never";
            UV_PYTHON_PREFERENCE = "only-system";
            LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath [
              pkgs.zlib
              pkgs.fribidi
              pkgs.stdenv.cc.cc.lib
            ];
            DYLD_LIBRARY_PATH = pkgs.lib.makeLibraryPath [
              pkgs.zlib
              pkgs.fribidi
              pkgs.stdenv.cc.cc.lib
            ];
          };

          # nix develop strips SSL_CERT_FILE even when it is set in env.
          shellHook = ''
            # env cannot unset, and pre-commit injects its own PYTHONPATH.
            unset PYTHONPATH
            export SSL_CERT_FILE="${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt"
            ${preCommit.shellHook}
          '';
        };
      }
    );
}
