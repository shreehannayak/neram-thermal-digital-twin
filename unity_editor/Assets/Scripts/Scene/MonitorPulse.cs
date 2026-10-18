using UnityEngine;

namespace Neram.Unity
{
    /// <summary>
    /// Animated traces on the theatre patient monitor (OT_Patient_Monitor/Monitor_Screen). DEMONSTRATION PROP: the ECG-
    /// style, pleth and respiration traces are drawn from fixed shapes at a fixed visual rate. They are not patient data,
    /// not VitalDB, not the NERAM replay, and no number is shown (the readout boxes in the texture show dashes). The base
    /// face comes from tools/meshgen/textures.py monitor_live(); band rows below match it. Runs on unscaled real time, so
    /// it keeps moving while a replay is paused. The TEMP box shows the replay's patient temperature signal (the same
    /// SYNTHETIC value the dashboard shows, via VisualModeController.PatientSignal), drawn as 7-segment digits; dashes
    /// when the replay has no observation.
    /// </summary>
    [DisallowMultipleComponent]
    public sealed class MonitorPulse : MonoBehaviour
    {
        // trace area and bands in texture pixels, measured from the TOP of the 640 x 400 face (as in the PNG)
        private const int X0 = 18, X1 = 462;
        private static readonly int[] BandTop = { 74, 186, 286 };
        private static readonly int[] BandBottom = { 160, 260, 344 };
        private static readonly Color32[] BandColor = { new Color32(64, 220, 120, 255), new Color32(60, 200, 230, 255), new Color32(240, 200, 80, 255) };
        private const float SweepPxPerS = 120f, BeatS = 0.86f, BreathS = 4.2f, Fps = 30f;
        private const int Gap = 14;

        private Texture2D _tex;
        private Color32[] _base, _buf;
        private int _w, _h;
        private float[,] _y;          // [band, column] trace value in pixels from the band top
        private float _head, _next, _beatFlash;
        private VisualModeController _modes;
        private static readonly Color32 TempColor = new Color32(240, 200, 80, 255);

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        private static void Attach()
        {
            foreach (var r in FindObjectsByType<MeshRenderer>(FindObjectsInactive.Exclude, FindObjectsSortMode.None))
                if (r.gameObject.name == "Monitor_Screen" && r.transform.parent != null && r.transform.parent.name == "OT_Patient_Monitor"
                    && r.GetComponent<MonitorPulse>() == null)
                    r.gameObject.AddComponent<MonitorPulse>();
        }

        private void Start()
        {
            var rend = GetComponent<Renderer>();
            if (rend == null) { enabled = false; return; }
            var mat = rend.material;   // instance: the shared screen material stays untouched
            var src = mat.HasProperty("_BaseMap") ? mat.GetTexture("_BaseMap") as Texture2D : mat.mainTexture as Texture2D;
            _w = src != null ? src.width : 640; _h = src != null ? src.height : 400;
            _base = new Color32[_w * _h];
            bool ok = false;
            if (src != null && src.isReadable) { try { _base = src.GetPixels32(); ok = true; } catch { ok = false; } }
            if (!ok) for (int i = 0; i < _base.Length; i++) _base[i] = new Color32(6, 9, 13, 255);   // plain face if not readable
            _buf = new Color32[_base.Length];
            _tex = new Texture2D(_w, _h, TextureFormat.RGBA32, false) { name = "__monitor_pulse", wrapMode = TextureWrapMode.Clamp };
            foreach (var p in new[] { "_BaseMap", "_MainTex", "_EmissionMap" })
                if (mat.HasProperty(p)) mat.SetTexture(p, _tex);
            if (mat.HasProperty("_EmissionColor")) { mat.EnableKeyword("_EMISSION"); if (mat.GetColor("_EmissionColor").maxColorComponent < 0.3f) mat.SetColor("_EmissionColor", Color.white * 0.8f); }
            _y = new float[3, X1 - X0 + 1];
            for (int b = 0; b < 3; b++) for (int c = 0; c <= X1 - X0; c++) _y[b, c] = float.NaN;
            _head = 0f;
            _modes = FindAnyObjectByType<VisualModeController>();
        }

        private static float G(float x, float mu, float s) => Mathf.Exp(-0.5f * (x - mu) * (x - mu) / (s * s));

        /// <summary>Normalised trace value 0..1 (1 = top of band) for band b at time t. Shapes only, no physiology.</summary>
        private static float Wave(int b, float t)
        {
            if (b == 0)
            {
                float p = (t % BeatS) / BeatS;
                return 0.32f + 0.06f * G(p, 0.12f, 0.025f) - 0.08f * G(p, 0.215f, 0.008f) + 0.62f * G(p, 0.235f, 0.009f)
                       - 0.14f * G(p, 0.258f, 0.009f) + 0.12f * G(p, 0.46f, 0.045f);
            }
            if (b == 1)
            {
                float p = ((t - 0.16f) % BeatS + BeatS) % BeatS / BeatS;
                return 0.12f + 0.72f * G(p, 0.30f, 0.085f) + 0.22f * G(p, 0.58f, 0.07f);
            }
            return 0.5f + 0.38f * Mathf.Sin(2f * Mathf.PI * t / BreathS);
        }

        private void Update()
        {
            if (_tex == null) return;
            float now = Time.unscaledTime;
            if (now < _next) return;
            float dt = Mathf.Min(0.2f, 1f / Fps + (now - _next));
            _next = now + 1f / Fps;
            int cols = X1 - X0 + 1;
            float newHead = _head + SweepPxPerS * dt;
            for (int c = Mathf.FloorToInt(_head) + 1; c <= Mathf.FloorToInt(newHead); c++)
            {
                int col = ((c % cols) + cols) % cols;
                float tc = now - (newHead - c) / SweepPxPerS;
                for (int b = 0; b < 3; b++) _y[b, col] = Wave(b, tc);
                for (int g = 1; g <= Gap; g++) for (int b = 0; b < 3; b++) _y[b, (col + g) % cols] = float.NaN;   // erase ahead
            }
            _head = newHead;
            float beatPhase = (now % BeatS) / BeatS;
            _beatFlash = beatPhase > 0.22f && beatPhase < 0.36f ? 1f : 0f;
            Draw();
        }

        private void Px(int x, int yTop, Color32 c)
        {
            if (x < 0 || x >= _w || yTop < 0 || yTop >= _h) return;
            _buf[(_h - 1 - yTop) * _w + x] = c;
        }

        private void Draw()
        {
            System.Array.Copy(_base, _buf, _base.Length);
            int cols = X1 - X0 + 1;
            for (int b = 0; b < 3; b++)
            {
                int top = BandTop[b], bot = BandBottom[b];
                var col = BandColor[b];
                for (int c = 1; c < cols; c++)
                {
                    float a = _y[b, c - 1], v = _y[b, c];
                    if (float.IsNaN(a) || float.IsNaN(v)) continue;
                    int ya = Mathf.RoundToInt(Mathf.Lerp(bot, top, a)), yv = Mathf.RoundToInt(Mathf.Lerp(bot, top, v));
                    int lo = Mathf.Min(ya, yv), hi = Mathf.Max(ya, yv);
                    for (int y = lo - 1; y <= hi + 1; y++) { Px(X0 + c, y, col); Px(X0 + c - 1, y, col); }
                }
            }
            if (_beatFlash > 0f)   // beat marker next to the ECG label
                for (int dy = -6; dy <= 6; dy++) for (int dx = -6; dx <= 6; dx++)
                    if (dx * dx + dy * dy <= 30) Px(118 + dx, 68 + dy, BandColor[0]);
            double sig = _modes != null ? _modes.PatientSignal : double.NaN;
            DrawNumber(double.IsNaN(sig) || double.IsInfinity(sig) ? "--.-" : sig.ToString("0.0", System.Globalization.CultureInfo.InvariantCulture), 612, 296, 32, TempColor);
            _tex.SetPixels32(_buf);
            _tex.Apply(false);
        }

        // 7-segment glyphs: a top, b upper-right, c lower-right, d bottom, e lower-left, f upper-left, g middle
        private static readonly string[] Seg = { "abcdef", "bc", "abdeg", "abcdg", "bcfg", "acdfg", "acdefg", "abc", "abcdefg", "abcdfg" };

        /// <summary>Right-aligned number with its right edge at xRight, top at yTop (pixels from the top), digit height h.</summary>
        private void DrawNumber(string s, int xRight, int yTop, int h, Color32 c)
        {
            int w = h / 2, th = Mathf.Max(3, h / 9), gap = w / 3;
            int x = xRight;
            for (int i = s.Length - 1; i >= 0; i--)
            {
                char ch = s[i];
                if (ch == '.') { x -= th + 2; Rect(x, yTop + h - th, th, th, c); x -= 3; continue; }
                x -= w;
                string segs = ch == '-' ? "g" : (ch >= '0' && ch <= '9' ? Seg[ch - '0'] : "");
                int mid = yTop + h / 2;
                foreach (char g in segs)
                    switch (g)
                    {
                        case 'a': Rect(x, yTop, w, th, c); break;
                        case 'd': Rect(x, yTop + h - th, w, th, c); break;
                        case 'g': Rect(x, mid - th / 2, w, th, c); break;
                        case 'f': Rect(x, yTop, th, h / 2, c); break;
                        case 'e': Rect(x, mid, th, h / 2, c); break;
                        case 'b': Rect(x + w - th, yTop, th, h / 2, c); break;
                        case 'c': Rect(x + w - th, mid, th, h / 2, c); break;
                    }
                x -= gap;
            }
        }

        private void Rect(int x0, int y0, int w, int h, Color32 c)
        {
            for (int y = y0; y < y0 + h; y++) for (int x = x0; x < x0 + w; x++) Px(x, y, c);
        }

        private void OnDestroy()
        {
            if (_tex != null) Destroy(_tex);
        }
    }
}
