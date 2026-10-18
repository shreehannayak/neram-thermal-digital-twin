using System.Collections.Generic;
using System.Linq;
using System.Text;
using Neram.Unity;
using UnityEditor;
using UnityEngine;

namespace Neram.EditorTools
{
    /// <summary>
    /// CAD integration for Neharika's models (docs/unity/CAD_INTEGRATION.md).
    ///  1. Export FBX in metres, Y up, origin = table-top centre, +Z toward the head (patient's left = +X), object names per
    ///     the CAD contract (Left_Hand_Module with children CH1_Liner ... CH1_Heater ..., Bedside_Controller with BC_* ...).
    ///  2. Drop the FBX files into Assets/NERAM_CAD/ (import settings are applied automatically below).
    ///  3. Select the imported model(s) in the Project window and run NERAM > CAD > Integrate selected CAD models.
    /// The tool instantiates each top-level role object under NERAM_Assembly with its exact role name; the binder then
    /// prefers it and disables the matching *_PLACEHOLDER. Nothing in the replay code changes.
    /// </summary>
    public static class NeramCadTools
    {
        public const string CadFolder = "Assets/NERAM_CAD";

        private static IEnumerable<string> Roles()
        {
            yield return SceneNames.Table;
            yield return SceneNames.Mannequin;
            yield return SceneNames.Controller;
            yield return SceneNames.CableHub;
            foreach (var m in SceneNames.Modules) yield return m;
            for (int ch = 1; ch <= 4; ch++) yield return SceneNames.Cable(ch);
        }

        [MenuItem("NERAM/CAD/Integrate selected CAD models", priority = 20)]
        public static void IntegrateSelected()
        {
            var asm = GameObject.Find(SceneNames.Assembly);
            if (asm == null) { EditorUtility.DisplayDialog("NERAM CAD", "Open " + NeramSetup.ScenePath + " first (NERAM_Assembly not found).", "OK"); return; }
            var roles = new HashSet<string>(Roles());
            var log = new StringBuilder();
            int placed = 0;
            foreach (var obj in Selection.objects)
            {
                var prefab = obj as GameObject;
                if (prefab == null) continue;
                // The model may be a single role (root named e.g. Left_Hand_Module) or a full assembly containing several roles.
                var candidates = roles.Contains(prefab.name)
                    ? new List<Transform> { prefab.transform }
                    : prefab.GetComponentsInChildren<Transform>(true).Where(t => roles.Contains(t.name)).ToList();
                if (candidates.Count == 0) { log.AppendLine(prefab.name + ": no object named after a CAD role (" + string.Join(", ", roles) + ")"); continue; }
                foreach (var c in candidates)
                {
                    var existing = asm.transform.Find(c.name);
                    if (existing != null) Undo.DestroyObjectImmediate(existing.gameObject);
                    GameObject inst;
                    if (c == prefab.transform) inst = (GameObject)PrefabUtility.InstantiatePrefab(prefab, asm.transform);
                    else
                    {
                        inst = Object.Instantiate(c.gameObject, asm.transform);
                        inst.name = c.name;
                    }
                    Undo.RegisterCreatedObjectUndo(inst, "Integrate CAD " + c.name);
                    inst.transform.SetPositionAndRotation(c.position, c.rotation); // CAD is authored in scene coordinates
                    placed++;
                    log.AppendLine(c.name + ": placed under " + SceneNames.Assembly + " — " + CheckParts(inst.transform));
                }
            }
            ApplyMaterials(asm.transform);
            var binder = asm.GetComponent<NeramAssemblyBinder>();
            if (binder != null) DisablePlaceholdersWithCad(asm.transform);
            UnityEditor.SceneManagement.EditorSceneManager.MarkSceneDirty(asm.scene);
            log.Insert(0, placed + " CAD object(s) integrated. Save the scene, then run NERAM > 4. Validate project.\n\n");
            Debug.Log(log.ToString());
            EditorUtility.DisplayDialog("NERAM CAD", log.ToString(), "OK");
        }

        [MenuItem("NERAM/CAD/Integrate selected CAD models", true)]
        private static bool IntegrateSelectedValidate() => Selection.objects.Any(o => o is GameObject);

        [MenuItem("NERAM/CAD/Report CAD vs placeholder", priority = 21)]
        public static void Report()
        {
            var asm = GameObject.Find(SceneNames.Assembly);
            if (asm == null) { Debug.LogWarning("[NERAM] NERAM_Assembly not found"); return; }
            var sb = new StringBuilder("CAD binding report\n");
            foreach (var role in Roles())
            {
                bool cad = asm.transform.Find(role) != null, ph = asm.transform.Find(role + SceneNames.PlaceholderSuffix) != null;
                sb.AppendLine(role + ": " + (cad ? "CAD" : ph ? "PLACEHOLDER" : "missing") + (cad ? " — " + CheckParts(asm.transform.Find(role)) : ""));
            }
            Debug.Log(sb.ToString());
            EditorUtility.DisplayDialog("NERAM CAD", sb.ToString(), "OK");
        }

        private static string CheckParts(Transform root)
        {
            var names = new HashSet<string>(root.GetComponentsInChildren<Transform>(true).Select(t => t.name));
            int idx = System.Array.IndexOf(SceneNames.Modules, root.name);
            if (idx >= 0)
            {
                var missing = SceneNames.ModuleParts.Select(p => SceneNames.Part(idx + 1, p)).Where(n => !names.Contains(n)).ToList();
                return missing.Count == 0 ? "all module parts named correctly" : "MISSING parts: " + string.Join(", ", missing);
            }
            if (root.name == SceneNames.Controller)
            {
                var missing = SceneNames.ControllerParts.Where(n => !names.Contains(n)).ToList();
                return missing.Count == 0 ? "all BC_* parts named correctly" : "MISSING parts: " + string.Join(", ", missing);
            }
            if (root.name.StartsWith("Cable_CH"))
            {
                var ch = root.name.Substring("Cable_CH".Length);
                return names.Contains("Connector_CH" + ch) ? "connector present" : "MISSING Connector_CH" + ch + " (plug state not animated)";
            }
            return "ok";
        }

        private static void DisablePlaceholdersWithCad(Transform asm)
        {
            foreach (var role in Roles())
            {
                var cad = asm.Find(role);
                var ph = asm.Find(role + SceneNames.PlaceholderSuffix);
                if (cad != null && ph != null && ph.gameObject.activeSelf)
                {
                    Undo.RecordObject(ph.gameObject, "Disable placeholder");
                    ph.gameObject.SetActive(false);
                }
            }
        }

        /// <summary>CAD material slots named MAT_* are replaced by the project materials of the same name.</summary>
        private static void ApplyMaterials(Transform asm)
        {
            var lib = new Dictionary<string, Material>();
            foreach (var guid in AssetDatabase.FindAssets("t:Material", new[] { NeramSetup.MaterialsDir }))
            {
                var m = AssetDatabase.LoadAssetAtPath<Material>(AssetDatabase.GUIDToAssetPath(guid));
                if (m != null) lib[m.name] = m;
            }
            foreach (var r in asm.GetComponentsInChildren<Renderer>(true))
            {
                if (r.GetComponentInParent<PlaceholderMarker>() != null) continue;
                var mats = r.sharedMaterials;
                bool changed = false;
                for (int i = 0; i < mats.Length; i++)
                {
                    if (mats[i] == null) continue;
                    var key = mats[i].name.Replace(" (Instance)", "");
                    if (lib.TryGetValue(key, out var proj) && proj != mats[i]) { mats[i] = proj; changed = true; }
                }
                if (changed) { Undo.RecordObject(r, "Apply NERAM materials"); r.sharedMaterials = mats; }
            }
        }
    }

    /// <summary>Import settings for CAD dropped into Assets/NERAM_CAD (metres, no animation, readable meshes for colliders).</summary>
    public sealed class NeramCadPostprocessor : AssetPostprocessor
    {
        private void OnPreprocessModel()
        {
            if (!assetPath.StartsWith(NeramCadTools.CadFolder + "/")) return;
            var mi = (ModelImporter)assetImporter;
            mi.globalScale = 1f;
            mi.useFileScale = true;
            mi.bakeAxisConversion = true;
            mi.importAnimation = false;
            mi.importCameras = false;
            mi.importLights = false;
            mi.isReadable = true;
            mi.addCollider = false;
            mi.materialImportMode = ModelImporterMaterialImportMode.ImportStandard;
            mi.materialLocation = ModelImporterMaterialLocation.InPrefab;
        }

        private void OnPostprocessModel(GameObject root)
        {
            if (!assetPath.StartsWith(NeramCadTools.CadFolder + "/")) return;
            var b = new Bounds();
            bool any = false;
            foreach (var r in root.GetComponentsInChildren<Renderer>(true))
            {
                if (!any) { b = r.bounds; any = true; }
                else b.Encapsulate(r.bounds);
            }
            if (any && (b.size.magnitude > 20f || b.size.magnitude < 0.01f))
                Debug.LogWarning("[NERAM CAD] " + assetPath + " bounds " + b.size + " m look wrong for metre units — check FBX export units (expected metres). Compare with Reference_Cube_1m.");
        }
    }
}
