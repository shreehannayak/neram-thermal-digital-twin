using System.Collections.Generic;
using UnityEngine;

namespace Neram.Unity
{
    /// <summary>
    /// Procedural cable: a tube along a Catmull-Rom curve through the waypoint children ("wp0", "wp1", ...).
    /// Used for placeholder cables; CAD cables (Cable_CHn meshes) replace it. Runs in edit mode so the scene looks right.
    /// </summary>
    [ExecuteAlways]
    [RequireComponent(typeof(MeshFilter), typeof(MeshRenderer))]
    public sealed class CableTube : MonoBehaviour
    {
        public float radius = 0.0045f;
        [Range(3, 16)] public int sides = 8;
        [Range(2, 24)] public int samplesPerSegment = 10;

        private Mesh _mesh;
        private readonly List<Vector3> _pts = new List<Vector3>();

        private void OnEnable() => Rebuild();
#if UNITY_EDITOR
        private void OnValidate() => Rebuild();
#endif

        public List<Transform> Waypoints()
        {
            var list = new List<Transform>();
            foreach (Transform c in transform) if (c.name.StartsWith("wp")) list.Add(c);
            list.Sort((a, b) => string.CompareOrdinal(a.name, b.name));
            return list;
        }

        public void Rebuild()
        {
            var wps = Waypoints();
            if (wps.Count < 2) return;
            if (_mesh == null)
            {
                _mesh = new Mesh { name = name + "_tube" };
                _mesh.hideFlags = HideFlags.DontSave;
                GetComponent<MeshFilter>().sharedMesh = _mesh;
            }
            _pts.Clear();
            for (int i = 0; i < wps.Count - 1; i++)
            {
                var p0 = transform.InverseTransformPoint(wps[Mathf.Max(0, i - 1)].position);
                var p1 = transform.InverseTransformPoint(wps[i].position);
                var p2 = transform.InverseTransformPoint(wps[i + 1].position);
                var p3 = transform.InverseTransformPoint(wps[Mathf.Min(wps.Count - 1, i + 2)].position);
                for (int k = 0; k < samplesPerSegment; k++) _pts.Add(CatmullRom(p0, p1, p2, p3, k / (float)samplesPerSegment));
            }
            _pts.Add(transform.InverseTransformPoint(wps[wps.Count - 1].position));

            var verts = new List<Vector3>(_pts.Count * sides);
            var normals = new List<Vector3>(_pts.Count * sides);
            var tris = new List<int>((_pts.Count - 1) * sides * 6);
            Vector3 prevN = Vector3.up;
            for (int i = 0; i < _pts.Count; i++)
            {
                var fwd = (i < _pts.Count - 1 ? _pts[i + 1] - _pts[i] : _pts[i] - _pts[i - 1]).normalized;
                if (fwd == Vector3.zero) fwd = Vector3.forward;
                var n = Vector3.Cross(fwd, Vector3.Cross(prevN, fwd)).normalized;
                if (n == Vector3.zero) n = Vector3.Cross(fwd, Vector3.right).normalized;
                prevN = n;
                var b = Vector3.Cross(fwd, n);
                for (int s = 0; s < sides; s++)
                {
                    float a = s * Mathf.PI * 2 / sides;
                    var dir = n * Mathf.Cos(a) + b * Mathf.Sin(a);
                    verts.Add(_pts[i] + dir * radius);
                    normals.Add(dir);
                }
            }
            for (int i = 0; i < _pts.Count - 1; i++)
                for (int s = 0; s < sides; s++)
                {
                    int a0 = i * sides + s, a1 = i * sides + (s + 1) % sides, b0 = a0 + sides, b1 = a1 + sides;
                    tris.Add(a0); tris.Add(b0); tris.Add(a1);
                    tris.Add(a1); tris.Add(b0); tris.Add(b1);
                }
            _mesh.Clear();
            _mesh.SetVertices(verts);
            _mesh.SetNormals(normals);
            _mesh.SetTriangles(tris, 0);
            _mesh.RecalculateBounds();
        }

        private static Vector3 CatmullRom(Vector3 p0, Vector3 p1, Vector3 p2, Vector3 p3, float t)
        {
            float t2 = t * t, t3 = t2 * t;
            return 0.5f * (2f * p1 + (-p0 + p2) * t + (2f * p0 - 5f * p1 + 4f * p2 - p3) * t2 + (-p0 + 3f * p1 - 3f * p2 + p3) * t3);
        }
    }
}
