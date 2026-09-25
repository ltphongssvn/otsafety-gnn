# flake.nix
# 4.2: proves this step of the plan.
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
          # A BARE BINARY is installed as downloaded; an archive unpacks into its dir.
          isBinary = (artifact.kind or "archive") == "binary";
          pinNotice = ''
            message = "${name} is pinned by toolchain.json in this repository; change its version there."
          '';
        in
        pkgs.stdenvNoCC.mkDerivation ({
          pname = name;
          inherit (tool) version;
          src = pkgs.fetchurl { inherit (artifact) url sha256; };
          nativeBuildInputs = [ pkgs.unzip ]
            ++ pkgs.lib.optionals isLinux [ pkgs.autoPatchelfHook ];
          buildInputs = pkgs.lib.optionals isLinux [ pkgs.stdenv.cc.cc.lib ];
          dontConfigure = true;
          dontBuild = true;
          dontStrip = true;
          # A PIN NOTICE, where the tool reads one: mise's self-update then refuses.
          postInstall = pkgs.lib.optionalString (tool ? self_update_notice) ''
            install -Dm644 ${pkgs.writeText "${name}-pin-notice" pinNotice} $out/${tool.self_update_notice}
          '';
          installPhase = if isBinary then ''
            runHook preInstall
            install -Dm755 $src $out/bin/${builtins.head tool.binaries}
            runHook postInstall
          '' else ''
            runHook preInstall
            ${pkgs.lib.concatMapStrings
              (b: "install -Dm755 ${b} $out/bin/${builtins.baseNameOf b}\n") tool.binaries}
            runHook postInstall
          '';
        } // (if isBinary then { dontUnpack = true; } else { sourceRoot = artifact.dir; }));

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
          # GENERATED FROM EACH TOOL'S PROBE in toolchain.json, the same data
          # toolchain:verify reads at run time, so the two checks cannot diverge.
          toolchain-versions = pkgs.runCommand "toolchain-versions" { } ''
            export HOME="$TMPDIR"
            ${pkgs.lib.concatMapStrings (name:
              let
                tool = toolchain.${name};
                bin = builtins.baseNameOf (builtins.head tool.binaries);
                escaped = builtins.replaceStrings [ "." ] [ "\\." ] tool.version;
                pattern = builtins.replaceStrings [ "{version}" ] [ escaped ] tool.probe.pattern;
              in ''
                reported="$(${tools.${name}}/bin/${bin} ${pkgs.lib.escapeShellArgs tool.probe.args} 2>/dev/null | head -1)"
                echo "${name}: $reported"
                printf '%s\n' "$reported" | grep -Eq ${pkgs.lib.escapeShellArg pattern} \
                  || { echo "${name} does not report ${tool.version}" >&2; exit 1; }
              '') toolNames}
            # PROVED, NOT ASSUMED: mise's self-update must refuse beside its pin notice.
            refusal="$(${tools.mise}/bin/mise self-update --yes 2>&1 || true)"
            case "$refusal" in *"cannot update"*) ;; *) echo "mise self-update is not disabled: $refusal" >&2; exit 1 ;; esac
            echo ok > $out
          '';
        });
    };
}
