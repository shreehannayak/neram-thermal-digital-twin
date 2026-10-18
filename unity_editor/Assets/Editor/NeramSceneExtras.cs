using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using Neram.Unity;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

namespace Neram.EditorTools
{
    /// <summary>
    /// Applies tools/gen_scene_extras.py output (Assets/NERAM_Generated/MeshData/scene_extras.json) to the open scene:
    /// patient head detail (theatre cap, ears, brows, lashes), anaesthesia face mask with strap, portable O2 cylinder on
    /// a trolley with tubing, ILLUSTRATIVE airway and lungs (Internal view), a surgeon figure (I J K L, U O) and the
    /// illustrative airflow particles. Re-applying replaces what an earlier run created (NeramExtrasMarker). Visual
    /// stand-ins only: nothing here models gas flow, oxygen delivery, breathing or anatomy.
    /// </summary>
    public static class NeramSceneExtras
    {
        public const string JsonPath = "Assets/NERAM_Generated/MeshData/scene_extras.json";
        private const string MeshDir = "Assets/NERAM_Generated/Meshes/Extras";

        [Serializable] private class MatJ { public string name; public float[] color; public float smoothness, metallic; public bool transparent; public float[] emission; }
        [Serializable] private class PartJ { public string group, name, parent, mat; public float[] v, n; public int[] f; }
        [Serializable] private class PoseJ { public float[] position; public float yaw_deg; }
        [Serializable] private class FlowJ { public bool @internal; public float[] p; }
        [Serializable] private class ExtrasJ { public MatJ[] materials; public PartJ[] parts; public string[] hide_prefixes; public PoseJ surgeon; public FlowJ[] airflow; public float breath_s; }

        [MenuItem("NERAM/Scene/Apply scene extras (mask, O2, airway, surgeon)", priority = 30)]
        public static void Menu() => EditorUtility.DisplayDialog("NERAM scene extras", Apply(), "OK");

        public static string Apply()
        {
            var sb = new StringBuilder();
            var ta = AssetDatabase.LoadAssetAtPath<TextAsset>(JsonPath);
            if (ta == null) return "missing " + JsonPath + " (run tools/gen_scene_extras.py)";
            var ex = JsonUtility.FromJson<ExtrasJ>(ta.text);
            if (ex == null || ex.parts == null) return "scene_extras.json does not parse";
            var asm = GameObject.Find(SceneNames.Assembly);
            if (asm == null) return "NERAM_Assembly not found (run NERAM > 1. Run full setup first)";

            foreach (var m in UnityEngine.Object.FindObjectsByType<NeramExtrasMarker>(FindObjectsInactive.Include, FindObjectsSortMode.None))
                if (m != null) UnityEngine.Object.DestroyImmediate(m.gameObject);

            var mats = EnsureMaterials(ex.materials, sb);
            Directory.CreateDirectory(MeshDir);

            var root = NewChild(asm.transform, "NERAM_Scene_Extras");
            Transform head = Find(asm.transform, "Head_Neck"), vessels = Find(asm.transform, "Illustrative_Vessels");
            var surgeon = NewChild(asm.transform, "Surgeon_Figure");
            if (ex.surgeon != null && ex.surgeon.position != null && ex.surgeon.position.Length == 3)
            {
                surgeon.localPosition = new Vector3(ex.surgeon.position[0], ex.surgeon.position[1], ex.surgeon.position[2]);
                surgeon.localRotation = Quaternion.Euler(0f, ex.surgeon.yaw_deg, 0f);
            }
            surgeon.gameObject.AddComponent<SurgeonController>();
            Transform airwayRoot = null;
            if (vessels != null) airwayRoot = NewChild(vessels, "Illustrative_Airway");

            var lungs = new List<Transform>();
            int made = 0;
            foreach (var p in ex.parts)
            {
                Transform parent = p.parent == "Head_Neck" ? (head != null ? head : root)
                                 : p.parent == "Illustrative_Vessels" ? (airwayRoot != null ? airwayRoot : root)
                                 : p.parent == "Surgeon_Figure" ? surgeon : root;
                var t = MakePart(p, parent, asm.transform, mats, sb);
                if (t == null) continue;
                made++;
                if (p.name.StartsWith("Airway_Lung")) lungs.Add(t);
            }

            int hidden = 0;
            if (ex.hide_prefixes != null)
                foreach (var tr in UnityEngine.Object.FindObjectsByType<Transform>(FindObjectsInactive.Exclude, FindObjectsSortMode.None))
                    foreach (var pre in ex.hide_prefixes)
                        if (tr.name.StartsWith(pre) && tr.GetComponentInParent<NeramExtrasMarker>() == null) { tr.gameObject.SetActive(false); hidden++; break; }

            mats.TryGetValue("MAT_AirParticle", out var particle);
            if (ex.airflow != null)
            {
                var ext = root.gameObject.AddComponent<AirflowAnimator>();
                ext.Setup(particle, Flows(ex.airflow, false), false, ex.breath_s, null);
                if (airwayRoot != null)
                {
                    var inner = NewChild(airwayRoot, "Airflow_Internal").gameObject.AddComponent<AirflowAnimator>();
                    inner.Setup(particle, Flows(ex.airflow, true), true, ex.breath_s, lungs.ToArray());
                }
            }

            EditorSceneManager.MarkSceneDirty(asm.scene);
            EditorSceneManager.SaveScene(asm.scene);
            sb.Insert(0, $"scene extras: {made} parts, {hidden} wall O2 cylinder parts hidden, surgeon at {surgeon.localPosition}, scene saved\n");
            return sb.ToString();
        }

        private static List<Vector3[]> Flows(FlowJ[] all, bool inner)
        {
            var list = new List<Vector3[]>();
            foreach (var f in all)
            {
                if (f.@internal != inner || f.p == null || f.p.Length < 6) continue;
                var pts = new Vector3[f.p.Length / 3];
                for (int i = 0; i < pts.Length; i++) pts[i] = new Vector3(f.p[3 * i], f.p[3 * i + 1], f.p[3 * i + 2]);
                list.Add(pts);
            }
            return list;
        }

        private static Transform NewChild(Transform parent, string name)
        {
            var go = new GameObject(name);
            go.AddComponent<NeramExtrasMarker>();
            go.transform.SetParent(parent, false);
            return go.transform;
        }

        private static Transform Find(Transform root, string name)
        {
            foreach (var t in root.GetComponentsInChildren<Transform>(true)) if (t.name == name) return t;
            return null;
        }

        /// <summary>Vertices are NERAM_Assembly-local (Surgeon_Figure parts: figure-local). The mesh is re-centred on its
        /// bounds so each part has a sensible pivot (lungs scale about their centre when they "breathe").</summary>
        private static Transform MakePart(PartJ p, Transform parent, Transform asm, Dictionary<string, Material> mats, StringBuilder sb)
        {
            if (p.v == null || p.f == null || p.v.Length < 9) return null;
            int nv = p.v.Length / 3;
            var V = new Vector3[nv];
            var N = new Vector3[nv];
            bool figure = p.parent == "Surgeon_Figure";
            var b = new Bounds();
            for (int i = 0; i < nv; i++)
            {
                var w = new Vector3(p.v[3 * i], p.v[3 * i + 1], p.v[3 * i + 2]);
                V[i] = w;
                if (p.n != null && p.n.Length == p.v.Length) N[i] = new Vector3(p.n[3 * i], p.n[3 * i + 1], p.n[3 * i + 2]);
                if (i == 0) b = new Bounds(w, Vector3.zero); else b.Encapsulate(w);
            }
            var go = new GameObject(p.name);
            go.AddComponent<NeramExtrasMarker>();
            go.transform.SetParent(parent, false);
            // place the pivot at the bounds centre, expressed in the parent's frame
            Vector3 centreAsm = b.center;
            if (figure) go.transform.localPosition = centreAsm;
            else go.transform.position = asm.TransformPoint(centreAsm);
            go.transform.rotation = figure ? parent.rotation : asm.rotation;
            var toLocal = figure ? Matrix4x4.Translate(-centreAsm) : go.transform.worldToLocalMatrix * asm.localToWorldMatrix;
            var nrm = figure ? Matrix4x4.identity : toLocal;
            for (int i = 0; i < nv; i++) { V[i] = toLocal.MultiplyPoint3x4(V[i]); N[i] = nrm.MultiplyVector(N[i]).normalized; }
            var mesh = new Mesh { name = "Extras_" + p.name };
            if (nv > 65000) mesh.indexFormat = IndexFormat.UInt32;
            mesh.vertices = V;
            mesh.triangles = p.f;
            if (p.n != null && p.n.Length == p.v.Length) mesh.normals = N; else mesh.RecalculateNormals();
            mesh.RecalculateBounds();
            var path = MeshDir + "/Extras_" + p.name + ".asset";
            var old = AssetDatabase.LoadAssetAtPath<Mesh>(path);
            if (old != null) { EditorUtility.CopySerialized(mesh, old); mesh = old; }
            else AssetDatabase.CreateAsset(mesh, path);
            go.AddComponent<MeshFilter>().sharedMesh = mesh;
            var mr = go.AddComponent<MeshRenderer>();
            if (!mats.TryGetValue(p.mat, out var mat))
            {
                mat = AssetDatabase.LoadAssetAtPath<Material>(NeramSetup.MaterialsDir + "/" + p.mat + ".mat");
                if (mat == null) { sb.AppendLine("  material missing for " + p.name + ": " + p.mat); mat = AssetDatabase.LoadAssetAtPath<Material>(NeramSetup.MaterialsDir + "/MAT_Skin.mat"); }
                mats[p.mat] = mat;
            }
            mr.sharedMaterial = mat;
            if (mat != null && mat.renderQueue >= (int)RenderQueue.Transparent) mr.shadowCastingMode = ShadowCastingMode.Off;
            return go.transform;
        }

        private static Dictionary<string, Material> EnsureMaterials(MatJ[] specs, StringBuilder sb)
        {
            var mats = new Dictionary<string, Material>();
            if (specs == null) return mats;
            var lit = NeramSetup.LitShader();
            foreach (var s in specs)
            {
                var path = NeramSetup.MaterialsDir + "/" + s.name + ".mat";
                var m = AssetDatabase.LoadAssetAtPath<Material>(path);
                if (m == null) { m = new Material(lit) { name = s.name }; AssetDatabase.CreateAsset(m, path); }
                m.shader = lit;
                var c = s.color != null && s.color.Length >= 4 ? new Color(s.color[0], s.color[1], s.color[2], s.color[3]) : Color.white;
                if (m.HasProperty("_BaseColor")) m.SetColor("_BaseColor", c);
                if (m.HasProperty("_Color")) m.SetColor("_Color", c);
                if (m.HasProperty("_Smoothness")) m.SetFloat("_Smoothness", s.smoothness);
                if (m.HasProperty("_Metallic")) m.SetFloat("_Metallic", s.metallic);
                if (s.transparent) NeramSceneBuilder.MakeTransparent(m); else NeramSceneBuilder.MakeOpaque(m);
                if (s.emission != null && s.emission.Length >= 3)
                {
                    m.EnableKeyword("_EMISSION");
                    m.SetColor("_EmissionColor", new Color(s.emission[0], s.emission[1], s.emission[2]));
                    m.globalIlluminationFlags = MaterialGlobalIlluminationFlags.RealtimeEmissive;
                }
                else { m.DisableKeyword("_EMISSION"); m.globalIlluminationFlags = MaterialGlobalIlluminationFlags.EmissiveIsBlack; }
                EditorUtility.SetDirty(m);
                mats[s.name] = m;
            }
            AssetDatabase.SaveAssets();
            sb.AppendLine("  materials: " + mats.Count);
            return mats;
        }
    }
}
