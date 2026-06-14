# Release CI

Two workflows build and publish PriorStates' platform installers. They run on
GitHub-hosted runners (Linux, macOS, Windows) — free for this public repo.

## `release.yml` — the release

Trigger: push a tag `vX.Y.Z` (must equal `pyproject.toml`'s `version`), or run
manually from the Actions tab.

It builds every installer from the recipes in [`packaging/`](../../packaging):

| Runner | Artifact | Recipe |
|---|---|---|
| `ubuntu-latest` | `.deb`, `.rpm`, `.tar.gz` | `packaging/build.sh` |
| `macos-latest` | `.pkg` | `packaging/macos/build-pkg.sh` |
| `windows-latest` | `Setup.exe` | `packaging/windows/priorstates.iss` (Inno Setup) |

…then attaches them all to a GitHub Release with a `SHA256SUMS`, **plus
stable-named copies** (`PriorStates-Setup.exe`, `priorstates-latest.*`) so the
`releases/latest/download/<name>` URLs are version-free.

**Installers ship unsigned by default.** Both the Windows (**SignPath**) and
macOS (**Developer ID**) signing paths are wired and auto-skip until configured.

### Enable macOS signing (Developer ID Installer)

Needs an Apple Developer membership and a **Developer ID Installer** certificate.
The certificate is held in SignPath-style secrets and the cloud runner signs the
`.pkg`; you must supply the cert **with its private key** as a `.p12`.

1. On the Mac that has the cert + key in Keychain Access, select the
   *Developer ID Installer* certificate **and its private key**, right-click →
   **Export 2 items…** → save a password-protected `.p12`. (A `.cer` alone is the
   public certificate and cannot sign.)
2. Add to this repo:
   - secret **`APPLE_INSTALLER_CERT_P12_BASE64`** = `base64 -i cert.p12` (the whole file)
   - secret **`APPLE_CERT_PASSWORD`** = the `.p12` export password
   - variable **`APPLE_INSTALLER_IDENTITY`** = the exact identity, e.g.
     `Developer ID Installer: ZHENDONG QIN (LGT8FC5ZZZ)` (this turns the steps on)
3. Optional — **notarize** (clears Gatekeeper fully for downloaded pkgs). Using an
   Apple ID + app-specific password, add secrets **`APPLE_NOTARY_APPLE_ID`** (your
   Apple ID email) and **`APPLE_NOTARY_APP_PASSWORD`** (an app-specific password
   from appleid.apple.com), plus variables **`APPLE_TEAM_ID`** (e.g. `LGT8FC5ZZZ`)
   and **`APPLE_NOTARIZE`** = `true`.

The next tagged release then ships a signed (and, if enabled, notarized) `.pkg`.

### Enable Windows signing (SignPath, free for OSS)

### Enable Windows signing (SignPath, free for OSS)

SignPath's cloud HSM signs the built installer and returns it signed — the
certificate never touches CI. One-time setup:

1. Apply to **[SignPath Foundation](https://signpath.org)** (free OSS program;
   they review the project).
2. Install the **SignPath GitHub App** on this repo (used to verify the build's
   provenance — only artifacts from a trusted CI run get signed).
3. In SignPath, create a **project** and a **signing policy** (e.g. `priorstates`
   / `release-signing`).
4. Add to this repo:
   - secret **`SIGNPATH_API_TOKEN`**
   - variable **`SIGNPATH_ORGANIZATION_ID`** (this is what turns the steps on)
   - optional vars **`SIGNPATH_PROJECT_SLUG`** (default `priorstates`),
     **`SIGNPATH_SIGNING_POLICY_SLUG`** (default `release-signing`)

The next tagged release then ships a signed `Setup.exe` (Windows SmartScreen
stops warning once the cert gains reputation). Nothing else changes.

## Where downloads are served

GitHub Releases host the installers. The website keeps branded
`priorstates.com/download/...` URLs that **302-redirect** to
`releases/latest/download/<name>` (set once in nginx) — so there is **no mirror
step and no deploy key in CI**. The last `release.yml` step just curls those
branded URLs to confirm the new release is reachable.

## Cutting a release

```bash
# bump version, publish the wheel to PyPI, then:
git commit -am "release X.Y.Z" && git push
git tag vX.Y.Z && git push origin vX.Y.Z      # CI does the rest
```

The maintainer runbook (build hosts, signing, infra) lives outside this public
repo.
