let
  flake = builtins.getFlake (toString ./.);
  nixpkgs = import <nixpkgs> {};
in
  {inherit flake;}
  // flake
  // builtins
  // nixpkgs
  // nixpkgs.lib
