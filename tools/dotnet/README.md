# Off-Unity build and checks (.NET 8)

Lets CI (or anyone without a Unity licence) run the NERAM core tests, compile-check the Unity scripts and check the
generated scene bundle. None of this proves that the project imports, compiles or renders in Unity 6000.3; opening the
project in the Editor is the real check.

```bash
export NEWTONSOFT_DLL=/path/to/Newtonsoft.Json.dll        # 13.x
export NUNIT_DLL=/path/to/nunit.framework.dll             # 2.6.x or 3.x
export NERAM_REPO_ROOT=$(pwd)/../..                       # workspace root (contains config/ and integration/)
cd tools/dotnet
dotnet build Tests/Neram.Tests.csproj -c Release && dotnet Tests/bin/Release/net8.0/Neram.Tests.dll   # 75 pass, 1 ignored
dotnet build UnityCheck/UnityCheck.csproj -c Release                                                  # compile-check vs stubs
dotnet run --project BundleCheck -c Release -- "$NERAM_REPO_ROOT"                                     # generated bundle
```
`nuget.config` clears package sources (offline build); point the two variables at local DLLs.

* **Core**: `unity_editor/Assets/Scripts/Core/*.cs` (no UnityEngine), built for netstandard2.1, C# 9 (Unity's language level), warnings as errors.
* **Tests**: the same `unity_editor/Assets/Tests/EditMode/*.cs` files Unity's Test Runner uses, run by a small reflection runner (`Runner.cs`).
* **UnityStubs + UnityCheck**: the runtime and editor scripts compiled against hand-written signatures of the Unity 6 APIs they use.
  * Defines: `UNITY_EDITOR;ENABLE_INPUT_SYSTEM;NERAM_INPUT_SYSTEM`, matching the project's Input System setting.
  * A legacy-input variant can be built with `-p:DefineConstants=UNITY_5_3_OR_NEWER%3BUNITY_EDITOR%3BENABLE_LEGACY_INPUT_MANAGER`.
  * This catches typos and type errors. The stubs are written from the documentation and may differ from the real API.
* **BundleCheck**: runs the exact `NeramBundleReader` the editor uses on `NERAM_Generated/MeshData/neram_scene.bytes`. It checks:
  * materials and textures against the palette;
  * the CAD part names, regions, presets and lights;
  * left/right placement;
  * triangle winding vs. normals (Unity front-face convention);
  * label reading direction.

Python checks (stdlib only), from the workspace root:
```bash
python tests/test_validate_replay.py          # 62 fixtures, Python validator == C# validator verdicts
python tests/test_unity_ui_contract.py        # UXML contract, file/class names, wording guard
python tools/verify_workspace_v3.py           # workspace layout, settings, root-cause fixes, generated data, replays, holdout guard
python tools/gen_replay_schema.py --check     # generated schema up to date
python tools/make_synthetic_replays.py --check
python tools/sync_unity_streaming_assets.py --check
```
