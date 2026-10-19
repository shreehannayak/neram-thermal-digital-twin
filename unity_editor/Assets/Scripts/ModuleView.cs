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

        // ------------------------------------------------------------------ exploded-view labels
        /// <summary>Display names of the construction layers (shown next to each part while the module is exploded).</summary>
        public static readonly Dictionary<string, string> LayerNames = new Dictionary<string, string>
        {
            { "Liner", "Liner (skin side)" }, { "Insulation", "Insulation" }, { "Heater", "Heater film" },
            { "Sensor_A", "Sensor A (NTC)" }, { "Sensor_B", "Sensor B (NTC)" }, { "Cutoff", "Thermal cutoff" },
            { "Shell", "Outer shell" }, { "Cuff", "Cuff" }, { "Label_Plate", "Label plate" }, { "Label", "Label" },
            { "Strain_Relief", "Strain relief" }, { "Strap", "Strap" }, { "Buckle", "Buckle" }, { "Toe_Cap", "Toe cap" },
            { "Heel_Counter", "Heel counter" }, { "Collar", "Collar" }, { "Sole_Outsole", "Outsole" },
            { "Sole_Tread", "Tread" }, { "Sole_Label", "Sole label" },
        };
        private GUIStyle _lblStyle, _lblTitle;
        private static Texture2D _px;

        private void OnGUI()
        {
            if (!_built || _explode < 0.6f || Event.current.type != EventType.Repaint) return;
            var cam = Camera.main;
            if (cam == null) return;
            if (_px == null) { _px = new Texture2D(1, 1); _px.SetPixel(0, 0, Color.white); _px.Apply(); }
            if (_lblStyle == null)
            {
                int fs = Mathf.Max(11, Screen.height / 72);
                _lblStyle = new GUIStyle(GUI.skin.box) { fontSize = fs, alignment = TextAnchor.MiddleLeft, padding = new RectOffset(8, 8, 3, 3) };
                _lblStyle.normal.textColor = new Color(0.94f, 0.97f, 1f);
                _lblStyle.normal.background = MakeTex(new Color(0.05f, 0.10f, 0.14f, 0.86f));
                _lblTitle = new GUIStyle(_lblStyle) { fontStyle = FontStyle.Bold };
                _lblTitle.normal.textColor = new Color(0.98f, 0.80f, 0.35f);
            }
            float a = Mathf.InverseLerp(0.6f, 1f, _explode);
            var seen = new HashSet<string>();
            var items = new List<(Vector2 anchor, string text)>();
            var prefix = "CH" + channel + "_";
            foreach (var (t, _, _) in _layers)
            {
                if (t == null) continue;
                var part = t.name.StartsWith(prefix) ? t.name.Substring(prefix.Length) : t.name;
                var key = part.StartsWith(SceneNames.StrapPrefix) ? "Strap" : part;
                if (!seen.Add(key)) continue;
                var rs = t.GetComponentsInChildren<Renderer>();
                if (rs.Length == 0) continue;
                var b = rs[0].bounds;
                foreach (var r in rs) if (!r.name.StartsWith("__")) b.Encapsulate(r.bounds);
                var sp = cam.WorldToScreenPoint(b.center);
                if (sp.z <= 0) continue;
                items.Add((new Vector2(sp.x, Screen.height - sp.y), LayerNames.TryGetValue(key, out var nm) ? nm : key.Replace('_', ' ')));
            }
            if (items.Count == 0) return;
            // labels in a column beside the module, sorted top to bottom, joined to their part by a leader line
            items.Sort((p, q) => p.anchor.y.CompareTo(q.anchor.y));
            float cx = 0f; foreach (var it in items) cx += it.anchor.x; cx /= items.Count;
            bool right = cx < Screen.width * 0.5f;
            float colX = right ? cx + Screen.width * 0.12f : cx - Screen.width * 0.12f;
            float lh = _lblStyle.fontSize * 2.0f;
            float top = items[0].anchor.y - lh;
            var old = GUI.color;
            GUI.color = new Color(1f, 1f, 1f, a);
            var title = new GUIContent(ChannelTitle(channel) + " - exploded layers");
            var ts = _lblTitle.CalcSize(title);
            GUI.Label(new Rect(right ? colX : colX - ts.x, top - lh * 1.1f, ts.x, lh), title, _lblTitle);
            for (int i = 0; i < items.Count; i++)
            {
                var c = new GUIContent(items[i].text);
                var sz = _lblStyle.CalcSize(c);
                float y = Mathf.Max(top + i * lh * 1.05f, items[i].anchor.y - lh * 0.5f);
                top = y - i * lh * 1.05f;
                var rect = new Rect(right ? colX : colX - sz.x, y, sz.x, lh * 0.9f);
                var end = new Vector2(right ? rect.xMin : rect.xMax, rect.center.y);
                Line(items[i].anchor, end, new Color(0.98f, 0.80f, 0.35f, 0.9f * a), 1.6f);
                GUI.color = new Color(0.98f, 0.80f, 0.35f, a);
                GUI.DrawTexture(new Rect(items[i].anchor.x - 3, items[i].anchor.y - 3, 6, 6), _px);
                GUI.color = new Color(1f, 1f, 1f, a);
                GUI.Label(rect, c, _lblStyle);
            }
            GUI.color = old;
        }

        private static string ChannelTitle(int ch) => ch switch
        {
            1 => "CH1 left hand module", 2 => "CH2 right hand module", 3 => "CH3 left foot module", 4 => "CH4 right foot module", _ => "Module",
        };

        private static Texture2D MakeTex(Color c)
        {
            var t = new Texture2D(1, 1); t.SetPixel(0, 0, c); t.Apply(); return t;
        }

        private static void Line(Vector2 a, Vector2 b, Color c, float w)
        {
            var m = GUI.matrix;
            var old = GUI.color;
            GUI.color = c;
            float ang = Mathf.Atan2(b.y - a.y, b.x - a.x) * Mathf.Rad2Deg;
            float len = (b - a).magnitude;
            GUIUtility.RotateAroundPivot(ang, a);
            GUI.DrawTexture(new Rect(a.x, a.y - w * 0.5f, len, w), _px);
            GUI.matrix = m;
            GUI.color = old;
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
