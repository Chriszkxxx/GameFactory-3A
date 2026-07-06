# serving/

Engine-side reference code — **fed to the LLM as context** when generating
mechanic / UI code, and used at runtime for RPC-style asset delivery.

## Sub-directories

| Directory   | Contents                                                   |
|-------------|------------------------------------------------------------|
| `ue5/`      | UE5 Blueprint templates, C++ modules, Python-remote scripts, importer helpers |
| `unity3d/`  | Unity3D C# templates, Editor scripts, PackageManager manifests |
| `common/`   | Engine-agnostic protocols: RPC schemas, asset manifests, event JSON schemas |

The LLM is expected to *reference / extend* these files rather than write engine
code from scratch, which improves compile-rate and reduces hallucinated APIs.
