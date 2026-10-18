using System.Collections.Generic;
using System.Text;
using Neram.Unity;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace Neram.EditorTools
{
    /// <summary>
    /// Places Neharika's CAD (Unity-prepped 2026-10-18: metres, Y up, plan V/W names, MAT_* materials) on the generated
    /// mannequin. All poses and fits come from Assets/NERAM_Generated/MeshData/cad_fit.json, written by
    /// tools/gen_cad_fit.py from the CAD geometry and the mannequin skeleton (single source of truth):
    ///   hands  : palm-up on the raised arm boards; anatomical hand (one finger under every glove finger, built from the
    ///            glove outline); the fabric pad layers are draped onto it (parts list)
    ///   feet   : five-toed foot skin, sole pad from heel towards the ball (toes left free)
    ///   straps : rebuilt as bands that follow the limb + pad section (CAD width/thickness, length fitted), closure tab on the band
    ///   watch  : display-only concept around the right wrist; the live watch face moves with it
    ///   ctrl   : clamped on the left side rail, display facing away from the table (towards the clinician)
    ///   cables : re-routed from the controller ports to each pad's cable edge
    /// The stand-ins (*_PLACEHOLDER) are disabled, never deleted. Runs from NERAM > CAD and after every scene rebuild.
    /// </summary>
    public static class NeramCadPlacement
    {
        public const string FitJson = "Assets/NERAM_Generated/MeshData/cad_fit.json";
        public const string WatchRole = "Watch_Concept";
        private static readonly string[] OldWatchParts = { "Watch_Band", "Watch_Body", "Watch_Bezel", "Watch_Crown" };
        private const string BoardsLiftedMarker = "__arm_boards_lifted";

#pragma warning disable 0649
        [System.Serializable] private sealed class PoseJ { public string role; public float[] p; public float[] fwd; public float[] up; public float k = 1f; }
        [System.Serializable] private sealed class MeshJ { public string name; public string role; public float[] v; public float[] n; public int[] f; }
        [System.Serializable] private sealed class StrapJ { public string obj; public float sx; public float sy; public float px; public float py; public float hookDy; }
        [System.Serializable] private sealed class CableJ { public int ch; public float[] port; public float[] w; }
        [System.Serializable] private sealed class ReplaceJ { public string name; public float[] v; public float[] n; }
        [System.Serializable] private sealed class PartJ { public string role; public string obj; public float[] v; public float[] n; public int[] f; public float[] uv; public string mat; }
        [System.Serializable] private sealed class FitJ { public PartJ[] parts; public ReplaceJ[] replace; public float boardLift; public float[] watchScreen; public PoseJ[] poses; public MeshJ[] meshes; public StrapJ[] straps; public CableJ[] cables; }
#pragma warning restore 0649

        private static Vector3 V(float[] a, int i = 0) => new Vector3(a[i], a[i + 1], a[i + 2]);
        private static GameObject Load(string file) => AssetDatabase.LoadAssetAtPath<GameObject>(NeramCadTools.CadFolder + "/" + file);

        [MenuItem("NERAM/CAD/Place Neharika CAD on the mannequin", priority = 19)]
        public static void PlaceMenu()
        {
            var asm = GameObject.Find(SceneNames.Assembly);
            if (asm == null) { EditorUtility.DisplayDialog("NERAM CAD", "Open " + NeramSetup.ScenePath + " first (NERAM_Assembly not found).", "OK"); return; }
            var log = PlaceAll(asm.transform, out int placed);
            EditorSceneManager.MarkSceneDirty(asm.scene);
            EditorSceneManager.SaveScene(asm.scene);
            Debug.Log("[NERAM CAD]\n" + log);
            EditorUtility.DisplayDialog("NERAM CAD", placed + " CAD model(s) placed and scene saved.\n\n" + log, "OK");
        }

        /// <summary>Called by setup after every scene rebuild; roles without a CAD file keep their stand-in.</summary>
        public static string PlaceAll(Transform asm, out int placed)
        {
            placed = 0;
            var sb = new StringBuilder();
            var ta = AssetDatabase.LoadAssetAtPath<TextAsset>(FitJson);
            if (ta == null) return "no " + FitJson + " (run tools/gen_cad_fit.py); CAD not placed";
            var fit = JsonUtility.FromJson<FitJ>(ta.text);
            var poses = new Dictionary<string, PoseJ>();
            foreach (var p in fit.poses) poses[p.role] = p;

            LiftArmBoards(asm, fit.boardLift, sb);
            if (fit.replace != null) foreach (var r in fit.replace) ReplaceSkin(asm, r, sb);

            for (int i = 0; i < 4; i++)
            {
                string role = SceneNames.Modules[i];
                var prefab = Load("NERAM_" + role + ".fbx");
                if (prefab == null || !poses.ContainsKey(role)) { sb.AppendLine(role + ": no CAD file, stand-in kept"); continue; }
                var ph = asm.Find(role + SceneNames.PlaceholderSuffix);
                KeepBodyVisible(asm, ph, role, "CH" + (i + 1) + "_");
                var inst = Place(asm, prefab, role, poses[role], ph, asm);
                foreach (var m in fit.meshes) if (m.role == role) AddSkin(asm, role, m);
                if (i >= 2) FitStraps(inst.transform, fit.straps, i + 1, sb);
                ApplyParts(inst.transform, role, fit.parts, sb);
                placed++;
                sb.AppendLine(role + ": CAD placed + fitted skin");
            }

            var ctrl = Load("NERAM_Bedside_Controller.fbx");
            if (ctrl != null && poses.ContainsKey(SceneNames.Controller))
            {
                var ci = Place(asm, ctrl, SceneNames.Controller, poses[SceneNames.Controller], asm.Find(SceneNames.Controller + SceneNames.PlaceholderSuffix), asm);
                ApplyParts(ci.transform, SceneNames.Controller, fit.parts, sb);
                placed++;
                sb.AppendLine(SceneNames.Controller + ": CAD clamped on the left side rail");
            }

            var watch = Load("NERAM_Watch_Concept.fbx");
            Transform host = null;
            foreach (var t in asm.GetComponentsInChildren<Transform>(true)) if (t.name == "Wearable_Watch") { host = t; break; }
            if (watch != null && host != null && poses.ContainsKey(WatchRole))
            {
                host.position = V(fit.watchScreen);               // generator node position = live screen position
                foreach (var n in OldWatchParts) { var o = host.Find(n); if (o != null) o.gameObject.SetActive(false); }
                Place(host, watch, WatchRole, poses[WatchRole], null, asm);
                placed++;
                sb.AppendLine("Wearable_Watch: watch around the right wrist (display-only concept), live screen moved with it");
            }

            if (fit.cables != null) foreach (var c in fit.cables) RouteCable(asm, c, sb);
            ApplyProjectMaterials(asm);
            return sb.ToString();
        }

        private static GameObject Place(Transform parent, GameObject prefab, string role, PoseJ pose, Transform placeholder, Transform asm)
        {
            var old = parent.Find(role);
            if (old != null) Object.DestroyImmediate(old.gameObject);
            var inst = (GameObject)PrefabUtility.InstantiatePrefab(prefab, parent);
            inst.name = role;
            inst.transform.SetPositionAndRotation(asm.TransformPoint(V(pose.p)),
                asm.rotation * Quaternion.LookRotation(V(pose.fwd), V(pose.up)));
            var ls = parent.lossyScale;
            inst.transform.localScale = new Vector3(pose.k / ls.x, pose.k / ls.y, pose.k / ls.z);
            if (placeholder != null) placeholder.gameObject.SetActive(false);
            return inst;
        }

        /// <summary>Raise the arm boards so the generated forearms rest on them (they floated 25 mm above). Once per scene.</summary>
        private static void LiftArmBoards(Transform asm, float lift, StringBuilder sb)
        {
            if (lift <= 0f) return;
            Transform table = null;
            foreach (var t in asm.GetComponentsInChildren<Transform>(true)) if (t.name.StartsWith("Arm_Board_L")) { table = t.parent; break; }
            if (table == null || table.Find(BoardsLiftedMarker) != null) return;
            var move = new List<Transform>();
            foreach (Transform c in table) if (c.name.StartsWith("Arm_Board_")) move.Add(c);
            foreach (var c in move) c.position += Vector3.up * lift;
            new GameObject(BoardsLiftedMarker).transform.SetParent(table, false);
            sb.AppendLine("arm boards raised " + (lift * 1000f).ToString("0") + " mm (" + move.Count + " parts)");
        }

        /// <summary>The generator parents some stand-in pieces under the module stand-in; keep anything that is not a
        /// stand-in module part (CHn_*) visible by moving it into "&lt;role&gt;_Body".</summary>
        private static Transform KeepBodyVisible(Transform asm, Transform ph, string role, string partPrefix)
        {
            var holderName = role + "_Body";
            var holder = asm.Find(holderName);
            if (holder == null)
            {
                holder = new GameObject(holderName).transform;
                holder.SetParent(asm, false);
            }
            if (ph == null) return holder;
            var move = new List<Transform>();
            foreach (Transform c in ph) if (!c.name.StartsWith(partPrefix)) move.Add(c);
            foreach (var c in move) c.SetParent(holder, true);
            return holder;
        }

        /// <summary>Forearm skin with the wrist flattened (tools/gen_cad_fit.py); same topology, saved as its own mesh asset.</summary>
        private static void ReplaceSkin(Transform asm, ReplaceJ r, StringBuilder sb)
        {
            MeshFilter mf = null;
            foreach (var t in asm.GetComponentsInChildren<MeshFilter>(true)) if (t.name == r.name) { mf = t; break; }
            if (mf == null || mf.sharedMesh == null || mf.sharedMesh.vertexCount * 3 != r.v.Length) { sb.AppendLine(r.name + ": not replaced (mesh missing or changed)"); return; }
            var path = "Assets/NERAM_Generated/Meshes/CadBody_" + r.name + ".asset";
            var src = mf.sharedMesh;
            if (AssetDatabase.GetAssetPath(src) == path) src = Object.Instantiate(src);
            var mesh = Object.Instantiate(src);
            mesh.name = r.name;
            int nv = r.v.Length / 3;
            var v = new Vector3[nv]; var nr = new Vector3[nv];
            for (int k = 0; k < nv; k++)
            {
                v[k] = mf.transform.InverseTransformPoint(asm.TransformPoint(V(r.v, 3 * k)));
                nr[k] = mf.transform.InverseTransformDirection(asm.TransformDirection(V(r.n, 3 * k)));
            }
            mesh.vertices = v; mesh.normals = nr; mesh.RecalculateBounds();
            if (AssetDatabase.LoadAssetAtPath<Mesh>(path) != null) AssetDatabase.DeleteAsset(path);
            AssetDatabase.CreateAsset(mesh, path);
            mf.sharedMesh = mesh;
            var mc = mf.GetComponent<MeshCollider>();
            if (mc != null) mc.sharedMesh = mesh;
            sb.AppendLine(r.name + ": wrist reshaped");
        }

        private static void AddSkin(Transform asm, string role, MeshJ bm)
        {
            var holder = KeepBodyVisible(asm, null, role, "");
            var old = holder.Find(bm.name);
            if (old != null) Object.DestroyImmediate(old.gameObject);
            int nv = bm.v.Length / 3;
            var v = new Vector3[nv]; var nr = new Vector3[nv];
            for (int k = 0; k < nv; k++) { v[k] = V(bm.v, 3 * k); nr[k] = V(bm.n, 3 * k); }
            var mesh = new Mesh { name = bm.name };
            if (nv > 65535) mesh.indexFormat = UnityEngine.Rendering.IndexFormat.UInt32;
            mesh.vertices = v; mesh.normals = nr; mesh.triangles = bm.f; mesh.RecalculateBounds();
            var path = "Assets/NERAM_Generated/Meshes/CadBody_" + bm.name + ".asset";
            if (AssetDatabase.LoadAssetAtPath<Mesh>(path) != null) AssetDatabase.DeleteAsset(path);
            AssetDatabase.CreateAsset(mesh, path);
            var go = new GameObject(bm.name);
            go.transform.SetParent(holder, false);
            go.transform.SetPositionAndRotation(asm.position, asm.rotation);
            go.AddComponent<MeshFilter>().sharedMesh = mesh;
            var r = go.AddComponent<MeshRenderer>();
            var skin = AssetDatabase.LoadAssetAtPath<Material>(NeramSetup.MaterialsDir + "/MAT_Skin.mat");
            if (skin != null) r.sharedMaterial = skin;
        }

        /// <summary>Replace (or add) CAD child meshes from tools/gen_cad_fit.py: draped pad layers, strap bands, closure tabs,
        /// the controller screen. Vertices are in the CAD root's local frame; meshes are saved as assets.</summary>
        private static void ApplyParts(Transform root, string role, PartJ[] parts, StringBuilder sb)
        {
            if (parts == null) return;
            int n = 0;
            foreach (var pj in parts)
            {
                if (pj.role != role) continue;
                Transform t = null;
                foreach (var c in root.GetComponentsInChildren<Transform>(true)) if (c.name == pj.obj) { t = c; break; }
                if (t == null)
                {
                    t = new GameObject(pj.obj).transform;
                    t.SetParent(root, false);
                }
                var mf = t.GetComponent<MeshFilter>();
                if (mf == null) mf = t.gameObject.AddComponent<MeshFilter>();
                var mr = t.GetComponent<MeshRenderer>();
                if (mr == null) mr = t.gameObject.AddComponent<MeshRenderer>();
                int nv = pj.v.Length / 3;
                var v = new Vector3[nv]; var nr = new Vector3[nv];
                for (int k = 0; k < nv; k++)
                {
                    v[k] = t.InverseTransformPoint(root.TransformPoint(V(pj.v, 3 * k)));
                    nr[k] = t.InverseTransformDirection(root.TransformDirection(V(pj.n, 3 * k))).normalized;
                }
                var mesh = new Mesh { name = role + "_" + pj.obj };
                if (nv > 65535) mesh.indexFormat = UnityEngine.Rendering.IndexFormat.UInt32;
                mesh.vertices = v; mesh.normals = nr;
                if (pj.uv != null && pj.uv.Length == nv * 2)
                {
                    var uv = new Vector2[nv];
                    for (int k = 0; k < nv; k++) uv[k] = new Vector2(pj.uv[2 * k], pj.uv[2 * k + 1]);
                    mesh.uv = uv;
                }
                mesh.triangles = pj.f; mesh.RecalculateBounds();
                var path = "Assets/NERAM_Generated/Meshes/CadPart_" + role + "_" + pj.obj + ".asset";
                if (AssetDatabase.LoadAssetAtPath<Mesh>(path) != null) AssetDatabase.DeleteAsset(path);
                AssetDatabase.CreateAsset(mesh, path);
                mf.sharedMesh = mesh;
                if (!string.IsNullOrEmpty(pj.mat)) { var m = TexMaterial(pj.mat); if (m != null) mr.sharedMaterial = m; }
                n++;
            }
            if (n > 0) sb.AppendLine(role + ": " + n + " fitted part mesh(es) (draped pad, strap bands, tabs, screen)");
        }

        /// <summary>"TEX:name" -> MAT_TEX_name (copy of MAT_TEX_watch_face with Assets/NERAM_Generated/Textures/name.png).</summary>
        private static Material TexMaterial(string spec)
        {
            if (!spec.StartsWith("TEX:")) return AssetDatabase.LoadAssetAtPath<Material>(NeramSetup.MaterialsDir + "/" + spec + ".mat");
            var name = spec.Substring(4);
            var path = NeramSetup.MaterialsDir + "/MAT_TEX_" + name + ".mat";
            var tex = AssetDatabase.LoadAssetAtPath<Texture2D>("Assets/NERAM_Generated/Textures/" + name + ".png");
            var mat = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (mat == null)
            {
                var src = AssetDatabase.LoadAssetAtPath<Material>(NeramSetup.MaterialsDir + "/MAT_TEX_watch_face.mat");
                if (src == null) return null;
                mat = new Material(src) { name = "MAT_TEX_" + name };
                AssetDatabase.CreateAsset(mat, path);
            }
            if (tex != null)
            {
                foreach (var prop in new[] { "_BaseMap", "_MainTex", "_EmissionMap" }) if (mat.HasProperty(prop)) mat.SetTexture(prop, tex);
                EditorUtility.SetDirty(mat);
            }
            return mat;
        }

        /// <summary>CAD straps enclose a 29 mm limb (a hand); on the foot they are lengthened to the foot height at their
        /// position (top edge kept) and the hook moved with the strap end. Visual fit only; noted for Neharika.</summary>
        private static void FitStraps(Transform root, StrapJ[] straps, int ch, StringBuilder sb)
        {
            if (straps == null) return;
            foreach (var s in straps)
            {
                if (!s.obj.StartsWith("CH" + ch + "_")) continue;
                var t = root.Find(s.obj);
                if (t == null) continue;
                t.localScale = new Vector3(s.sx, s.sy, 1f);
                t.localPosition = new Vector3(s.px, s.py, 0f);
                var hook = root.Find(s.obj.Replace("Strap", "Hook"));
                if (hook != null) hook.localPosition = new Vector3(0f, s.hookDy, 0f);
            }
            sb.AppendLine("CH" + ch + " straps fitted to the foot");
        }

        private static void RouteCable(Transform asm, CableJ c, StringBuilder sb)
        {
            Transform node = asm.Find("Cable_CH" + c.ch + SceneNames.PlaceholderSuffix);
            if (node == null) return;
            node.position = asm.TransformPoint(V(c.port));
            var kill = new List<GameObject>();
            foreach (Transform t in node) if (t.name.StartsWith("wp")) kill.Add(t.gameObject);
            foreach (var g in kill) Object.DestroyImmediate(g);
            int n = c.w.Length / 3;
            for (int i = 0; i < n; i++)
            {
                var wp = new GameObject("wp" + i.ToString("00") + "_CH" + c.ch);
                wp.transform.SetParent(node, false);
                wp.transform.position = asm.TransformPoint(V(c.w, 3 * i));
            }
            var tube = node.GetComponent<CableTube>();
            if (tube != null) tube.Rebuild();
            sb.AppendLine("Cable_CH" + c.ch + " re-routed (" + n + " waypoints)");
        }

        /// <summary>MAT_* slots that exist in the project palette use the project material (heater glow, indicator
        /// states); other MAT_* slots (MAT_Display, MAT_Button_*, MAT_Placeholder) keep Neharika's flat colours.</summary>
        private static void ApplyProjectMaterials(Transform asm)
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
                    if (mats[i] == null || !mats[i].name.StartsWith("MAT_")) continue;
                    if (lib.TryGetValue(mats[i].name, out var proj) && proj != mats[i]) { mats[i] = proj; changed = true; }
                }
                // PCB/PSU placeholders sit inside the closed enclosure: magenta (CAD placeholder convention) shows through
                // the vents and reads as a render error in the viewer, so they use the dark equipment material here.
                if ((r.name == "BC_PCB_Placeholder" || r.name == "BC_PSU_Placeholder") && lib.TryGetValue("MAT_EquipDark", out var dark))
                {
                    for (int i = 0; i < mats.Length; i++) mats[i] = dark;
                    changed = true;
                }
                if (changed) r.sharedMaterials = mats;
            }
        }
    }
}
