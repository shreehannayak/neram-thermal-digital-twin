using System.Collections.Generic;
using UnityEngine;

namespace Neram.Unity
{
    /// <summary>
    /// ILLUSTRATIVE oxygen flow: glowing particles travel along fixed paths. External (always visible): humidifier ->
    /// tubing -> face mask, a steady stream. Internal (child of Illustrative_Vessels, so it shows only in the Internal
    /// view): mask -> pharynx -> trachea -> bronchi, moving in with each "breath" and drifting back out, while the lungs
    /// swell slightly. The breath period is a fixed visual constant shared with the monitor's respiration trace; nothing
    /// here is a measured or modelled gas flow, oxygen concentration or respiratory rate. Unscaled real time.
    /// </summary>
    [DisallowMultipleComponent]
    public sealed class AirflowAnimator : MonoBehaviour
    {
        public Material particleMaterial;
        public bool breathing;                    // internal paths: in on inspiration, out on expiration
        public float breathSeconds = 4.2f;
        public float speed = 0.16f;               // metres of path per second (visual)
        public float spacing = 0.045f;            // metres between particles
        public float particleSize = 0.0075f;
        public Transform[] lungs;
        [SerializeField, HideInInspector] private float[] _flat;     // concatenated NERAM_Assembly-local points
        [SerializeField, HideInInspector] private int[] _counts;

        private sealed class Path { public Vector3[] P; public float[] Cum; public float L; public readonly List<Transform> Dots = new List<Transform>(); }
        private readonly List<Path> _paths = new List<Path>();
        private Vector3[] _lungBase;
        private float _offset;

        public void Setup(Material mat, List<Vector3[]> paths, bool breathe, float breathS, Transform[] lungTransforms)
        {
            particleMaterial = mat;
            breathing = breathe;
            if (breathS > 0.5f) breathSeconds = breathS;
            lungs = lungTransforms;
            var flat = new List<float>();
            var counts = new List<int>();
            foreach (var p in paths)
            {
                counts.Add(p.Length);
                foreach (var v in p) { flat.Add(v.x); flat.Add(v.y); flat.Add(v.z); }
            }
            _flat = flat.ToArray();
            _counts = counts.ToArray();
        }

        private void Start()
        {
            var asm = GameObject.Find(SceneNames.Assembly);
            var toWorld = asm != null ? asm.transform.localToWorldMatrix : Matrix4x4.identity;
            int k = 0;
            if (_counts != null)
                foreach (var n in _counts)
                {
                    var path = new Path { P = new Vector3[n], Cum = new float[n] };
                    for (int i = 0; i < n; i++, k += 3) path.P[i] = toWorld.MultiplyPoint3x4(new Vector3(_flat[k], _flat[k + 1], _flat[k + 2]));
                    for (int i = 1; i < n; i++) path.Cum[i] = path.Cum[i - 1] + Vector3.Distance(path.P[i - 1], path.P[i]);
                    path.L = path.Cum[n - 1];
                    int dots = Mathf.Clamp(Mathf.RoundToInt(path.L / spacing), 2, 60);
                    for (int d = 0; d < dots; d++)
                    {
                        var go = GameObject.CreatePrimitive(PrimitiveType.Sphere);
                        go.name = "__air";
                        var col = go.GetComponent<Collider>();
                        if (col != null) Destroy(col);
                        go.transform.SetParent(transform, true);
                        go.transform.localScale = Vector3.one * particleSize / Mathf.Max(1e-4f, transform.lossyScale.x);
                        var r = go.GetComponent<Renderer>();
                        if (particleMaterial != null) r.sharedMaterial = particleMaterial;
                        r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                        path.Dots.Add(go.transform);
                    }
                    _paths.Add(path);
                }
            if (lungs != null)
            {
                _lungBase = new Vector3[lungs.Length];
                for (int i = 0; i < lungs.Length; i++) if (lungs[i] != null) _lungBase[i] = lungs[i].localScale;
            }
        }

        private static Vector3 At(Path p, float s)
        {
            s = Mathf.Clamp(s, 0f, p.L);
            int i = 1;
            while (i < p.P.Length - 1 && p.Cum[i] < s) i++;
            float seg = p.Cum[i] - p.Cum[i - 1];
            return Vector3.Lerp(p.P[i - 1], p.P[i], seg > 1e-6f ? (s - p.Cum[i - 1]) / seg : 0f);
        }

        private void Update()
        {
            float t = Time.unscaledTime, dt = Mathf.Min(Time.unscaledDeltaTime, 0.1f);
            float phase = (t % breathSeconds) / breathSeconds;          // 0..0.4 inspiration, 0.4..1 expiration
            float v = !breathing ? speed : (phase < 0.4f ? speed * 1.6f * Mathf.Sin(Mathf.PI * phase / 0.4f) : -speed * 0.55f * Mathf.Sin(Mathf.PI * (phase - 0.4f) / 0.6f));
            _offset += v * dt;
            foreach (var p in _paths)
            {
                int n = p.Dots.Count;
                float gap = p.L / n;
                for (int d = 0; d < n; d++)
                {
                    float s = Mathf.Repeat(_offset + d * gap, p.L);
                    p.Dots[d].position = At(p, s);
                    // fade in near the start and out near the end of each path
                    float e = Mathf.Min(s, p.L - s) / Mathf.Max(0.02f, p.L * 0.08f);
                    p.Dots[d].localScale = Vector3.one * (particleSize / Mathf.Max(1e-4f, transform.lossyScale.x)) * Mathf.Clamp01(e);
                }
            }
            if (lungs != null && _lungBase != null)
            {
                float fill = phase < 0.4f ? Mathf.SmoothStep(0f, 1f, phase / 0.4f) : 1f - Mathf.SmoothStep(0f, 1f, (phase - 0.4f) / 0.6f);
                for (int i = 0; i < lungs.Length; i++)
                    if (lungs[i] != null) lungs[i].localScale = _lungBase[i] * (1f + 0.045f * fill);
            }
        }
    }
}
