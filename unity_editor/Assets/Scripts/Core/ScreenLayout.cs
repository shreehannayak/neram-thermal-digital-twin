using System;
using System.Collections.Generic;

namespace Neram.Core
{
    /// <summary>The three screens of the viewer. All three show the same replay session and the same replay clock.</summary>
    public enum ScreenMode
    {
        /// <summary>Default: the 3D operating theatre and patient, with a slim header, replay controls and camera tools.</summary>
        Theatre,
        /// <summary>Dedicated monitoring screen: values, pipeline, the three graphs and the forecast in large type.</summary>
        Monitor,
        /// <summary>The full engineering dashboard over the 3D view (every panel, region details, drawers).</summary>
        Analysis,
    }

    /// <summary>Pages of the MONITOR screen (v4): one subject per page so values and graphs are never squeezed together.</summary>
    public enum MonitorPage
    {
        /// <summary>Temperature signal, twin estimate ± SD, controller / alerts / faults, CH1–CH4, quality, N/A vitals.</summary>
        Values,
        /// <summary>Temperature graphs A and B stacked at full width.</summary>
        Graphs,
        /// <summary>Graph C (warming-channel commands CH1–CH4) at full size.</summary>
        Channels,
        /// <summary>The five-stage pipeline and the +20 / +30 / +60 min forecast.</summary>
        Flow,
    }

    /// <summary>
    /// Display-only panel visibility per screen (no replay values, no clock). Every hideable panel has an id; each screen has
    /// its own visible set with sensible defaults: THEATRE hides every secondary panel, FULL ANALYSIS shows all of them and
    /// MONITOR shows every panel it contains. Hiding, "hide all", "show panels" and "reset layout" only change these sets.
    /// </summary>
    public sealed class ScreenLayout
    {
        // Panel ids (also used as keys in the Panels drawer).
        public const string Controller = "controller";
        public const string Temp = "temp";
        public const string Twin = "twin";
        public const string ControllerInfo = "ctrlinfo";
        public const string Channels = "channels";
        public const string Quality = "quality";
        public const string Unavailable = "na";
        public const string Pipeline = "pipeline";
        public const string Details = "details";
        public const string Forecast = "forecast";
        public const string ChartA = "chartA";
        public const string ChartB = "chartB";
        public const string ChartC = "chartC";
        public const string Legend = "legend";
        public const string Safety = "safety";
        public const string FaultStrip = "faultstrip";
        public const string Labels = "labels";

        /// <summary>Every panel id in display order (Panels drawer order).</summary>
        public static readonly string[] All =
        {
            Controller, Temp, Twin, ControllerInfo, Channels, Quality, Unavailable, Pipeline, Details, Forecast, ChartA, ChartB,
            ChartC, Legend, Safety, FaultStrip, Labels,
        };

        /// <summary>Panels of the left column (the column disappears when all of them are hidden).</summary>
        public static readonly string[] LeftColumn = { Controller, Temp, Twin, ControllerInfo, Channels, Quality, Unavailable };

        /// <summary>The three graphs (the chart strip disappears when all of them are hidden).</summary>
        public static readonly string[] Charts = { ChartA, ChartB, ChartC };

        private static readonly Dictionary<string, string> TitleMap = new Dictionary<string, string>
        {
            { Controller, "Controller status banner" },
            { Temp, "Temperature signal card" },
            { Twin, "Model (twin) estimate card" },
            { ControllerInfo, "Controller · alerts · faults · safety" },
            { Channels, "Warming channels CH1–CH4" },
            { Quality, "Signal quality · data availability" },
            { Unavailable, "HR · SpO₂ · MAP (N/A)" },
            { Pipeline, "Pipeline (5 stages)" },
            { Details, "Selected-region details" },
            { Forecast, "Forecast +20 / +30 / +60 min" },
            { ChartA, "Graph A · temperature signal" },
            { ChartB, "Graph B · measurement vs twin" },
            { ChartC, "Graph C · channel commands" },
            { Legend, "View-mode legend (Internal / Thermal / Exploded)" },
            { Safety, "Safety-shutdown banner" },
            { FaultStrip, "Channel-fault notice" },
            { Labels, "3D labels over the scene" },
        };

        private readonly Dictionary<ScreenMode, HashSet<string>> _visible = new Dictionary<ScreenMode, HashSet<string>>();

        public ScreenLayout()
        {
            foreach (ScreenMode m in Enum.GetValues(typeof(ScreenMode))) Reset(m);
        }

        public static string Title(string id) => TitleMap.TryGetValue(id, out var t) ? t : id;

        /// <summary>Panels shown on a MONITOR page.</summary>
        public static string[] OnPage(MonitorPage page)
        {
            switch (page)
            {
                case MonitorPage.Graphs: return new[] { ChartA, ChartB };
                case MonitorPage.Channels: return new[] { ChartC };
                case MonitorPage.Flow: return new[] { Pipeline, Forecast };
                default: return LeftColumn;
            }
        }

        /// <summary>Page title for the monitor's page buttons.</summary>
        public static string PageTitle(MonitorPage page) =>
            page == MonitorPage.Graphs ? "TEMPERATURE GRAPHS" : page == MonitorPage.Channels ? "CHANNEL GRAPH" :
            page == MonitorPage.Flow ? "PIPELINE · FORECAST" : "VALUES";

        /// <summary>Whether a panel exists on a screen. The monitor has no 3D view, so 3D-only panels are not part of it.</summary>
        public static bool AvailableIn(ScreenMode mode, string id)
        {
            if (Array.IndexOf(All, id) < 0) return false;
            if (mode == ScreenMode.Monitor)
                return id != Details && id != Legend && id != Labels && id != FaultStrip;
            return true;
        }

        /// <summary>
        /// Default visibility. THEATRE: only what the audience must not miss (the latched safety banner, the legend of a
        /// view mode the presenter chose, the compact 3D labels); every statistic, graph and panel is hidden.
        /// MONITOR and FULL ANALYSIS: every available panel is shown.
        /// </summary>
        public static bool DefaultVisible(ScreenMode mode, string id)
        {
            if (!AvailableIn(mode, id)) return false;
            if (mode == ScreenMode.Theatre) return id == Safety || id == Legend || id == Labels;
            return true;
        }

        public bool IsVisible(ScreenMode mode, string id) => AvailableIn(mode, id) && _visible[mode].Contains(id);

        public void Set(ScreenMode mode, string id, bool visible)
        {
            if (!AvailableIn(mode, id)) return;
            if (visible) _visible[mode].Add(id);
            else _visible[mode].Remove(id);
        }

        public void Toggle(ScreenMode mode, string id) => Set(mode, id, !IsVisible(mode, id));

        /// <summary>HIDE ALL PANELS: leaves only the theatre / patient (the safety banner is hidden too; the header still
        /// states the controller state).</summary>
        public void HideAll(ScreenMode mode) => _visible[mode].Clear();

        /// <summary>SHOW PANELS: every panel available on this screen.</summary>
        public void ShowAll(ScreenMode mode)
        {
            foreach (var id in All) if (AvailableIn(mode, id)) _visible[mode].Add(id);
        }

        /// <summary>RESET LAYOUT: the screen's default set.</summary>
        public void Reset(ScreenMode mode)
        {
            var set = new HashSet<string>();
            foreach (var id in All) if (DefaultVisible(mode, id)) set.Add(id);
            _visible[mode] = set;
        }

        public int AvailableCount(ScreenMode mode)
        {
            int n = 0;
            foreach (var id in All) if (AvailableIn(mode, id)) n++;
            return n;
        }

        public int HiddenCount(ScreenMode mode) => AvailableCount(mode) - _visible[mode].Count;

        public bool AnyVisible(ScreenMode mode, string[] ids)
        {
            foreach (var id in ids) if (IsVisible(mode, id)) return true;
            return false;
        }
    }
}
