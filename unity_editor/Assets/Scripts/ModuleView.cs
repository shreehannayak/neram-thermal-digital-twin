using System.Collections.Generic;
using Neram.Core;
using UnityEngine;

namespace Neram.Unity
{
    /// <summary>
    /// One warming module (CH1 left hand ... CH4 right foot). Works with placeholder or CAD geometry because it only looks
    /// up the CAD part names (CHn_Heater, CHn_Liner, ...).
    ///  - Heater layer glow follows Heat_i from the replay (0 % = dark). Nothing else drives it.
    ///  - A fault outline (inverted hull) appears when the replay reports a channel fault, hardware cutoff or disconnection.
    ///  - Exploded view separates the layers along the module's local +Y (away from the skin) for hardware inspection.
    /// </summary>
    [DisallowMultipleComponent]
    public sealed class ModuleView : MonoBehaviour
    {
        [Range(1, 4)] public int channel = 1;
        [Tooltip("URP Unlit material with Cull Front, used for the fault outline (MAT_Halo).")]
        public Material haloMaterial;
        [Tooltip("Emission colour at 100 % heating command (HDR). Visual encoding only.")]
        [ColorUsage(false, true)] public Color heatEmission = new Color(2.4f, 0.75f, 0.12f);
        [Tooltip("Outline colours: warning (fault / disconnected) and critical (hardware cutoff / over-temperature).")]
        public Color haloWarning = new Color(0.92f, 0.70f, 0.03f);
        public Color haloCritical = new Color(0.94f, 0.27f, 0.27f);
        [Tooltip("Seconds to ease the glow toward a new value while playing (snaps on seek). Visual only.")]
        public float glowEase = 0.25f;
        [Tooltip("Small amber point light whose intensity follows the replayed heat command (visual cue only; 0 = off).")]
        public float heatLightIntensity = 0.9f;
        public float heatLightRange = 0.28f;
        private Light _heatLight;

        private static readonly int EmissionId = Shader.PropertyToID("_EmissionColor");
        private static readonly int BaseColorId = Shader.PropertyToID("_BaseColor");

        private readonly List<Renderer> _heater = new List<Renderer>();
        private readonly List<GameObject> _halo = new List<GameObject>();
        private readonly List<(Transform t, Vector3 basePos, float offset)> _layers = new List<(Transform, Vector3, float)>();
        private MaterialPropertyBlock _mpb;
        private MaterialPropertyBlock _haloMpb;
        private float _glow, _glowTarget;
        private float _explode, _explodeTarget;
        private bool _built;

        public ChannelView Last { get; private set; }
        public bool HasCadHeater => _heater.Count > 0;
        public IReadOnlyList<(Transform t, Vector3 basePos, float offset)> Layers => _layers;

        /// <summary>Default exploded offsets (metres along local +Y) when CAD exploded_offsets.csv is not provided.
        /// Hand mitts: local +Y points away from the palm surface the mitt rests on.</summary>
        public static readonly Dictionary<string, float> DefaultExplode = new Dictionary<string, float>
        {
            { "Liner", 0.0f }, { "Insulation", 0.025f }, { "Heater", 0.05f }, { "Sensor_A", 0.062f }, { "Sensor_B", 0.062f }, { "Cutoff", 0.07f },
            { "Shell", 0.085f }, { "Cuff", 0.085f }, { "Label_Plate", 0.085f }, { "Label", 0.085f }, { "Strain_Relief", 0.085f },
            { "Strap", 0.12f }, { "Buckle", 0.12f },
        };

        /// <summary>Foot boots: local +Y points out of the sole (plantar direction), so the heated sole stack separates
        /// toward the foot end while the boot upper stays on the foot.</summary>
        public static readonly Dictionary<string, float> FootExplode = new Dictionary<string, float>
        {
            { "Shell", 0.0f }, { "Toe_Cap", 0.0f }, { "Heel_Counter", 0.0f }, { "Collar", 0.0f }, { "Strap", 0.0f }, { "Buckle", 0.0f },
            { "Label_Plate", 0.0f }, { "Label", 0.0f }, { "Cutoff", 0.0f }, { "Strain_Relief", 0.0f },
            { "Liner", 0.02f }, { "Sensor_A", 0.035f }, { "Sensor_B", 0.035f }, { "Heater", 0.05f }, { "Insulation", 0.08f },
            { "Sole_Outsole", 0.11f }, { "Sole_Tread", 0.11f }, { "Sole_Label", 0.11f },
        };

        public void Build(IDictionary<string, Vector3> cadOffsets = null)
        {
            _mpb = new MaterialPropertyBlock();
            _haloMpb = new MaterialPropertyBlock();
            _heater.Clear();
            _layers.Clear();
            foreach (var g in _halo) if (g != null) Destroy(g);
            _halo.Clear();
            var prefix = "CH" + channel + "_";
            foreach (var t in GetComponentsInChildren<Transform>(true))
            {
                if (!t.name.StartsWith(prefix)) continue;
                var part = t.name.Substring(prefix.Length);
                if (part == "Heater") _heater.AddRange(t.GetComponentsInChildren<Renderer>(true));
                float off;
                if (cadOffsets != null && cadOffsets.TryGetValue(t.name, out var v)) off = v.y;
                else if (!(channel >= 3 ? FootExplode : DefaultExplode).TryGetValue(part.StartsWith(SceneNames.StrapPrefix) ? "Strap" : part, out off)) continue;
                _layers.Add((t, t.localPosition, off));
            }
            if (haloMaterial != null)
            {
                foreach (var mf in GetComponentsInChildren<MeshFilter>(true))
                {
                    if (mf.sharedMesh == null || mf.gameObject.name.StartsWith("__")) continue;
                    var h = new GameObject("__halo");
                    h.transform.SetParent(mf.transform, false);
                    h.transform.localScale = Vector3.one * 1.06f;
                    h.AddComponent<MeshFilter>().sharedMesh = mf.sharedMesh;
                    var r = h.AddComponent<MeshRenderer>();
                    r.sharedMaterial = haloMaterial;
                    r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                    h.SetActive(false);
                    _halo.Add(h);
                }
            }
            if (heatLightIntensity > 0f && _heatLight == null)
            {
                var lg = new GameObject("__heat_light");
                lg.transform.SetParent(transform, false);
                lg.transform.localPosition = new Vector3(0f, 0.05f, 0f);
                _heatLight = lg.AddComponent<Light>();
                _heatLight.type = LightType.Point;
                _heatLight.color = new Color(1f, 0.62f, 0.18f);
                _heatLight.range = heatLightRange;
                _heatLight.intensity = 0f;
                _heatLight.shadows = LightShadows.None;
            }
            _built = true;
            ApplyGlow(0);
        }

        /// <summary>Apply the channel's replay values. snap = true on seeks/steps so the scene matches the frame exactly.</summary>
        public void Show(ChannelView v, bool snap)
        {
            if (!_built) Build();
            Last = v;
            _glowTarget = double.IsNaN(v.Heat) ? 0f : Mathf.Clamp01((float)(v.Heat / 100.0));
            if (snap || glowEase <= 0) { _glow = _glowTarget; ApplyGlow(_glow); }
            bool outline = v.FaultCode > 0 || v.Cutoff || !v.Connected;
            // Critical colour only for replayed hardware cutoff / safety shutdown; no severity is inferred from code numbers.
            var color = v.Cutoff || v.Status == ChannelStatus.Shutdown ? haloCritical : haloWarning;
            foreach (var h in _halo)
            {
                if (h == null) continue;
                if (h.activeSelf != outline) h.SetActive(outline);
                if (outline)
                {
                    var r = h.GetComponent<MeshRenderer>();
                    r.GetPropertyBlock(_haloMpb);
                    _haloMpb.SetColor(BaseColorId, color);
                    r.SetPropertyBlock(_haloMpb);
                }
            }
        }

        public void SetExploded(bool exploded) => _explodeTarget = exploded ? 1f : 0f;
        public bool Exploded => _explodeTarget > 0.5f;

        private void Update()
        {
            if (!_built) return;
            if (!Mathf.Approximately(_glow, _glowTarget))
            {
                _glow = Mathf.MoveTowards(_glow, _glowTarget, Time.unscaledDeltaTime / Mathf.Max(0.01f, glowEase));
                ApplyGlow(_glow);
            }
            if (!Mathf.Approximately(_explode, _explodeTarget))
            {
                _explode = Mathf.MoveTowards(_explode, _explodeTarget, Time.unscaledDeltaTime * 2.5f);
                float e = Mathf.SmoothStep(0, 1, _explode);
                foreach (var (t, basePos, off) in _layers)
                    if (t != null) t.localPosition = basePos + t.parent.InverseTransformDirection(transform.up) * (off * e);
            }
        }

        private void ApplyGlow(float g)
        {
            if (_heatLight != null)
            {
                _heatLight.intensity = heatLightIntensity * g;
                _heatLight.enabled = g > 0.001f;
            }
            foreach (var r in _heater)
            {
                if (r == null) continue;
                r.GetPropertyBlock(_mpb);
                _mpb.SetColor(EmissionId, heatEmission * g);
                r.SetPropertyBlock(_mpb);
            }
        }
    }
}
