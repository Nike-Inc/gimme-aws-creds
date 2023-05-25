{
  description = "Gimme AWS Creds";
  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    mach-nix.url = "github:davhau/mach-nix";
    flake-utils.url = "github:numtide/flake-utils";
    flake-compat.url = "github:edolstra/flake-compat";
    flake-compat.flake = false;
  };

  outputs = {
    self,
    nixpkgs,
    flake-utils,
    mach-nix,
    ...
  } @ inputs: let
    pythonVersion = "python310";
    packageName = "gimme-aws-creds";
  in
    flake-utils.lib.eachDefaultSystem
    (
      system: let
        pkgs = nixpkgs.legacyPackages.${system};
        mach = mach-nix.lib.${system};
        pythonApp = mach.buildPythonPackage {
          pname = packageName;
          src = ./.;
          python = pythonVersion;
          requirements = builtins.readFile ./requirements.txt;
          #version =; gets automatically detected
        };
        pythonAppEnv = mach.mkPython {
          python = pythonVersion;
          requirements = builtins.readFile ./requirements.txt;
        };
      in rec {
        # nix build '.#gimme-aws-creds'
        packages.${packageName} = pythonApp;

        legacyPackages = self.packages.${system}.${packageName};
        defaultPackage = self.packages.${system}.${packageName};

        # nix run '.#default'
        defaultApp = flake-utils.lib.mkApp {
          drv = packages.${packageName};
          exePath = "/bin/${packageName}";
        };

        devShells.default = pkgs.mkShellNoCC {
          packages = [pythonAppEnv defaultPackage];
          shellHook = ''
            export PYTHONPATH="${pythonAppEnv}/bin/python"
          '';
        };
      }
    );
}
