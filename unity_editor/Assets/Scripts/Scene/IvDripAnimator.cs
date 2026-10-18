using UnityEngine;

namespace Neram.Unity
{
    /// <summary>
    /// Conceptual droplet in the IV drip chamber. DEMONSTRATION PROP: the drop period is a fixed visual constant, not an
    /// infusion rate, and nothing here represents patient fluid balance. The drop follows REPLAY time (frozen when the
    /// replay is paused or no replay is loaded).
    /// </summary>
    [DisallowMultipleComponent]
    public sealed class IvDripAnimator : MonoBehaviour
    {
        public Material dropMaterial;
        public float fallDistance = 0.034f;
        [Tooltip("Seconds of replay time between conceptual drops (visual constant, not an infusion rate).")]
        public float period = 1.5f;
        private Transform _drop;
        private double _t;

        private void Start()
        {
            var go = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            go.name = "__iv_drop";
            var col = go.GetComponent<Collider>();
            if (col != null) Destroy(col);
            go.transform.SetParent(transform, false);
            go.transform.localScale = new Vector3(0.0045f, 0.006f, 0.0045f);
            var r = go.GetComponent<Renderer>();
            if (dropMaterial != null) r.sharedMaterial = dropMaterial;
            r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            _drop = go.transform;
            Place();
        }

        /// <summary>Replay time in seconds (NaN when no replay is loaded).</summary>
        public void SetReplayTime(double t)
        {
            _t = double.IsNaN(t) ? 0 : t;
            Place();
        }

        private void Place()
        {
            if (_drop == null) return;
            float phase = (float)((_t % period) / period);
            // hang briefly, then fall with constant acceleration
            float fall = phase < 0.55f ? 0f : Mathf.Pow((phase - 0.55f) / 0.45f, 2f) * fallDistance;
            _drop.localPosition = new Vector3(0f, -fall, 0f);
        }
    }
}
