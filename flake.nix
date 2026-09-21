# flake.nix
# THE LAPTOP AND CI TOOLCHAIN, TAKEN FROM toolchain.json.
#
# WHY NOT pkgs.uv / pkgs.bun / pkgs.gh: nixpkgs builds its own copies and
# tracks upstream on its own schedule (it has shipped uv 0.12.11 while this
# project pins 0.12.7). Exact parity needs the SAME upstream release on the
# laptop, GitHub Actions and Lightning AI alike, so this flake installs the
# official release artifacts named in
# toolchain.json, verified by the same sha256 the other machines check.
# Changing a version means editing toolchain.json only.
#
# Python is NOT from Nix: uv installs the CPython in .python-version, and an
# identical uv release downloads an identical CPython build on every machine.
# Linters, formatters, tests and git hooks live in uv.lock / bun.lock.
{
  description = "otsafety-gnn developer toolchain";

  inputs = {
    # Only for build helpers (fetchurl, unzip, autoPatchelfHook, mkShell);
    # no tool version comes from nixpkgs. flake.lock pins the revision.
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
  };

  outputs = { self, nixpkgs }:
    let
      systems = [ "aarch64-darwin" "x86_64-linux" ];
      toolchain = builtins.fromJSON (builtins.readFile ./toolchain.json);
      # FILTERED ON WHAT AN ENTRY IS, NOT ON WHAT IT IS CALLED. Every entry
      # carrying `artifacts` is a downloadable archive this flake builds. Adding
      # render_image -- a container pinned by digest, not an archive -- broke the
      # devShell for every task, because the old filter excluded one name and
      # assumed everything else was a binary. A blacklist would have to grow with
      # each new kind of pin; this does not.
      toolNames = builtins.filter
        (name: builtins.isAttrs toolchain.${name} && toolchain.${name} ? artifacts)
        (builtins.attrNames toolchain);
      forAllSystems = f:
        nixpkgs.lib.genAttrs systems
          (system: f system nixpkgs.legacyPackages.${system});

      # One derivation per tool: fetch the pinned official archive and install
      # its binaries unchanged (no stripping: macOS binaries are code-signed).
      # `binaries` are paths inside the archive's `dir` (gh keeps its binary in
      # bin/); each is installed under its file name.
      # On Linux, autoPatchelfHook points the binary at Nix's glibc loader,
      # the standard treatment for prebuilt binaries in Nix.
      upstreamBinary = system: pkgs: name:
        let
          tool = toolchain.${name};
          artifact = tool.artifacts.${system};
          isLinux = pkgs.stdenv.hostPlatform.isLinux;
        in
        pkgs.stdenvNoCC.mkDerivation {
          pname = name;
          inherit (tool) version;
          src = pkgs.fetchurl { inherit (artifact) url sha256; };
          sourceRoot = artifact.dir;
          nativeBuildInputs = [ pkgs.unzip ]
            ++ pkgs.lib.optionals isLinux [ pkgs.autoPatchelfHook ];
          buildInputs = pkgs.lib.optionals isLinux [ pkgs.stdenv.cc.cc.lib ];
          dontConfigure = true;
          dontBuild = true;
          dontStrip = true;
          installPhase = ''
            runHook preInstall
            ${pkgs.lib.concatMapStrings
              (b: "install -Dm755 ${b} $out/bin/${builtins.baseNameOf b}\n") tool.binaries}
            runHook postInstall
          '';
        };

      packagesFor = system: pkgs:
        nixpkgs.lib.genAttrs toolNames (upstreamBinary system pkgs);
    in
    {
      packages = forAllSystems packagesFor;

      devShells = forAllSystems (system: pkgs: {
        default = pkgs.mkShell {
          packages = builtins.attrValues (packagesFor system pkgs);
          shellHook = ''
            # uv must use its own managed CPython, never a Nix or Homebrew one.
            export UV_PYTHON_PREFERENCE=only-managed
          '';
        };
      });

      # `nix flake check` builds every tool AND runs it, asserting the version
      # it reports equals toolchain.json -- a wrong artifact fails here.
      checks = forAllSystems (system: pkgs:
        let tools = packagesFor system pkgs; in {
          toolchain-versions = pkgs.runCommand "toolchain-versions" { } ''
            uv_reported="$(${tools.uv}/bin/uv --version)"
            bun_reported="$(${tools.bun}/bin/bun --version)"
            gh_reported="$(${tools.gh}/bin/gh --version | head -1)"
            echo "uv:  $uv_reported"
            echo "bun: $bun_reported"
            echo "gh:  $gh_reported"
            case "$uv_reported" in
              "uv ${toolchain.uv.version} "*) ;;
              *) echo "uv version mismatch" >&2; exit 1 ;;
            esac
            [ "$bun_reported" = "${toolchain.bun.version}" ] \
              || { echo "bun version mismatch" >&2; exit 1; }
            case "$gh_reported" in
              "gh version ${toolchain.gh.version} "*) ;;
              *) echo "gh version mismatch" >&2; exit 1 ;;
            esac
            echo ok > $out
          '';
        });
    };
}
