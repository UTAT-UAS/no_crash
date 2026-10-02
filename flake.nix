{
  description = "Host tools for the no_crash development containers";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";

  outputs = { nixpkgs, ... }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs { inherit system; };
      # Use the existing host daemon; include Compose and Buildx in the CLI.
      docker = pkgs.docker-client;
    in
    {
      devShells.${system}.default = pkgs.mkShellNoCC {
        packages = [
          pkgs.bashInteractive
          pkgs.git
          pkgs.python3
          docker
          (pkgs.devcontainer.override { inherit docker; })
          pkgs.shellcheck
          pkgs.hadolint
          pkgs.uv
        ];
      };
    };
}
