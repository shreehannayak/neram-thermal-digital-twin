using UnityEngine;

namespace Neram.Unity
{
    /// <summary>
    /// Conceptual droplet in the IV drip chamber. DEMONSTRATION PROP: the drop period is a fixed visual constant, not an
    /// infusion rate, and nothing here represents patient fluid balance or comes from the replay. Each cycle a drop
    /// forms at the drip orifice, detaches, falls and splashes into the fluid in the chamber. Runs on unscaled real time
    /// (18 Oct 2026: it used to follow replay time, which froze it when paused and made it race at 60x).
    /// </summary>
    [DisallowMultipleComponent]
    public sealed class IvDripAnimator : MonoBehaviour
    {
        public Material dropMaterial;
        public float fallDistance = 0.034f;
        [Tooltip("Seconds between conceptual drops (visual constant, not an infusion rate).")]
        public float period = 1.4f;
        private Transform _drop, _splash;
        private Renderer _splashR;

        private void Start()
        {
            _drop = MakeBlob("__iv_drop");
            _splash = MakeBlob("__iv_splash");
            _splashR = _splash.GetComponent<Renderer>();
            Place(0f);
        }

        private Transform MakeBlob(string name)
        {
            var go = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            go.name = name;
            var col = go.GetComponent<Collider>();
            if (col != null) Destroy(col);
            go.transform.SetParent(transform, false);
            var r = go.GetComponent<Renderer>();
            if (dropMaterial != null) r.sharedMaterial = dropMaterial;
            r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            return go.transform;
        }

        /// <summary>Kept for callers; the drop no longer follows replay time.</summary>
        public void SetReplayTime(double t) { }

        private void Update() => Place(Time.unscaledTime);

        private void Place(float t)
        {
            if (_drop == null) return;
            float phase = (t % period) / period;
            const float form = 0.62f, land = 0.84f;
            if (phase < form)
            {   // drop swells at the orifice
                float g = Mathf.SmoothStep(0.25f, 1f, phase / form);
                _drop.localScale = new Vector3(0.0055f, 0.0065f + 0.0015f * g, 0.0055f) * g;
                _drop.localPosition = new Vector3(0f, -0.0035f * g, 0f);
            }
            else if (phase < land)
            {   // detaches and falls with constant acceleration, slightly stretched
                float u = (phase - form) / (land - form);
                _drop.localScale = new Vector3(0.0050f, 0.0080f, 0.0050f);
                _drop.localPosition = new Vector3(0f, -0.0035f - u * u * (fallDistance - 0.0035f), 0f);
            }
            else _drop.localScale = Vector3.zero;
            if (_splash != null)
            {   // ripple on the fluid surface: flat disc that widens and thins out
                bool on = phase >= land;
                _splashR.enabled = on;
                if (on)
                {
                    float s = (phase - land) / (1f - land);
                    _splash.localPosition = new Vector3(0f, -fallDistance, 0f);
                    _splash.localScale = new Vector3(0.004f + 0.012f * s, 0.0016f * (1f - s), 0.004f + 0.012f * s);
                }
            }
        }
    }
}
