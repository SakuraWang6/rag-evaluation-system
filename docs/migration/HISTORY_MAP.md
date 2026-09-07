# Evaluation repository history map

The monorepo was assembled with non-squashed `git subtree` imports. Existing
component commit objects were not rewritten, so every old SHA maps to the same
SHA in this repository. Component refs are retained under
`refs/components/<component>/...`; public convenience tags use the component
prefix.

| Component | Original HEAD | Frozen dirty baseline commit | Imported ref |
|---|---|---|---|
| Platform | `c866b417ebb42b06257bf022c82dccec9654b14e` | `64ddfec2c15b0ec9cacab66f4a0fe21766f12571` | `refs/components/platform/heads/main` |
| Adapters | `0b47f8661036678e112a00f4dc14a22ba8b2a95c` | `ec007b5e033f2fc43ec2f8da5c6db2e16f590b72` | `refs/components/adapters/heads/main` |
| WebUI | `089e1232b36ab38a97a47a93d17db31088537a3f` | `be1504badc0e014bad33254d5a4db2bcfcd730ed` | `refs/components/webui/heads/main` |

Original tags are retained in namespaced refs and exposed as:

- `platform/v0.1.0`
- `platform/rag-eval-contract-1.0.0`
- `adapters/v0.1.0`
- `webui/v0.1.0`

Recovery bundles and their SHA-256 values are recorded outside the workspace
repository at:

`/Users/sakura/.codex/visualizations/2026/09/07/01a079b7-3cca-7322-ae76-effb64651877/rag-workspace-restructure-20260907`

| Bundle | SHA-256 |
|---|---|
| `lightrag.bundle` | `16dc934cd3d3d73d4bb6e645c4d785157366140fd30be1241b269ba811432187` |
| `platform.bundle` | `93433e32bbc3a7c52d40e845a08a6742733e1e8eaaba4e811a9a94ed3c600d99` |
| `adapters.bundle` | `de0ceeb7b2ad71ec710627d8482e6f3a7bc1375b2808cf73ba107377f610605d` |
| `webui.bundle` | `e8126c7e30051616f742d97f659a0cc252e25ea662f9de57461b3288098de054` |

