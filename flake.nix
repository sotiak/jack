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
        # Not packaged in nixpkgs; wrap the upstream release binary.
        # Only the x86_64 Linux asset is handled here.
        fontspector =
          if system == "x86_64-linux" then
            pkgs.stdenvNoCC.mkDerivation (finalAttrs: {
              pname = "fontspector";
              version = "1.9.1";
              src = pkgs.fetchurl {
                url = "https://github.com/fonttools/fontspector/releases/download/fontspector-v${finalAttrs.version}/fontspector-${finalAttrs.version}-x86_64-unknown-linux-gnu.tar.gz";
                hash = "sha256-/5gr+/ue22DLNVEpZPuizGVg6UtJLPUD9dyXOcgXprU=";
              };
              nativeBuildInputs = [ pkgs.autoPatchelfHook ];
              buildInputs = [
                pkgs.zlib
                pkgs.openssl
                pkgs.stdenv.cc.cc.lib
              ];
              dontConfigure = true;
              dontBuild = true;
              installPhase = ''
                install -Dm755 fontspector $out/bin/fontspector
              '';
            })
          else
            null;
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
                runtimeInputs = [
                  pkgs.uv
                  pkgs.chromium
                ];
                text = ''
                  uv run site
                  uv run screenshots
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
            pkgs.chromium
          ]
          ++ pkgs.lib.optional (fontspector != null) fontspector;

          # Pillow's wheel uses zlib and loads libfribidi for Raqm text layout;
          # its AVIF support needs libstdc++.
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
