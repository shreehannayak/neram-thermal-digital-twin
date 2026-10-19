using System.Text;
using UnityEditor;
using UnityEngine;

namespace Neram.EditorTools
{
    /// <summary>Diagnostic dump of the surgeon / instrument renderers (automation job "diag").</summary>
    public static class NeramDiag
    {
        public static string Run()
        {
            var sb = new StringBuilder();
            foreach (var r in Object.FindObjectsByType<Renderer>(FindObjectsInactive.Include, FindObjectsSortMode.None))
            {
                var n = r.gameObject.name;
                if (!(n.StartsWith("Surgeon") || n.StartsWith("Instr_") || n.StartsWith("Trolley_") || n.Contains("Cap") || n.Contains("Hair"))) continue;
                var mf = r.GetComponent<MeshFilter>();
                var m = r.sharedMaterial;
                string path = n; var t = r.transform.parent; while (t != null) { path = t.name + "/" + path; t = t.parent; }
                sb.AppendLine(path + " active=" + r.gameObject.activeInHierarchy + " en=" + r.enabled
                    + " mesh=" + (mf && mf.sharedMesh ? mf.sharedMesh.name + "(" + mf.sharedMesh.vertexCount + ")" : "none")
                    + " b=" + r.bounds.center.ToString("F2") + "/" + r.bounds.size.ToString("F2")
                    + " scale=" + r.transform.lossyScale.ToString("F2")
                    + " mat=" + (m ? m.name + " sh=" + m.shader.name + " q=" + m.renderQueue
                        + " surf=" + (m.HasProperty("_Surface") ? m.GetFloat("_Surface") : -1)
                        + " cull=" + (m.HasProperty("_Cull") ? m.GetFloat("_Cull") : -1)
                        + " clip=" + (m.HasProperty("_AlphaClip") ? m.GetFloat("_AlphaClip") : -1)
                        + " cut=" + (m.HasProperty("_Cutoff") ? m.GetFloat("_Cutoff") : -1)
                        + " a=" + (m.HasProperty("_BaseColor") ? m.GetColor("_BaseColor").a : -1)
                        + " base=" + (m.HasProperty("_BaseMap") && m.GetTexture("_BaseMap") ? m.GetTexture("_BaseMap").name : "-")
                        + " kw=" + string.Join(",", m.shaderKeywords) : "none"));
            }
            return sb.ToString();
        }
    }
}
