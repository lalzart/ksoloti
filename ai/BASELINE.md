# Development baseline

- Development fork (`origin`): `https://github.com/lalzart/ksoloti.git`
- Baseline authority (`upstream`): `https://github.com/ksoloti/ksoloti.git`
- Upstream tag: `1.1.0`
- Starting commit: `6dd3e7df756bcafe6958ae50b811cb605b4ccd27`
- Development branch: `codex/ai-native-authoring`
- Compatibility target: Ksoloti Patcher and firmware 1.1.0

Work belongs on the personal fork; the official repository remains the
read-only baseline authority. Its tag and commit are authoritative, so a
similarly named tag in the fork must not silently replace the baseline. Object
libraries are indexed as external inputs and receive deterministic content
fingerprints in the generated catalog.
