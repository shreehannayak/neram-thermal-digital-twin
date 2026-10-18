# Unity installation failures: diagnosis from the available evidence

**What I had:** your written observations only. No Unity Hub log, Editor log, installer log or disk report was in the ZIPs. Everything below is therefore **inferred** unless marked otherwise.

## Observations (yours)
1. **Missing Package Manager server.** In `C:\Program Files\Unity\Hub\Editor\6000.6.5f1\Editor\Data\Resources\PackageManager\`, `BuiltinPackages` is present and **`Server` (UnityPackageManager.exe) is missing**. The Editor reports "Could not find Unity Package Manager local server application … antivirus action or corrupt Unity installation".
2. **Install not registered.** Hub does **not list 6000.6.5f1 under Installs**, although its folder exists in Program Files.
3. **Template decompression fails.** "Failed to decompress" occurs for two different template `.tgz` files in `%APPDATA%\UnityHub\Templates` (on C:). It persisted after deleting one of them.
4. **No security action logged.** Windows Security protection history shows "No recent action".
5. **C: full; new install fails.** **C: became full.** Hub was then pointed at D: (13 GB free), and the 6.3 LTS install failed with "Something went wrong". The Visual Studio Community 2026 component never downloaded.

## Most consistent explanation (inferred)
**C: ran out of space while the 6000.6.5f1 install was unpacking, and the install never completed.**

* **Why this fits observations 1 and 2.** Hub registers an Editor under Installs only after a successful install. An Editor folder that exists but is not listed is the signature of an interrupted install. Files written late in the unpack, such as the Package Manager `Server` folder, would be missing.
* **Public precedent.** In a Unity forum thread about this exact error, reporters traced it to low disk space during installation. One installer claimed it needed 7.5 GB and actually used about 21 GB; freeing about 25 GB and reinstalling fixed it.
* **Why this fits observation 3.** Unity's own support article lists **insufficient disk space** and a corrupted or incomplete template download among the causes of "Failed to decompress". Both template archives live on the full C: drive.
* **Antivirus.** Unity's error text lists antivirus as a possible cause, but "No recent action" makes it less likely. It is not ruled out.
* **Why the 6.3 install probably failed (observation 5).** Peak disk use during an Editor install has been measured far above the installed size: **about 26 GB at peak versus about 8.5 GB net** (6.2, macOS). 13 GB on D: is plausibly too little, and Hub may still place temporary files on C:. Visual Studio installs largely to C: regardless of Hub's paths. **The Hub log is needed to tell which of these happened.**

**What this means for the fix:**
* Deleting cached templates, switching templates or reinstalling *without freeing disk space* addresses none of these causes. That is why repeating those steps did not help.
* The ready-made project ZIP removes the template step entirely. It does **not** remove the need for a complete Editor, because the Package Manager server must exist for any project to open.

## Exact information needed from your PC (to confirm or refute the above)
1. Unity Hub logs: the whole folder **`%APPDATA%\UnityHub\logs\`** (`info-log.json` and any other files). The failed install attempts are recorded there with the actual error.
2. **`%LOCALAPPDATA%\Unity\Editor\Editor.log`** and **`upm.log`** from the same folder, if they exist.
3. PowerShell output:
   ```powershell
   Get-PSDrive C,D | Select-Object Name,@{n='UsedGB';e={[math]::Round($_.Used/1GB,1)}},@{n='FreeGB';e={[math]::Round($_.Free/1GB,1)}}
   $env:TEMP
   Get-ChildItem "C:\Program Files\Unity\Hub\Editor\6000.6.5f1\Editor\Data\Resources\PackageManager" | Select-Object Name
   (Get-ChildItem "C:\Program Files\Unity\Hub\Editor\6000.6.5f1" -Recurse -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum/1GB
   ```
4. A screenshot of Hub → Preferences → **Installs** (install and download locations) and of Hub → **Installs**.

## What to do, in order, and why
1. **Free space first:** ≥ 10 GB on C: and ≥ 30 GB on the Editor drive (D:). Removes the most likely cause of observations 1, 2, 3 and 5.
2. **Remove the broken 6000.6.5f1 folder.** Hub doesn't know about it, so delete `C:\Program Files\Unity\Hub\Editor\6000.6.5f1` manually (with Hub closed), or use "Locate" then "Uninstall" if Hub offers it. This recovers several GB on C:, and an incomplete Editor cannot open any project.
3. **Install 6000.3.x (LTS) to D: with no extra modules and Visual Studio unticked.** It matches the project manifest, and installing only the Editor minimises peak space.
4. **If it fails again,** send item 1 above (Hub logs) before anything else. That file holds the actual installer error; guessing further would repeat the loop.
5. **Open `NERAM_Unity_Project_Ready\unity` via Add project from disk** (no template). This avoids the template failure entirely.

## Sources
- [Unity Support: Failed to resolve project template / Failed to decompress](https://support.unity.com/hc/en-us/articles/37967813822996-Resolving-Failed-to-Resolve-Project-Template-Failed-to-Decompress-Error)
- [Unity Discussions: Could not find Unity Package Manager local server application](https://discussions.unity.com/t/could-not-find-unity-package-manager-local-server-application/931253)
- [Unity Discussions: Hub feature request on installation space (peak vs. net usage)](https://discussions.unity.com/t/unity-hub-feature-request-optimise-installation-of-editor/1690858)
- [Unity 6 support / LTS dates](https://unity.com/releases/unity-6/support)
- [URP version follows the Editor line (Unity 6.6 docs page)](https://docs.unity.cn/6000.6/Documentation/Manual/urp/requirements.html) · [Unity-version → URP-version table (third-party project)](https://github.com/izayoijiichan/VGO/blob/main/Documentation~/UniVGO/Installation.md)
