using Neram.Core;
using UnityEngine;

namespace Neram.Unity
{
    /// <summary>
    /// Bedside controller visuals: BC_LED_CH1..4 follow each channel's display status; BC_Display is tinted with the
    /// controller-state colour. Colours encode replayed values only.
    /// </summary>
    [DisallowMultipleComponent]
    public sealed class ControllerView3D : MonoBehaviour
    {
        [ColorUsage(false, true)] public Color ledOff = new Color(0.08f, 0.09f, 0.11f);
        [ColorUsage(false, true)] public Color ledHeating = new Color(2.2f, 1.1f, 0.15f);
        [ColorUsage(false, true)] public Color ledFault = new Color(2.0f, 1.5f, 0.0f);
        [ColorUsage(false, true)] public Color ledCritical = new Color(2.4f, 0.25f, 0.25f);
        public float displayIntensity = 1.4f;

        private static readonly int EmissionId = Shader.PropertyToID("_EmissionColor");
        private readonly Renderer[] _leds = new Renderer[4];
        private Renderer _display;
        private MaterialPropertyBlock _mpb;

        public void Build()
        {
            _mpb = new MaterialPropertyBlock();
            foreach (var t in GetComponentsInChildren<Transform>(true))
            {
                for (int i = 0; i < 4; i++)
                    if (t.name == "BC_LED_CH" + (i + 1)) _leds[i] = t.GetComponent<Renderer>();
                if (t.name == "BC_Display") _display = t.GetComponent<Renderer>();
            }
        }

        public void Show(ReplaySession s, int frame)
        {
            if (_mpb == null) Build();
            for (int i = 0; i < 4; i++)
            {
                if (_leds[i] == null) continue;
                var v = ChannelRules.Compute(s, frame, i + 1);
                Color c;
                switch (v.Status)
                {
                    case ChannelStatus.Heating: c = ledHeating * Mathf.Lerp(0.35f, 1f, (float)(v.Heat / 100.0)); break;
                    case ChannelStatus.Fault:
                    case ChannelStatus.Disconnected: c = ledFault; break;
                    case ChannelStatus.Cutoff:
                    case ChannelStatus.Shutdown: c = ledCritical; break;
                    default: c = ledOff; break;
                }
                Set(_leds[i], c);
            }
            if (_display != null)
            {
                var name = s.Enums.NameOf(EnumNames.ControllerState, s.Table.GetInt(s.F.State, frame));
                Set(_display, UiUtil.StateColor(name) * displayIntensity);
            }
        }

        private void Set(Renderer r, Color emission)
        {
            r.GetPropertyBlock(_mpb);
            _mpb.SetColor(EmissionId, emission);
            r.SetPropertyBlock(_mpb);
        }
    }
}
