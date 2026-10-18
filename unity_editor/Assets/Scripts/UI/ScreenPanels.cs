using System;
using System.Collections.Generic;
using Neram.Core;
using UnityEngine.UIElements;

namespace Neram.Unity
{
    /// <summary>
    /// THEATRE / MONITOR / FULL ANALYSIS screens and per-panel visibility (display only: never touches the replay, the
    /// clock, the scenario, the speed or the camera).
    ///
    /// Every hideable panel is registered with an id from <see cref="ScreenLayout"/> and gets its own "×" button. Visibility
    /// is kept per screen; root classes (scr-theatre / scr-monitor / scr-analysis, no-left, no-charts, no-pipeline,
    /// no-details, no-forecast, details-collapsed) let neram.uss reflow the remaining panels. The Panels drawer lists every
    /// panel of the current screen with its own switch, plus HIDE ALL PANELS / SHOW PANELS / RESET LAYOUT.
    /// </summary>
    public sealed class ScreenPanels
    {
        private readonly VisualElement _root;
        private readonly ScreenLayout _layout = new ScreenLayout();
        private readonly Dictionary<string, List<VisualElement>> _elements = new Dictionary<string, List<VisualElement>>();
        private readonly Dictionary<string, Action<bool>> _hooks = new Dictionary<string, Action<bool>>();
        private readonly Dictionary<ScreenMode, Button> _tabs = new Dictionary<ScreenMode, Button>();
        private readonly Dictionary<MonitorPage, Button> _pages = new Dictionary<MonitorPage, Button>();
        private readonly Dictionary<string, (VisualElement row, Button toggle)> _rows = new Dictionary<string, (VisualElement, Button)>();
        private readonly VisualElement _list, _ovPair, _monitorEmpty;
        private readonly Label _drawerTitle;
        private readonly Button _btnPanels;

        public ScreenMode Mode { get; private set; } = ScreenMode.Theatre;
        /// <summary>Screen to return to when the monitor is closed (never Monitor).</summary>
        public ScreenMode ReturnTo { get; private set; } = ScreenMode.Theatre;
        /// <summary>Current MONITOR page (kept while the monitor is closed).</summary>
        public MonitorPage Page { get; private set; } = MonitorPage.Values;

        /// <summary>Raised after every change of screen or visibility (NeramApp syncs buttons and settings).</summary>
        public event Action Changed;

        public ScreenPanels(VisualElement root)
        {
            _root = root;
            _tabs[ScreenMode.Theatre] = UiUtil.Req<Button>(root, "tab-theatre");
            _tabs[ScreenMode.Monitor] = UiUtil.Req<Button>(root, "tab-monitor");
            _tabs[ScreenMode.Analysis] = UiUtil.Req<Button>(root, "tab-analysis");
            foreach (var kv in _tabs)
            {
                var m = kv.Key;
                kv.Value.clicked += () => SetMode(m);
            }
            _list = UiUtil.Req<VisualElement>(root, "panels-scroll");
            _drawerTitle = UiUtil.Req<Label>(root, "panels-title");
            _ovPair = UiUtil.Req<VisualElement>(root, "ov-pair");
            _monitorEmpty = UiUtil.Req<Label>(root, "monitor-empty");
            _btnPanels = UiUtil.Req<Button>(root, "btn-panels");
            UiUtil.Req<Button>(root, "btn-hide-all").clicked += HideAll;
            UiUtil.Req<Button>(root, "btn-show-all").clicked += ShowAll;
            UiUtil.Req<Button>(root, "btn-reset-layout").clicked += ResetLayout;
            UiUtil.Req<Button>(root, "panels-hide-all").clicked += HideAll;
            UiUtil.Req<Button>(root, "panels-show-all").clicked += ShowAll;
            UiUtil.Req<Button>(root, "panels-reset").clicked += ResetLayout;
            UiUtil.Req<Button>(root, "monitor-to-theatre").clicked += () => SetMode(ScreenMode.Theatre);
            UiUtil.Req<Button>(root, "monitor-to-analysis").clicked += () => SetMode(ScreenMode.Analysis);
            UiUtil.Req<Button>(root, "monitor-close").clicked += CloseMonitor;
            _pages[MonitorPage.Values] = UiUtil.Req<Button>(root, "mon-page-values");
            _pages[MonitorPage.Graphs] = UiUtil.Req<Button>(root, "mon-page-graphs");
            _pages[MonitorPage.Channels] = UiUtil.Req<Button>(root, "mon-page-channels");
            _pages[MonitorPage.Flow] = UiUtil.Req<Button>(root, "mon-page-flow");
            foreach (var kv in _pages)
            {
                var pg = kv.Key;
                kv.Value.clicked += () => SetPage(pg);
            }

            foreach (var id in ScreenLayout.All)
            {
                _elements[id] = new List<VisualElement>();
                var row = UiUtil.Box("pn-row");
                row.Add(UiUtil.Label(ScreenLayout.Title(id), "pn-name"));
                string pid = id;
                var toggle = UiUtil.Button("Shown", () => { _layout.Toggle(Mode, pid); Apply(); }, "btn", "btn-small", "pn-toggle");
                toggle.focusable = false;
                row.Add(toggle);
                _list.Add(row);
                _rows[id] = (row, toggle);
            }
        }

        /// <summary>The "PANELS ▾" button (NeramApp opens the drawer with it).</summary>
        public Button PanelsButton => _btnPanels;

        /// <summary>Register a panel: its elements, and the row that receives its "×" hide button (null = no button).</summary>
        public void Register(string id, VisualElement buttonHost, params VisualElement[] elements)
        {
            foreach (var e in elements) if (e != null) _elements[id].Add(e);
            if (buttonHost != null) buttonHost.Add(HideButton(id));
        }

        /// <summary>Extra effect when a panel is shown or hidden (e.g. 3D labels, region-panel button text).</summary>
        public void Hook(string id, Action<bool> onApply) => _hooks[id] = onApply;

        /// <summary>A clearly visible "×" button that hides one panel on the current screen.</summary>
        public Button HideButton(string id)
        {
            string pid = id;
            var b = UiUtil.Button("×", () => Set(pid, false), "btn", "hide-btn");
            b.tooltip = "Hide: " + ScreenLayout.Title(id) + ". Restore with SHOW PANELS, RESET LAYOUT or PANELS ▾ (bottom bar). The replay is not affected.";
            b.focusable = false;
            return b;
        }

        public bool IsVisible(string id) => _layout.IsVisible(Mode, id);

        public bool IsVisible(ScreenMode mode, string id) => _layout.IsVisible(mode, id);

        public void Set(string id, bool visible)
        {
            _layout.Set(Mode, id, visible);
            Apply();
        }

        /// <summary>Set a panel on a screen that may not be the current one (e.g. the breakpoint default for Analysis).</summary>
        public void Set(ScreenMode mode, string id, bool visible)
        {
            _layout.Set(mode, id, visible);
            if (mode == Mode) Apply();
        }

        public void HideAll() { _layout.HideAll(Mode); Apply(); }
        public void ShowAll() { _layout.ShowAll(Mode); Apply(); }
        public void ResetLayout() { _layout.Reset(Mode); Apply(); }

        public void SetMode(ScreenMode mode)
        {
            if (mode != ScreenMode.Monitor) ReturnTo = mode;
            else if (Mode != ScreenMode.Monitor) ReturnTo = Mode;
            Mode = mode;
            Apply();
        }

        /// <summary>Show one MONITOR page (opens the monitor if it is closed).</summary>
        public void SetPage(MonitorPage page)
        {
            Page = page;
            if (Mode != ScreenMode.Monitor) SetMode(ScreenMode.Monitor);
            else Apply();
        }

        public void CloseMonitor()
        {
            if (Mode == ScreenMode.Monitor) SetMode(ReturnTo);
        }

        public void ToggleMonitor()
        {
            if (Mode == ScreenMode.Monitor) CloseMonitor();
            else SetMode(ScreenMode.Monitor);
        }

        /// <summary>Apply the current screen and its visible set to the tree (classes only; layout lives in neram.uss).</summary>
        public void Apply()
        {
            var m = Mode;
            _root.EnableInClassList("scr-theatre", m == ScreenMode.Theatre);
            _root.EnableInClassList("scr-monitor", m == ScreenMode.Monitor);
            _root.EnableInClassList("scr-analysis", m == ScreenMode.Analysis);
            _root.EnableInClassList("mp-values", Page == MonitorPage.Values);
            _root.EnableInClassList("mp-graphs", Page == MonitorPage.Graphs);
            _root.EnableInClassList("mp-channels", Page == MonitorPage.Channels);
            _root.EnableInClassList("mp-flow", Page == MonitorPage.Flow);
            foreach (var kv in _pages) kv.Value.EnableInClassList("selected", kv.Key == Page);
            foreach (var id in ScreenLayout.All)
            {
                bool vis = _layout.IsVisible(m, id);
                foreach (var e in _elements[id]) e.EnableInClassList("user-hidden", !vis);
                if (_hooks.TryGetValue(id, out var hook)) hook(vis);
            }
            bool left = _layout.AnyVisible(m, ScreenLayout.LeftColumn);
            bool charts = _layout.AnyVisible(m, ScreenLayout.Charts);
            bool details = _layout.IsVisible(m, ScreenLayout.Details);
            bool forecast = _layout.IsVisible(m, ScreenLayout.Forecast);
            _root.EnableInClassList("no-left", !left);
            _root.EnableInClassList("no-charts", !charts);
            _root.EnableInClassList("no-pipeline", !_layout.IsVisible(m, ScreenLayout.Pipeline));
            _root.EnableInClassList("no-details", !details);
            _root.EnableInClassList("no-forecast", !forecast);
            _root.EnableInClassList("details-collapsed", !details && !forecast);
            _ovPair.EnableInClassList("user-hidden", !_layout.IsVisible(m, ScreenLayout.Temp) && !_layout.IsVisible(m, ScreenLayout.Twin));
            UiUtil.Show(_monitorEmpty, m == ScreenMode.Monitor && !_layout.AnyVisible(m, ScreenLayout.OnPage(Page)));
            foreach (var kv in _tabs) kv.Value.EnableInClassList("selected", kv.Key == m);

            string screen = m == ScreenMode.Theatre ? "THEATRE" : m == ScreenMode.Monitor ? "MONITOR" : "FULL ANALYSIS";
            UiUtil.SetText(_drawerTitle, "Panels · " + screen);
            foreach (var id in ScreenLayout.All)
            {
                var (row, toggle) = _rows[id];
                bool avail = ScreenLayout.AvailableIn(m, id);
                UiUtil.Show(row, avail);
                if (!avail) continue;
                bool vis = _layout.IsVisible(m, id);
                UiUtil.SetText(toggle, vis ? "Shown · hide" : "Hidden · show");
                toggle.EnableInClassList("selected", vis);
            }
            int hidden = _layout.HiddenCount(m);
            UiUtil.SetText(_btnPanels, hidden > 0 ? "PANELS ▾ (" + hidden + " hidden)" : "PANELS ▾");
            Changed?.Invoke();
        }
    }
}
