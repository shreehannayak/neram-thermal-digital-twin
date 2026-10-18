using System;
using System.Collections.Generic;
using System.IO;
using Neram.Core;
using UnityEngine.UIElements;

namespace Neram.Unity
{
    /// <summary>
    /// Scenario drawer: every catalogued scenario slot (unity_scenarios.json) and every replay file found, with title,
    /// purpose, data source, cohort, expected tags, limitations and availability. Scenarios without a file are shown as
    /// AWAITING DATA (e.g. SCN_A until Sai's development replay exists); files with an invalid header cannot be loaded.
    /// </summary>
    public sealed class ScenarioSelector
    {
        private readonly VisualElement _drawer;
        private readonly ScrollView _list;
        private readonly Action<ScenarioListing> _load;
        private readonly Action _rescan;
        private string _currentId;

        public ScenarioSelector(VisualElement root, Action<ScenarioListing> load, Action rescan)
        {
            _load = load;
            _rescan = rescan;
            _drawer = UiUtil.Req<VisualElement>(root, "drawer-scenarios");
            var head = UiUtil.Box("drawer-head");
            head.Add(UiUtil.Label("Scenarios", "drawer-title"));
            head.Add(UiUtil.Button("Rescan", () => _rescan(), "btn-ghost"));
            head.Add(UiUtil.Button("Close", Close, "btn-ghost"));
            _drawer.Add(head);
            _drawer.Add(UiUtil.Label("Engineering / simulation demonstrations. No scenario shows a measured or predicted clinical benefit. " +
                                     "The final holdout never appears here (replays with any cohort other than SYNTHETIC or DEVELOPMENT are rejected).", "card-text"));
            _list = new ScrollView();
            _list.style.flexGrow = 1;
            _list.style.marginTop = 8;
            _drawer.Add(_list);
        }

        public bool IsOpen => UiUtil.IsShown(_drawer);
        public void Toggle() => UiUtil.Show(_drawer, !IsOpen);
        public void Close() => UiUtil.Show(_drawer, false);

        public void SetCurrent(string id) => _currentId = id;

        public void Render(List<ScenarioListing> scenarios)
        {
            _list.Clear();
            foreach (var l in scenarios)
            {
                var card = UiUtil.Box("card");
                card.EnableInClassList("current", l.Id == _currentId);
                var top = UiUtil.Box("row");
                top.Add(UiUtil.Label(l.Title, "card-title"));
                top.Add(UiUtil.Box("spacer"));
                switch (l.Availability)
                {
                    case ScenarioAvailability.Available: top.Add(UiUtil.Chip("AVAILABLE", "chip-ok")); break;
                    case ScenarioAvailability.AwaitingData: top.Add(UiUtil.Chip("AWAITING DATA", "chip-warn")); break;
                    default: top.Add(UiUtil.Chip("INVALID HEADER", "chip-crit")); break;
                }
                if (l.IsPlaceholder) top.Add(UiUtil.Chip("PLACEHOLDER", "chip-placeholder"));
                if (l.Header?.Cohort != null) top.Add(UiUtil.Chip(l.Header.Cohort, l.Header.Cohort == "DEVELOPMENT" ? "chip-ok" : "chip-info"));
                card.Add(top);
                card.Add(UiUtil.Label(l.Id + (l.FilePath != null ? "  ·  " + Path.GetFileName(l.FilePath) : ""), "t-xs", "c-3", "mono"));
                var info = l.Header?.Info;
                var purpose = info?.Purpose ?? l.Catalog?.Purpose;
                if (!string.IsNullOrEmpty(purpose)) card.Add(UiUtil.Label(purpose, "card-text"));
                var source = info?.DataSource ?? l.Catalog?.ExpectedDataSource;
                if (!string.IsNullOrEmpty(source)) card.Add(UiUtil.Label("Data source: " + source, "card-text"));
                if (!string.IsNullOrEmpty(info?.LoopDescription)) card.Add(UiUtil.Label(info.LoopDescription, "card-text"));
                if (l.Catalog?.Producer != null) card.Add(UiUtil.Label("Produced by: " + l.Catalog.Producer, "card-text"));
                var lims = info != null && info.Limitations.Count > 0 ? info.Limitations : l.Catalog?.Limitations;
                if (lims != null && lims.Count > 0)
                {
                    card.Add(UiUtil.Label("Limitations", "t-xs", "c-2", "semibold"));
                    foreach (var lim in lims) card.Add(UiUtil.Label("• " + lim, "limit"));
                }
                if (l.Availability == ScenarioAvailability.HeaderInvalid && l.HeaderReport != null)
                    foreach (var i in l.HeaderReport.Issues)
                        if (i.Severity == IssueSeverity.Error) card.Add(UiUtil.Label(i.ToString(), "limit"));
                var listing = l;
                var btn = UiUtil.Button(l.Id == _currentId ? "Reload" : "Load", () => { Close(); _load(listing); }, "btn-primary");
                btn.style.marginTop = 6;
                btn.style.alignSelf = Align.FlexStart;
                btn.SetEnabled(l.Availability == ScenarioAvailability.Available);
                card.Add(btn);
                _list.Add(card);
            }
        }
    }
}
