using Neram.Core;
using UnityEngine.UIElements;

namespace Neram.Unity
{
    /// <summary>
    /// Persistent footer: "Proof-of-concept. SIMULATED / ASSUMED PROTOTYPE RESPONSE where marked. Not for treatment decisions."
    /// plus the replay's own disclaimer, cohort and a placeholder watermark for synthetic scaffolding files.
    /// It cannot be hidden, including in presentation mode.
    /// </summary>
    public sealed class DisclaimerBanner : IReplayView
    {
        public const string Standard = "SIMULATED / ASSUMED PROTOTYPE RESPONSE where marked. Not for treatment decisions. " +
                                       "Patient temperature signal: anatomical site not established (not core temperature).";

        private readonly Label _text, _right, _mark;

        public DisclaimerBanner(VisualElement root)
        {
            _text = UiUtil.Req<Label>(root, "footer-text");
            _right = UiUtil.Req<Label>(root, "footer-right");
            _mark = UiUtil.Req<Label>(root, "placeholder-mark");
            _text.text = Standard;
        }

        public void Bind(ReplaySession s)
        {
            var h = s.Header;
            _text.text = Standard;
            _text.tooltip = h.Disclaimer;
            _right.text = "cohort " + h.Cohort + "  ·  schema " + h.SchemaVersion + "  ·  params v" + h.ParamsVersion + "  ·  spec v" + h.SpecVersion;
            UiUtil.Show(_mark, h.Placeholder);
        }

        public void ShowFrame(int frame) { }

        public void Unbind()
        {
            _right.text = "";
            UiUtil.Show(_mark, false);
        }
    }
}
