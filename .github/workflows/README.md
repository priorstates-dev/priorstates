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

…then attaches them all to a GitHub Release with a `SHA256SUMS`.

**Installers ship unsigned by default** (no secrets required). To code-sign +
notarize, fill in the secrets named in the commented blocks of `release.yml`
(Apple Developer ID + App Store Connect key for macOS; an Authenticode cert —
e.g. free-for-OSS [SignPath](https://signpath.io) — for Windows). Nothing else
changes.

## `publish-downloads.yml` — manual mirror (optional)

Manually mirrors a release's installers to a self-hosted download area with
version-free aliases. Gated on deploy secrets (`DOWNLOADS_DEPLOY_KEY`,
`DOWNLOADS_HOST`); skips cleanly if unset. The normal tag-push release already
mirrors automatically (the `mirror-downloads` job in `release.yml`), so this is
only for re-publishing an older release.

## Cutting a release

```bash
# bump version, publish the wheel to PyPI, then:
git commit -am "release X.Y.Z" && git push
git tag vX.Y.Z && git push origin vX.Y.Z      # CI does the rest
```

The maintainer runbook (build hosts, signing, infra) lives outside this public
repo.
