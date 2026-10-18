using System.Collections.Generic;
using Neram.Core;
using UnityEngine.UIElements;

namespace Neram.Unity
{
    /// <summary>
    /// Reusable provenance badge: "GROUP | TAG" (e.g. "TWIN | MODEL"). Badges are never hidden: the global toggle only
    /// switches between compact and expanded (expanded adds the meaning of the tag). Colours come from neram.uss.
    /// </summary>
    public sealed class SourceBadge
    {
        private static readonly List<SourceBadge> Live = new List<SourceBadge>();
        private static bool _expanded;

        public readonly VisualElement Root;
        private readonly Label _group;
        private readonly Label _tag;
        private readonly Label _meaning;
        private string _currentTag;

        public SourceBadge(string groupTitle)
        {
            Root = new VisualElement();
            Root.AddToClassList("src-badge");
            _group = UiUtil.Label(groupTitle.ToUpperInvariant(), "src-badge-group");
            _tag = UiUtil.Label("—", "src-badge-tag");
            _meaning = UiUtil.Label("", "src-badge-meaning");
            Root.Add(_group);
            Root.Add(_tag);
            Root.Add(_meaning);
            UiUtil.Show(_meaning, _expanded);
            Live.Add(this);
        }

        /// <summary>Set the tag (REAL_DEV / MODEL / SIMULATED / ASSUMED) and its plain-language meaning.</summary>
        public void Set(string tag, string meaning)
        {
            if (_currentTag != tag)
            {
                if (_currentTag != null) Root.RemoveFromClassList("src-" + _currentTag);
                _currentTag = tag;
                if (tag != null) Root.AddToClassList("src-" + tag);
                _tag.text = tag ?? "—";
            }
            UiUtil.SetText(_meaning, meaning ?? "");
            Root.tooltip = (tag ?? "no tag") + ": " + (meaning ?? "");
        }

        public void Set(ReplaySession s, string group, int frame)
        {
            var tag = s.Tag(group, frame);
            Set(tag, ProvenanceRules.Meaning(group, tag, s, frame));
        }

        /// <summary>Global compact / expanded mode for every badge.</summary>
        public static bool Expanded
        {
            get => _expanded;
            set
            {
                _expanded = value;
                foreach (var b in Live) UiUtil.Show(b._meaning, value);
            }
        }

        public void Dispose()
        {
            Live.Remove(this);
            Root.RemoveFromHierarchy();
        }
    }
}
