using System.IO;
using Neram.Unity;
using UnityEditor;
using UnityEngine;

namespace Neram.EditorTools
{
    /// <summary>Renders evidence PNGs of the placed CAD (edit mode, scene lights) into docs/evidence/cad_unity/.</summary>
    public static class NeramCadSnapshots
    {
        [MenuItem("NERAM/CAD/Save CAD snapshots (docs/evidence/cad_unity)", priority = 22)]
        public static void Save()
        {
            var asm = GameObject.Find(SceneNames.Assembly);
            if (asm == null) { EditorUtility.DisplayDialog("NERAM CAD", "NERAM_Assembly not found.", "OK"); return; }
            var dir = Path.GetFullPath(Path.Combine(Application.dataPath, "..", "..", "docs", "evidence", "cad_unity"));
            Directory.CreateDirectory(dir);
            int n = 0;
            n += Shot(asm.transform, "Left_Hand_Module", new Vector3(0.6f, 1.1f, -0.9f), 2.6f, dir, "01_left_hand_CH1.png");
            n += Shot(asm.transform, "Right_Hand_Module", new Vector3(-0.6f, 1.1f, -0.9f), 2.6f, dir, "02_right_hand_CH2.png");
            n += Shot(asm.transform, "Left_Foot_Module", new Vector3(0.5f, 0.6f, -1.2f), 2.4f, dir, "03_left_foot_CH3.png");
            n += Shot(asm.transform, "Right_Foot_Module", new Vector3(-0.5f, 0.6f, -1.2f), 2.4f, dir, "04_right_foot_CH4.png");
            n += Shot(asm.transform, "Bedside_Controller", new Vector3(0.2f, 0.4f, -1f), 2.2f, dir, "05_bedside_controller.png");
            n += Shot(asm.transform, "Watch_Concept", new Vector3(-0.3f, 1f, -0.6f), 3.5f, dir, "06_watch_concept.png");
            n += Shot(asm.transform, null, new Vector3(0.0f, 1.1f, -0.9f), 1.1f, dir, "00_overview.png");
            EditorUtility.DisplayDialog("NERAM CAD", n + " snapshot(s) written to\n" + dir, "OK");
        }

        /// <summary>views file: one view per line "name px py pz tx ty tz fov" (world metres). Returns a log.</summary>
        public static string RenderViews(string viewsFile, string outDir)
        {
            if (!File.Exists(viewsFile)) return "no views file " + viewsFile;
            Directory.CreateDirectory(outDir);
            var sb = new System.Text.StringBuilder();
            foreach (var raw in File.ReadAllLines(viewsFile))
            {
                var line = raw.Trim();
                if (line.Length == 0 || line.StartsWith("#")) continue;
                var p = line.Split(new[] { ' ', '\t' }, System.StringSplitOptions.RemoveEmptyEntries);
                if (p.Length < 8) { sb.AppendLine("bad line: " + line); continue; }
                float F(int i) => float.Parse(p[i], System.Globalization.CultureInfo.InvariantCulture);
                Capture(new Vector3(F(1), F(2), F(3)), new Vector3(F(4), F(5), F(6)), F(7), Path.Combine(outDir, p[0] + ".png"));
                sb.AppendLine("ok " + p[0]);
            }
            return sb.ToString();
        }

        private static void Capture(Vector3 pos, Vector3 target, float fov, string file)
        {
            var go = new GameObject("__snapshot_cam");
            try
            {
                var cam = go.AddComponent<Camera>();
                cam.fieldOfView = fov; cam.nearClipPlane = 0.005f; cam.farClipPlane = 50f;
                cam.clearFlags = CameraClearFlags.SolidColor; cam.backgroundColor = new Color(0.16f, 0.18f, 0.21f);
                cam.transform.position = pos;
                cam.transform.LookAt(target);
                var rt = new RenderTexture(1600, 1000, 24) { antiAliasing = 4 };
                cam.targetTexture = rt;
                cam.Render();
                RenderTexture.active = rt;
                var tex = new Texture2D(1600, 1000, TextureFormat.RGB24, false);
                tex.ReadPixels(new Rect(0, 0, 1600, 1000), 0, 0); tex.Apply();
                File.WriteAllBytes(file, tex.EncodeToPNG());
                RenderTexture.active = null; cam.targetTexture = null;
                Object.DestroyImmediate(rt); Object.DestroyImmediate(tex);
            }
            finally { Object.DestroyImmediate(go); }
        }

        private static int Shot(Transform asm, string role, Vector3 viewDir, float distFactor, string dir, string file)
        {
            Bounds b = default; bool any = false;
            Transform target = null;
            if (role != null)
                foreach (var t in asm.GetComponentsInChildren<Transform>(true)) if (t.name == role) { target = t; break; }
            var root = role == null ? asm : target;
            if (root == null) return 0;
            foreach (var r in root.GetComponentsInChildren<Renderer>(false))
            {
                if (r.name.StartsWith("__")) continue;
                if (!any) { b = r.bounds; any = true; } else b.Encapsulate(r.bounds);
            }
            if (!any) return 0;
            var go = new GameObject("__snapshot_cam");
            try
            {
                var cam = go.AddComponent<Camera>();
                cam.fieldOfView = 30f; cam.nearClipPlane = 0.01f; cam.farClipPlane = 50f;
                cam.clearFlags = CameraClearFlags.SolidColor; cam.backgroundColor = new Color(0.16f, 0.18f, 0.21f);
                float size = b.extents.magnitude;
                cam.transform.position = b.center + viewDir.normalized * size * distFactor / Mathf.Tan(15f * Mathf.Deg2Rad) * 0.5f;
                cam.transform.LookAt(b.center);
                var rt = new RenderTexture(1600, 1000, 24) { antiAliasing = 4 };
                cam.targetTexture = rt;
                cam.Render();
                RenderTexture.active = rt;
                var tex = new Texture2D(1600, 1000, TextureFormat.RGB24, false);
                tex.ReadPixels(new Rect(0, 0, 1600, 1000), 0, 0); tex.Apply();
                File.WriteAllBytes(Path.Combine(dir, file), tex.EncodeToPNG());
                RenderTexture.active = null; cam.targetTexture = null;
                Object.DestroyImmediate(rt); Object.DestroyImmediate(tex);
                return 1;
            }
            finally { Object.DestroyImmediate(go); }
        }
    }
}
