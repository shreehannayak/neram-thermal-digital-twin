using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using Neram.Unity;
using UnityEditor;
using UnityEngine;

namespace Neram.EditorTools
{
    /// <summary>
    /// CAD renders R01-R07 of the Team Implementation Plan (section U) from the Unity viewer scene, 1920x1080, into
    /// &lt;workspace&gt;/docs/evidence/cad_renders/. Exploded views (R04, R05) move the module layers along the module's
    /// local +Y by ModuleView.DefaultExplode / FootExplode (x1.4) for the shot and put them back afterwards. For every
    /// exploded part the screen position is written to &lt;id&gt;_labels.json so the layer names can be drawn on the image.
    /// R08 (sensor-pocket section) needs a cutting plane and is drawn outside Unity (tools/render_section.py).
    /// </summary>
    public static class NeramRenders
    {
        private const int W = 1920, H = 1080;

        [MenuItem("NERAM/CAD/Render plan renders R01-R07", priority = 23)]
        public static void Menu() => EditorUtility.DisplayDialog("NERAM CAD", RenderAll(), "OK");

        public static string RenderAll()
        {
            var asm = GameObject.Find(SceneNames.Assembly);
            if (asm == null) return "NERAM_Assembly not found";
            var dir = Path.GetFullPath(Path.Combine(Application.dataPath, "..", "..", "docs", "evidence", "cad_renders"));
            Directory.CreateDirectory(dir);
            var sb = new StringBuilder();
            Shot(dir, "R01_full_scene", new Vector3(1.55f, 1.25f, -1.65f), new Vector3(0f, 0.0f, -0.2f), 40f, Vector3.up, null, null, sb);
            Shot(dir, "R02_hand_module_iso", new Vector3(1.00f, 0.30f, 0.30f), new Vector3(0.79f, 0.055f, 0.53f), 26f, Vector3.up, null, null, sb);
            Shot(dir, "R03_foot_module_iso", new Vector3(0.50f, 0.22f, -1.20f), new Vector3(0.12f, 0.10f, -0.84f), 30f, Vector3.up, null, null, sb);
            Shot(dir, "R04_hand_module_exploded", new Vector3(0.86f, 0.38f, 0.20f), new Vector3(0.79f, 0.155f, 0.53f), 33f, Vector3.up, asm.transform.Find("Left_Hand_Module"), ModuleView.DefaultExplode, sb);
            Shot(dir, "R05_foot_module_exploded", new Vector3(0.78f, 0.26f, -1.18f), new Vector3(0.12f, 0.12f, -0.96f), 30f, Vector3.up, asm.transform.Find("Left_Foot_Module"), ModuleView.DefaultExplode, sb);
            Shot(dir, "R06_controller_front_ports", new Vector3(0.80f, 0.02f, -0.86f), new Vector3(0.34f, -0.04f, -0.55f), 26f, Vector3.up, null, null, sb);
            var hidden = HideOverhead();
            try { Shot(dir, "R07_cable_routing_top", new Vector3(0.0f, 2.4f, -0.16f), new Vector3(0.0f, 0.0f, -0.15f), 50f, Vector3.forward, null, null, sb); }
            finally { foreach (var r in hidden) r.enabled = true; }
            return sb.ToString();
        }

        /// <summary>Top view only: switch off ceiling, laminar canopy, booms and light heads so the camera sees the table.</summary>
        private static List<Renderer> HideOverhead()
        {
            var keys = new[] { "Ceiling", "Laminar", "Boom", "Light_Head", "Surgical_Light", "Lamp" };
            var off = new List<Renderer>();
            foreach (var r in Object.FindObjectsByType<Renderer>(FindObjectsSortMode.None))
            {
                if (!r.enabled) continue;
                var n = r.gameObject.name + "|" + (r.transform.parent != null ? r.transform.parent.name : "") + "|" + (r.sharedMaterial != null ? r.sharedMaterial.name : "");
                bool hit = false;
                foreach (var k in keys) if (n.IndexOf(k, System.StringComparison.OrdinalIgnoreCase) >= 0) { hit = true; break; }
                if (!hit && r.bounds.min.y > 1.9f) hit = true;   // anything wholly above 1.9 m
                if (hit) { r.enabled = false; off.Add(r); }
            }
            return off;
        }

        private static void Shot(string dir, string id, Vector3 eye, Vector3 target, float fov, Vector3 up, Transform explodeRoot,
                                 Dictionary<string, float> explode, StringBuilder sb)
        {
            var moved = new List<(Transform t, Vector3 p)>();
            var labels = new List<string>();
            var go = new GameObject("__render_cam");
            try
            {
                var cam = go.AddComponent<Camera>();
                cam.fieldOfView = fov; cam.nearClipPlane = 0.005f; cam.farClipPlane = 60f;
                cam.clearFlags = CameraClearFlags.SolidColor; cam.backgroundColor = new Color(0.16f, 0.18f, 0.21f);
                cam.transform.position = eye; cam.transform.LookAt(target, up);
                cam.aspect = (float)W / H;
                if (explodeRoot != null)
                {
                    var prefix = explodeRoot.name.Contains("Hand") ? (explodeRoot.name.StartsWith("Left") ? "CH1_" : "CH2_") : (explodeRoot.name.StartsWith("Left") ? "CH3_" : "CH4_");
                    foreach (Transform c in explodeRoot)
                    {
                        if (!c.name.StartsWith(prefix)) continue;
                        var part = c.name.Substring(prefix.Length);
                        var key = part.StartsWith("Strap") || part.StartsWith("Hook") ? "Strap" : part;
                        if (!explode.TryGetValue(key, out var off)) continue;
                        moved.Add((c, c.localPosition));
                        c.localPosition += Vector3.up * off * 1.4f / Mathf.Max(1e-6f, explodeRoot.lossyScale.y);
                    }
                    // Label anchors from a silhouette pass: each exploded part is rendered alone (layer 31) at 1/4 size and
                    // the anchor is the silhouette pixel nearest its centroid, so the dot always sits on what the camera sees.
                    const int q = 4; int w4 = W / q, h4 = H / q;
                    var mrt = new RenderTexture(w4, h4, 24); var mtex = new Texture2D(w4, h4, TextureFormat.RGB24, false);
                    var oldMask = cam.cullingMask;
                    foreach (var (t, _) in moved)
                    {
                        var r = t.GetComponent<Renderer>();
                        if (r == null || !r.enabled) continue;
                        int oldLayer = t.gameObject.layer; t.gameObject.layer = 31;
                        cam.cullingMask = 1 << 31; cam.backgroundColor = Color.black; cam.targetTexture = mrt;
                        cam.Render();
                        RenderTexture.active = mrt; mtex.ReadPixels(new Rect(0, 0, w4, h4), 0, 0); mtex.Apply(); RenderTexture.active = null;
                        cam.targetTexture = null; t.gameObject.layer = oldLayer;
                        var px = mtex.GetPixels32(); double sx = 0, sy = 0; int cnt = 0;
                        for (int i = 0; i < px.Length; i++) if (px[i].r + px[i].g + px[i].b > 6) { sx += i % w4; sy += i / w4; cnt++; }
                        if (cnt == 0) continue;
                        float cx = (float)(sx / cnt), cy = (float)(sy / cnt), bx = cx, by = cy, bd = float.MaxValue;
                        for (int i = 0; i < px.Length; i++)
                        {
                            if (px[i].r + px[i].g + px[i].b <= 6) continue;
                            float dx = i % w4 - cx, dy = i / w4 - cy, dd = dx * dx + dy * dy;
                            if (dd < bd) { bd = dd; bx = i % w4; by = i / w4; }
                        }
                        labels.Add(string.Format(CultureInfo.InvariantCulture, "{{\"name\":\"{0}\",\"x\":{1:0.0},\"y\":{2:0.0}}}", t.name, (bx + 0.5f) * q, H - (by + 0.5f) * q));
                    }
                    cam.cullingMask = oldMask; cam.backgroundColor = new Color(0.16f, 0.18f, 0.21f);
                    Object.DestroyImmediate(mrt); Object.DestroyImmediate(mtex);
                }
                var rt = new RenderTexture(W, H, 24) { antiAliasing = 8 };
                cam.targetTexture = rt;
                cam.Render();
                RenderTexture.active = rt;
                var tex = new Texture2D(W, H, TextureFormat.RGB24, false);
                tex.ReadPixels(new Rect(0, 0, W, H), 0, 0); tex.Apply();
                File.WriteAllBytes(Path.Combine(dir, id + ".png"), tex.EncodeToPNG());
                RenderTexture.active = null; cam.targetTexture = null;
                Object.DestroyImmediate(rt); Object.DestroyImmediate(tex);
                if (labels.Count > 0) File.WriteAllText(Path.Combine(dir, id + "_labels.json"), "[" + string.Join(",", labels) + "]");
                sb.AppendLine("ok " + id + (labels.Count > 0 ? " (" + labels.Count + " labels)" : ""));
            }
            finally
            {
                foreach (var (t, p) in moved) t.localPosition = p;   // put the layers back
                Object.DestroyImmediate(go);
            }
        }
    }
}
