using System.Collections.Generic;
using Neram.Core;
using UnityEngine.UIElements;

namespace Neram.Unity
{
    /// <summary>
    /// PIPELINE strip: temperature input -> state estimator -> controller decision -> warming channels -> patient/device
    /// view. Values come from PipelineRules (pure functions of the replay frame). The stage that changed most recently
    /// (look-back 60 s of replay time) is highlighted. Unity does not decide anything here: the warming-channel stage shows
    /// the replayed Heat_i commands, and the device glow follows exactly those commands.
    /// </summary>
    public sealed class PipelinePanel : IReplayView
    {
        private sealed class Card
        {
            public VisualElement Root;
            public Label Title, Value, Detail, Tag;
        }

        private readonly List<Card> _cards = new List<Card>();
        private readonly Label _note;
        private ReplaySession _s;

        public PipelinePanel(VisualElement root)
        {
            var host = UiUtil.Req<VisualElement>(root, "pipeline-stages");
            _note = UiUtil.Req<Label>(root, "pipeline-note");
            string[] titles = { "1 · TEMPERATURE INPUT", "2 · STATE ESTIMATOR", "3 · CONTROLLER DECISION", "4 · WARMING CHANNELS", "5 · PATIENT / DEVICE VIEW" };
            for (int i = 0; i < 5; i++)
            {
                if (i > 0)
                {
                    var arrow = UiUtil.Label("›", "pl-arrow");
                    arrow.pickingMode = PickingMode.Ignore;
                    host.Add(arrow);
                }
                var c = new Card { Root = UiUtil.Box("pl-card") };
                var head = UiUtil.Box("row");
                c.Title = UiUtil.Label(titles[i], "pl-title");
                c.Tag = UiUtil.Label("", "pl-tag");
                head.Add(c.Title);
                head.Add(UiUtil.Box("spacer"));
                head.Add(c.Tag);
                c.Value = UiUtil.Label("—", "pl-value");
                c.Detail = UiUtil.Label("", "pl-detail");
                c.Root.Add(head);
                c.Root.Add(c.Value);
                c.Root.Add(c.Detail);
                host.Add(c.Root);
                _cards.Add(c);
            }
            Unbind();
        }

        public void Bind(ReplaySession s) => _s = s;

        public void Unbind()
        {
            _s = null;
            foreach (var c in _cards)
            {
                c.Value.text = "—";
                c.Detail.text = "no replay loaded";
                c.Tag.text = "";
                c.Root.EnableInClassList("pl-active", false);
            }
            _note.text = "Replay-driven: every stage shows values from the loaded replay; Unity computes no estimate, decision or command.";
        }

        public void ShowFrame(int frame)
        {
            if (_s == null) return;
            var v = PipelineRules.Compute(_s, frame);
            double now = _s.Table.T[frame];
            for (int i = 0; i < 5; i++)
            {
                var st = v.Stages[i];
                var c = _cards[i];
                UiUtil.SetText(c.Value, st.Value);
                UiUtil.SetText(c.Detail, st.Detail);
                UiUtil.SetText(c.Tag, st.Tag);
                SwapClass(c.Tag, "tag-" + st.Tag);
                c.Root.EnableInClassList("pl-unavailable", !st.Available);
                bool recent = !double.IsNaN(st.LastChange) && now - st.LastChange <= 10.0;
                c.Root.EnableInClassList("pl-recent", recent);
                c.Root.EnableInClassList("pl-active", i == v.ActiveStage || (i == 4 && v.ActiveStage == 3));
            }
            UiUtil.SetText(_note, v.ActiveStage >= 0
                ? "Most recent change in the last 60 s of replay: stage " + (v.ActiveStage + 1) + " · " + v.Stages[v.ActiveStage].Title.ToLowerInvariant()
                : "No stage changed in the last 60 s of replay time.");
        }

        private static void SwapClass(VisualElement e, string cls)
        {
            if (e.userData is string prev && prev != cls) e.RemoveFromClassList(prev);
            e.AddToClassList(cls);
            e.userData = cls;
        }
    }
}
