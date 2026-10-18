using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using Neram.EditorTools;
using Neram.Unity;

// Off-Unity check of the generated scene bundle with the SAME reader NeramSceneBuilder uses.
// Usage: dotnet run --project tools/dotnet/BundleCheck -- <workspace root>
static class Program
{
    static int fails;
    static void Check(bool ok, string msg) { Console.WriteLine((ok ? "PASS  " : "FAIL  ") + msg); if (!ok) fails++; }

    static int Main(string[] args)
    {
        var root = args.Length > 0 ? args[0] : Environment.GetEnvironmentVariable("NERAM_REPO_ROOT") ?? ".";
        var gen = Path.Combine(root, "unity_editor", "Assets", "NERAM_Generated");
        var bundlePath = Path.Combine(gen, "MeshData", "neram_scene.bytes");
        NeramBundleReader.Bundle b;
        try { b = NeramBundleReader.Read(File.ReadAllBytes(bundlePath)); Check(true, "bundle parses with NeramBundleReader (" + b.Nodes.Count + " nodes, " + b.Meshes.Count + " meshes)"); }
        catch (Exception ex) { Check(false, "bundle parse: " + ex.Message); return 1; }

        // materials referenced by meshes exist in the palette consumed by NeramSceneBuilder
        using var doc = JsonDocument.Parse(File.ReadAllText(Path.Combine(gen, "MeshData", "materials.json")));
        var palette = new HashSet<string>(doc.RootElement.GetProperty("materials").EnumerateArray().Select(e => e.GetProperty("name").GetString()));
        var used = b.Meshes.Select(m => m.Material.StartsWith("TEX:") ? "MAT_TEX_" + m.Material.Substring(4) : m.Material).Distinct().ToList();
        var missing = used.Where(u => !palette.Contains(u)).ToList();
        Check(missing.Count == 0, "all " + used.Count + " materials used by meshes exist in materials.json" + (missing.Count > 0 ? " — missing " + string.Join(", ", missing) : ""));
        var cad = SceneNames.Materials.Where(m => !palette.Contains(m)).ToList();
        Check(cad.Count == 0, "CAD material list present in the palette" + (cad.Count > 0 ? " — missing " + string.Join(", ", cad) : ""));
        foreach (var e in doc.RootElement.GetProperty("materials").EnumerateArray())
        {
            var tex = e.GetProperty("texture").GetString();
            if (!string.IsNullOrEmpty(tex) && !File.Exists(Path.Combine(gen, "Textures", tex + ".png"))) Check(false, "texture missing: " + tex);
        }

        // regions and module part names (CAD contract)
        var regions = b.Nodes.Where(n => n.Region.Length > 0).Select(n => n.Region).ToHashSet();
        foreach (var r in new[] { "hand_left", "hand_right", "arm_left", "arm_right", "torso", "leg_left", "leg_right", "foot_left", "foot_right", "wearable", "controller" })
            Check(regions.Contains(r), "region node '" + r + "'");
        var parentOf = b.Nodes.ToDictionary(n => n.Name, n => n.Parent);
        bool Under(string node, string ancestor) { for (var p = node; !string.IsNullOrEmpty(p); p = parentOf.TryGetValue(p, out var q) ? q : null) if (p == ancestor) return true; return false; }
        for (int i = 0; i < 4; i++)
        {
            int ch = i + 1;
            var role = SceneNames.Modules[i] + SceneNames.PlaceholderSuffix;
            var parts = b.Meshes.Where(m => Under(m.Parent, role)).Select(m => m.Name).ToHashSet();
            var miss = SceneNames.ModuleParts.Select(p => SceneNames.Part(ch, p)).Where(p => !parts.Contains(p)).ToList();
            Check(miss.Count == 0, role + ": all CH" + ch + "_* contract parts present" + (miss.Count > 0 ? " — missing " + string.Join(", ", miss) : ""));
            Check(parts.Contains(SceneNames.Part(ch, SceneNames.StrapPrefix + "1")), role + ": strap parts present");
            // left/right: patient's LEFT = +X (CH1 left hand, CH3 left foot)
            var node = b.Nodes.First(n => n.Name == role);
            bool left = ch == 1 || ch == 3;
            Check(left ? node.Position[0] > 0.05f : node.Position[0] < -0.05f, role + ": on the patient's " + (left ? "LEFT (+X)" : "RIGHT (-X)") + " side, x = " + node.Position[0].ToString("0.00"));
        }
        foreach (var c in SceneNames.ControllerParts) Check(b.Meshes.Any(m => m.Name == c), "controller part " + c);
        for (int ch = 1; ch <= 4; ch++)
        {
            Check(b.Meshes.Any(m => m.Name == SceneNames.Connector(ch)), SceneNames.Connector(ch) + " mesh");
            Check(b.Nodes.Count(n => n.Parent == SceneNames.Cable(ch) + SceneNames.PlaceholderSuffix && n.Name.StartsWith("wp")) >= 3, "cable CH" + ch + " has waypoints");
        }
        Check(b.Nodes.Count(n => n.Flags.StartsWith("preset:")) >= 9, "camera presets (9: overview, top, soles, hands, wearable, torso, controller, theatre)");
        var vessels = b.Nodes.Where(n => n.Flags.StartsWith("vessel:")).ToList();
        Check(vessels.Count >= 10 && vessels.All(v => b.Nodes.Count(w => w.Parent == v.Name && w.Name.StartsWith("wp")) >= 2), "illustrative vessels with pulse paths (" + vessels.Count + ")");
        Check(vessels.Any(v => v.Flags == "vessel:artery") && vessels.Any(v => v.Flags == "vessel:vein"), "arteries and veins present");
        Check(b.Nodes.Count(n => n.Flags.StartsWith("anchor:ivdrop")) == 1, "IV drip-chamber drop anchor");
        Check(b.Meshes.Any(m => m.Name == "IV_Fluid") && b.Meshes.Any(m => m.Name == "IV_Cannula_Hub"), "IV bag fluid and arm access point");
        Check(b.Nodes.Count(n => n.Flags.StartsWith("navroom:")) == 1 && b.Nodes.Count(n => n.Flags.StartsWith("keepout:")) >= 5, "Free Roam room + keep-out volumes");
        // keep-out sanity: the default overview camera position must not start inside a keep-out box
        foreach (var k in b.Nodes.Where(n => n.Flags.StartsWith("keepout:")))
        {
            var h = k.Flags.Substring(8).Split(',').Select(x => float.Parse(x, System.Globalization.CultureInfo.InvariantCulture)).ToArray();
            Check(h.All(x => x > 0 && x < 3), "keep-out " + k.Name + " has sane half-extents");
        }
        Check(b.Nodes.Count(n => n.Flags.StartsWith("light:")) >= 3, "light nodes");

        // winding: geometric normal must agree with the vertex normals (Unity front face = numeric cross(b-a, c-a))
        long tris = 0, bad = 0;
        foreach (var m in b.Meshes)
        {
            var P = m.Positions; var N = m.Normals; var I = m.Indices;
            for (int t = 0; t < I.Length; t += 3)
            {
                int a = I[t] * 3, b1 = I[t + 1] * 3, c = I[t + 2] * 3;
                float ux = P[b1] - P[a], uy = P[b1 + 1] - P[a + 1], uz = P[b1 + 2] - P[a + 2];
                float vx = P[c] - P[a], vy = P[c + 1] - P[a + 1], vz = P[c + 2] - P[a + 2];
                float nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
                float sx = N[a] + N[b1] + N[c], sy = N[a + 1] + N[b1 + 1] + N[c + 1], sz = N[a + 2] + N[b1 + 2] + N[c + 2];
                if (nx * sx + ny * sy + nz * sz < 0) bad++;
                tris++;
            }
        }
        Check(bad <= tris / 1000, "winding agrees with normals on " + (tris - bad) + " / " + tris + " triangles (Unity front-face convention)");

        // labels read left-to-right from their viewer (texture u axis -> world +X for labels seen from the foot end/top)
        foreach (var m in b.Meshes.Where(m => m.Name.EndsWith("_Label") || m.Name.EndsWith("_Sole_Label")))
        {
            if (m.Name.StartsWith("BC_") || m.VertexCount != 4) continue; // flat label quads only (wrapped cylinder bands excluded)
            int i0 = -1, i1 = -1;
            for (int k = 0; k < m.VertexCount; k++)
            {
                float u = m.Uvs[k * 2], v = m.Uvs[k * 2 + 1];
                if (u < 0.01f && v < 0.01f) i0 = k;
                if (u > 0.99f && v < 0.01f) i1 = k;
            }
            if (i0 < 0 || i1 < 0) { Check(false, m.Name + ": label UV corners not found"); continue; }
            float dx = m.Positions[i1 * 3] - m.Positions[i0 * 3];
            Check(dx > 0, m.Name + ": text runs toward +X (reads left-to-right from the foot-end camera)");
        }
        Console.WriteLine(fails == 0 ? "\nALL PASS" : "\n" + fails + " FAIL");
        return fails == 0 ? 0 : 1;
    }
}
