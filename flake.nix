{
  description = "Back font build environment";

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

        devShells.default = pkgs.mkShell {
          packages = [
            python
            pkgs.uv
            pkgs.pre-commit
            pkgs.nil
            pkgs.nixd
          ];

          # Pillow's wheel uses zlib and loads libfribidi for Raqm text layout.
          env = {
            UV_PYTHON = "${python}/bin/python3";
            UV_PYTHON_DOWNLOADS = "never";
            UV_PYTHON_PREFERENCE = "only-system";
            LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath [
              pkgs.zlib
              pkgs.fribidi
            ];
            DYLD_LIBRARY_PATH = pkgs.lib.makeLibraryPath [
              pkgs.zlib
              pkgs.fribidi
            ];
          };

          # Nix clears SSL_CERT_FILE, so restore a CA bundle for urllib.
          shellHook = ''
            # Keep pre-commit's Python dependencies out of the project's uv environment.
            unset PYTHONPATH
            export SSL_CERT_FILE="${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt"
            ${preCommit.shellHook}
          '';
        };
      }
    );
}
