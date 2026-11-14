{
  description = "Back font build environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs =
    { nixpkgs, flake-utils, ... }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        python = pkgs.python314;
      in
      {
        devShells.default = pkgs.mkShell {
          packages = [
            python
            pkgs.uv
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
            export SSL_CERT_FILE="${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt"
          '';
        };

        formatter = pkgs.nixfmt;
      }
    );
}
