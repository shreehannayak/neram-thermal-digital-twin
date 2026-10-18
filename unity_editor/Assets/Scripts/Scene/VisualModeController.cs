using System;
using System.Collections.Generic;
using Neram.Core;
using UnityEngine;

namespace Neram.Unity
{
    public enum VisualMode { External, Internal, Thermal, Exploded }

    /// <summary>
    /// The four visualisation modes. All animations are driven by REPLAY time (paused replay = frozen animation); only
    /// the cross-fade between modes uses wall-clock time.
    ///  - External: the patient as generated.
    ///  - Internal: body surfaces cross-fade to translucent "ghost" materials and the ILLUSTRATIVE vessel network appears
    ///    with pulses moving along it. Not patient-specific anatomy, flow, velocity or perfusion.
    ///  - Thermal: body surfaces are tinted UNIFORMLY with the single patient-level temperature signal (ThermalScale).
    ///    No limb or organ receives a temperature of its own because the replay contains none. Warming devices keep
    ///    their replay-driven heater glow.
    ///  - Exploded: one warming module separates its construction layers (ModuleView); Reset returns it to assembled.
    /// </summary>
    [DefaultExecutionOrder(90)]
    public sealed class VisualModeController : MonoBehaviour
    {
        public NeramAssemblyBinder assembly;
        public Material skinGhost, gownGhost, drapeGhost, thermalMaterial, pulseMaterial;
        [Tooltip("Illustrative pulse travel speed along the vessel paths (metres of path per replay second). Not a flow rate.")]
        public float pulseSpeed = 0.08f;
        public int pulsesPerVessel = 3;
        public float fadeSeconds = 0.6f;

        private sealed class BodyRenderer
        {
            public Renderer R;
            public Material Original, Ghost;
            public Color OriginalColor, GhostColor;
        }

        private sealed class VesselPath
        {
            public Vector3[] Points;
            public float[] Cum;
            public float Length;
            public readonly List<Transform> Pulses = new List<Transform>();
        }

        private static readonly int BaseColorId = Shader.PropertyToID("_BaseColor");
        private readonly List<BodyRenderer> _body = new List<BodyRenderer>();
        private readonly List<VesselPath> _vessels = new List<VesselPath>();
        private GameObject _vesselRoot;
        private MaterialPropertyBlock _mpb;
        private double _replayTime;
        private double _patientSignal = double.NaN;
        private float _fade = 1f; // 0 = previous mode, 1 = current mode fully applied
        private VisualMode _from = VisualMode.External;
        private bool _ready;

        public VisualMode Mode { get; private set; } = VisualMode.External;
        public int ExplodedChannel { get; private set; }
        public event Action<VisualMode> ModeChanged;

        private void Start() => Collect();

        public void Collect()
        {
            _mpb = new MaterialPropertyBlock();
            if (assembly == null) assembly = FindAnyObjectByType<NeramAssemblyBinder>();
            _body.Clear();
            var man = GameObject.Find("Patient_Mannequin_PLACEHOLDER");
            var cadMan = GameObject.Find("Patient_Mannequin");
            var root = cadMan != null ? cadMan : man;
            if (root != null)
            {
                foreach (var r in root.GetComponentsInChildren<Renderer>(true))
                {
                    var m = r.sharedMaterial;
                    if (m == null || r.gameObject.name.StartsWith("__")) continue;
                    Material ghost = m.name.StartsWith("MAT_Gown") ? gownGhost : m.name.StartsWith("MAT_Drape") ? drapeGhost : skinGhost;
                    if (ghost == null) continue;
                    _body.Add(new BodyRenderer
                    {
                        R = r, Original = m, Ghost = ghost,
                        OriginalColor = m.HasProperty(BaseColorId) ? m.GetColor(BaseColorId) : Color.white,
                        GhostColor = ghost.HasProperty(BaseColorId) ? ghost.GetColor(BaseColorId) : new Color(1, 1, 1, 0.15f),
                    });
                }
            }
            _vessels.Clear();
            _vesselRoot = null;
            foreach (var v in FindObjectsByType<NeramVessel>(FindObjectsInactive.Include, FindObjectsSortMode.None))
            {
                if (_vesselRoot == null && v.transform.parent != null) _vesselRoot = v.transform.parent.gameObject;
                var pts = v.Waypoints();
                if (pts.Length < 2) continue;
                var path = new VesselPath { Points = pts, Cum = new float[pts.Length] };
                for (int i = 1; i < pts.Length; i++) path.Cum[i] = path.Cum[i - 1] + Vector3.Distance(pts[i - 1], pts[i]);
                path.Length = path.Cum[pts.Length - 1];
                for (int k = 0; k < pulsesPerVessel; k++)
                {
                    var go = GameObject.CreatePrimitive(PrimitiveType.Sphere);
                    go.name = "__pulse";
                    var col = go.GetComponent<Collider>();
                    if (col != null) Destroy(col);
                    go.transform.SetParent(v.transform, false);
                    go.transform.localScale = Vector3.one * (v.kind == "artery" ? 0.014f : 0.012f);
                    var mr = go.GetComponent<Renderer>();
                    if (pulseMaterial != null) mr.sharedMaterial = pulseMaterial;
                    mr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                    path.Pulses.Add(go.transform);
                }
                _vessels.Add(path);
            }
            if (_vesselRoot != null) _vesselRoot.SetActive(false);
            _ready = true;
        }

        /// <summary>Replay time in seconds (NaN when no replay is loaded). Drives the pulse animation.</summary>
        public void SetReplayTime(double t) => _replayTime = double.IsNaN(t) ? 0 : t;

        /// <summary>The single patient-level temperature signal at the current frame (NaN = no observation).</summary>
        public void SetPatientSignal(double celsius) => _patientSignal = celsius;

        public void SetMode(VisualMode mode, int explodeChannel = 0)
        {
            if (!_ready) Collect();
            if (mode == Mode && (mode != VisualMode.Exploded || explodeChannel == ExplodedChannel)) return;
            _from = Mode;
            Mode = mode;
            _fade = 0f;
            if (mode == VisualMode.Exploded) Explode(explodeChannel > 0 ? explodeChannel : (ExplodedChannel > 0 ? ExplodedChannel : 3));
            else Explode(0);
            if (mode == VisualMode.Internal || _from == VisualMode.Internal) SetVesselsVisible(mode == VisualMode.Internal);
            // material targets
            foreach (var b in _body)
            {
                if (b.R == null) continue;
                if (mode == VisualMode.Internal) b.R.sharedMaterial = b.Ghost;
                else if (mode == VisualMode.Thermal) b.R.sharedMaterial = thermalMaterial != null ? thermalMaterial : b.Original;
                else if (_from != VisualMode.Internal && _from != VisualMode.Thermal) b.R.sharedMaterial = b.Original;
            }
            ModeChanged?.Invoke(mode);
        }

        /// <summary>Separate the layers of one module (1..4); 0 reassembles all.</summary>
        public void Explode(int channel)
        {
            ExplodedChannel = channel;
            if (assembly == null) return;
            for (int i = 0; i < 4; i++)
            {
                var m = assembly.Modules[i];
                if (m != null) m.SetExploded(channel == i + 1);
            }
        }

        private void SetVesselsVisible(bool on)
        {
            if (_vesselRoot != null) _vesselRoot.SetActive(on);
        }

        private void LateUpdate()
        {
            if (!_ready) return;
            if (_fade < 1f)
            {
                _fade = Mathf.MoveTowards(_fade, 1f, Time.unscaledDeltaTime / Mathf.Max(0.05f, fadeSeconds));
                if (_fade >= 1f && Mode != VisualMode.Internal && Mode != VisualMode.Thermal)
                    foreach (var b in _body) if (b.R != null) { b.R.sharedMaterial = b.Original; SetColor(b.R, b.OriginalColor); }
            }
            float e = Mathf.SmoothStep(0f, 1f, _fade);
            Color thermal;
            ThermalScale.Color(_patientSignal, out var tr, out var tg, out var tb);
            thermal = new Color((float)tr, (float)tg, (float)tb, 1f);
            foreach (var b in _body)
            {
                if (b.R == null) continue;
                Color c;
                if (Mode == VisualMode.Internal)
                    c = Color.Lerp(new Color(b.GhostColor.r, b.GhostColor.g, b.GhostColor.b, 1f), b.GhostColor, e);
                else if (Mode == VisualMode.Thermal)
                    c = Color.Lerp(_from == VisualMode.Internal ? new Color(b.GhostColor.r, b.GhostColor.g, b.GhostColor.b, 1f) : b.OriginalColor, thermal, e);
                else if (_fade < 1f && _from == VisualMode.Internal)
                    c = Color.Lerp(b.GhostColor, new Color(b.GhostColor.r, b.GhostColor.g, b.GhostColor.b, 1f), e);
                else if (_fade < 1f && _from == VisualMode.Thermal)
                    c = Color.Lerp(thermal, b.OriginalColor, e);
                else continue;
                SetColor(b.R, c);
            }
            if (Mode == VisualMode.Internal) AnimatePulses();
        }

        private void SetColor(Renderer r, Color c)
        {
            r.GetPropertyBlock(_mpb);
            _mpb.SetColor(BaseColorId, c);
            r.SetPropertyBlock(_mpb);
        }

        private void AnimatePulses()
        {
            foreach (var v in _vessels)
            {
                if (v.Length <= 0) continue;
                for (int k = 0; k < v.Pulses.Count; k++)
                {
                    double s = (_replayTime * pulseSpeed + v.Length * k / v.Pulses.Count) % v.Length;
                    v.Pulses[k].position = PointAt(v, (float)s);
                }
            }
        }

        private static Vector3 PointAt(VesselPath v, float s)
        {
            for (int i = 1; i < v.Points.Length; i++)
            {
                if (s > v.Cum[i]) continue;
                float seg = v.Cum[i] - v.Cum[i - 1];
                float u = seg > 1e-6f ? (s - v.Cum[i - 1]) / seg : 0f;
                return Vector3.Lerp(v.Points[i - 1], v.Points[i], u);
            }
            return v.Points[v.Points.Length - 1];
        }
    }
}
