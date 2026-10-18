using System.Collections.Generic;
using System.Linq;
using Neram.Core;
using UnityEngine.UIElements;

namespace Neram.Unity
{
    /// <summary>
    /// Parameters drawer. Default view: the key parameters only, grouped and named in plain language, each with a clear
    /// state (SET / PLACEHOLDER / NOT SET YET) and who supplies the real value. "All parameters (advanced)" shows the
    /// complete audit table from config/params.json overlaid with the replay's params_used snapshot.
    /// Unity displays these values; it never uses them to make a decision. (Key view: Sai, 18 Oct 2026)
    /// </summary>
    public sealed class ParametersPanel : IReplayView
    {
        private sealed class Key
        {
            public string Name, Label, Meaning;
            public Key(string n, string l, string m) { Name = n; Label = l; Meaning = m; }
        }

        private static readonly (string group, Key[] keys)[] Groups =
        {
            ("Patient temperature", new[]
            {
                new Key("t_hypo_degC", "Hypothermia line", "Below this the patient counts as hypothermic. The forecast reports the chance of falling below it."),
                new Key("t_target_degC", "Warming target", "The temperature the controller warms towards. Set by a clinician."),
            }),
            ("Digital twin", new[]
            {
                new Key("ts_twin_s", "Twin update interval", "How often the twin recomputes its estimate and forecast."),
                new Key("sd_degrade_degC", "Reliability limit", "If the estimate's uncertainty (1 SD) is not below this, the twin is DEGRADED and the forecast is hidden."),
            }),
            ("Predictive warming trigger", new[]
            {
                new Key("p_trigger", "Start probability", "Warming is started when the predicted chance of hypothermia reaches this."),
                new Key("p_release", "Stop probability", "Predictive warming ends when the chance falls below this."),
                new Key("n_confirm_updates", "Confirmations needed", "Consecutive twin updates above the start probability before acting."),
            }),
            ("Controller", new[]
            {
                new Key("band_target_degC", "Target band", "How close to the target counts as 'reached'."),
                new Key("d_pred_max_pct", "Max heat, predictive", "Heater ceiling while warming pre-emptively."),
                new Key("d_active_max_pct", "Max heat, active", "Heater ceiling while actively warming."),
            }),
            ("Assumed warming effect (illustrative)", new[]
            {
                new Key("k_heat_degC_per_h", "Warming strength", "Assumed temperature rise per hour with all four channels at 100 %. No real data exist."),
                new Key("tau_heat_min", "Warming delay", "Assumed lag before heating shows up in body temperature."),
                new Key("w_ch", "Channel weights", "Assumed share of each hand/foot channel in the warming effect."),
            }),
            ("Hardware safety limits", new[]
            {
                new Key("t_mod_trip_degC", "Module trip temperature", "Module temperature at which the controller shuts heating off."),
                new Key("t_hw_cutoff_degC", "Hardware cutoff", "Independent hardware thermal cutoff."),
                new Key("t_surface_limit_degC", "Skin-contact limit", "Maximum allowed surface temperature against the skin."),
            }),
        };

        private readonly VisualElement _drawer;
        private readonly ScrollView _list;
        private readonly Button _modeButton;
        private readonly VisualElement _filterRow;
        private readonly List<Button> _filters = new List<Button>();
        private ReplaySession _s;
        private string _status = "ALL";
        private bool _advanced;

        public ParametersPanel(VisualElement root)
        {
            _drawer = UiUtil.Req<VisualElement>(root, "drawer-params");
            var head = UiUtil.Box("drawer-head");
            head.Add(UiUtil.Label("Parameters", "drawer-title"));
            _modeButton = UiUtil.Button("All parameters (advanced)", ToggleMode, "btn-ghost");
            head.Add(_modeButton);
            head.Add(UiUtil.Button("Close", () => UiUtil.Show(_drawer, false), "btn-ghost"));
            _drawer.Add(head);

            _filterRow = UiUtil.Box("row");
            _filterRow.style.marginTop = 6;
            _filterRow.style.marginBottom = 6;
            foreach (var st in new[] { "ALL", "FROZEN", "PROVISIONAL", "TBD", "ASSUMED" })
            {
                var s = st;
                Button b = null;
                b = UiUtil.Button(st, () => { _status = s; UiUtil.Select(_filters, b); Render(); }, "btn-ghost");
                _filters.Add(b);
                _filterRow.Add(b);
            }
            UiUtil.Select(_filters, _filters[0]);
            UiUtil.Show(_filterRow, false);
            _drawer.Add(_filterRow);

            _list = new ScrollView();
            _list.style.flexGrow = 1;
            _drawer.Add(_list);
        }

        private void ToggleMode()
        {
            _advanced = !_advanced;
            _modeButton.text = _advanced ? "Key parameters" : "All parameters (advanced)";
            UiUtil.Show(_filterRow, _advanced);
            Render();
        }

        public void Toggle()
        {
            UiUtil.Show(_drawer, !UiUtil.IsShown(_drawer));
            if (UiUtil.IsShown(_drawer)) Render();
        }

        public bool IsOpen => UiUtil.IsShown(_drawer);
        public void Close() => UiUtil.Show(_drawer, false);

        public void Bind(ReplaySession s)
        {
            _s = s;
            if (IsOpen) Render();
        }

        private void Render()
        {
            _list.Clear();
            if (_s == null) { _list.Add(UiUtil.Label("No replay loaded.", "card-text")); return; }
            if (_advanced) RenderAll(); else RenderKey();
        }

        // ------------------------------------------------------------------ key view

        private enum State { Set, Placeholder, Assumed, NotSet }

        private static State StateOf(ParamEntry e) =>
            e.HasValue ? State.Set : e.Status == "ASSUMED" && e.IsPlaceholderInUse ? State.Assumed : e.IsPlaceholderInUse ? State.Placeholder : State.NotSet;

        /// <summary>Who supplies the real value (one name per person, so the summary line stays short).</summary>
        private static string Supplier(ParamEntry e)
        {
            if (e.Name == "t_target_degC" || (e.Source ?? "").StartsWith("Clinician")) return "a clinician";
            return e.Owner ?? "?";
        }

        private static string SupplierDetail(ParamEntry e)
        {
            if (e.Name == "t_target_degC" || (e.Source ?? "").StartsWith("Clinician")) return "real value: a clinician";
            if (e.Owner == "Sai" && e.Status == "TBD") return "real value: Sai (development fit)";
            if (e.Owner == "Sai") return "real value: Sai (design choice)";
            return "real value: " + e.Owner;
        }

        private void RenderKey()
        {
            var p = _s.Params;
            int set = 0, ph = 0, none = 0, assumed = 0;
            var waiting = new SortedDictionary<string, int>();
            foreach (var (_, keys) in Groups)
                foreach (var k in keys)
                {
                    var e = p.GetOrNull(k.Name);
                    if (e == null) continue;
                    var st = StateOf(e);
                    if (st == State.Set) set++;
                    else if (st == State.Assumed) assumed++;
                    else { if (st == State.Placeholder) ph++; else none++; var w = Supplier(e); waiting[w] = waiting.TryGetValue(w, out var n) ? n + 1 : 1; }
                }

            var sum = UiUtil.Box("kp-summary");
            sum.Add(Tile(set.ToString(), "set", "kp-tile-ok"));
            sum.Add(Tile(ph.ToString(), "placeholder", "kp-tile-ph"));
            sum.Add(Tile(none.ToString(), "not set yet", "kp-tile-none"));
            sum.Add(Tile(assumed.ToString(), "assumed", "kp-tile-assumed"));
            _list.Add(sum);
            var intro = UiUtil.Label("The numbers behind this replay. PLACEHOLDER = a labelled stand-in so the demo can run, replaced when the real value arrives. ASSUMED = illustrative on purpose, because no warming data exist. Unity only displays these; it never decides anything with them.", "kp-intro");
            _list.Add(intro);
            if (waiting.Count > 0)
                _list.Add(UiUtil.Label("Real values still to come from: " + string.Join(" · ", waiting.Select(w => w.Key + " (" + w.Value + ")")), "kp-waiting"));

            foreach (var (group, keys) in Groups)
            {
                var card = UiUtil.Box("kp-group");
                card.Add(UiUtil.Label(group, "kp-group-title"));
                foreach (var k in keys)
                {
                    var e = p.GetOrNull(k.Name);
                    if (e == null) continue;
                    var st = StateOf(e);
                    var row = UiUtil.Box("kp-row");
                    var left = UiUtil.Box("kp-left");
                    left.Add(UiUtil.Label(k.Label, "kp-name"));
                    left.Add(UiUtil.Label(k.Meaning, "kp-meaning"));
                    row.Add(left);
                    var right = UiUtil.Box("kp-right");
                    string v = st == State.NotSet ? "—" : e.DisplayValue().Replace(" (PLACEHOLDER)", "");
                    right.Add(UiUtil.Label(v, "kp-value", st == State.Set ? "kp-value-set" : "kp-value-ph"));
                    var chip = st == State.Set ? UiUtil.Chip("SET", "kp-chip-ok")
                             : st == State.Placeholder ? UiUtil.Chip("PLACEHOLDER", "chip-placeholder")
                             : st == State.Assumed ? UiUtil.Chip("ASSUMED", "chip-status-ASSUMED")
                             : UiUtil.Chip("NOT SET YET", "kp-chip-none");
                    right.Add(chip);
                    if (st == State.Assumed) right.Add(UiUtil.Label("illustrative: no warming data exist", "kp-who"));
                    else if (st != State.Set) right.Add(UiUtil.Label(SupplierDetail(e), "kp-who"));
                    row.Add(right);
                    row.tooltip = k.Name + "  ·  status " + e.Status + "  ·  owner " + e.Owner + "\n" + (e.Source ?? "") + "\n" + e.Origin;
                    card.Add(row);
                }
                _list.Add(card);
            }
        }

        private static VisualElement Tile(string big, string label, string cls)
        {
            var t = UiUtil.Box("kp-tile", cls);
            t.Add(UiUtil.Label(big, "kp-tile-big"));
            t.Add(UiUtil.Label(label, "kp-tile-label"));
            return t;
        }

        // ------------------------------------------------------------------ advanced (complete audit table)

        private void RenderAll()
        {
            var p = _s.Params;
            _list.Add(UiUtil.Label("Complete list for audit. Status is copied verbatim from the source: FROZEN (agreed), PROVISIONAL (usable, may change once), " +
                                   "TBD (not established; a value shown is a labelled PLACEHOLDER), ASSUMED (no data exist; illustrative).", "card-text"));
            _list.Add(UiUtil.Label("params " + p.Origin + "  ·  version " + p.ParamsVersion + "  ·  replay generated with params v" + _s.Header.ParamsVersion, "t-xs", "c-3"));
            if (p.Notes.Count > 0)
            {
                var notes = UiUtil.Box("card");
                notes.Add(UiUtil.Label("Replay header snapshot (params_used) differs from config", "card-title"));
                foreach (var n in p.Notes) notes.Add(UiUtil.Label("• " + n, "card-text"));
                _list.Add(notes);
            }
            var head = UiUtil.Box("ptable-row");
            foreach (var (txt, cls) in new[] { ("parameter", "ptable-name"), ("value (effective)", "ptable-value"), ("status", "ptable-status"), ("owner", "ptable-owner"), ("source / origin", "ptable-source") })
                head.Add(UiUtil.Label(txt, cls, "c-3"));
            _list.Add(head);
            foreach (var e in p.Entries.Values.OrderBy(x => x.Name))
            {
                if (_status != "ALL" && e.Status != _status) continue;
                var row = UiUtil.Box("ptable-row");
                row.Add(UiUtil.Label(e.Name, "ptable-name"));
                var val = UiUtil.Label(e.DisplayValue(), "ptable-value");
                if (e.IsPlaceholderInUse || !e.HasValue) val.AddToClassList("c-2");
                row.Add(val);
                var stBox = UiUtil.Box("ptable-status", "col");
                stBox.Add(UiUtil.Chip(e.Status, UiUtil.StatusChipClass(e.Status)));
                if (e.IsPlaceholderInUse) stBox.Add(UiUtil.Chip("PLACEHOLDER", "chip-placeholder"));
                row.Add(stBox);
                row.Add(UiUtil.Label(e.Owner ?? "", "ptable-owner"));
                row.Add(UiUtil.Label((e.Source ?? "") + "\n" + e.Origin, "ptable-source"));
                row.tooltip = (e.Purpose ?? "") + (e.UsedBy != null ? "\nused by: " + e.UsedBy : "");
                _list.Add(row);
            }
            var d = _s.Display;
            _list.Add(UiUtil.Box("sep"));
            _list.Add(UiUtil.Label("Display-only settings (" + d.Origin + "): not model, controller or clinical parameters", "card-title"));
            foreach (var kv in d.Settings.OrderBy(k => k.Key))
            {
                var row = UiUtil.Box("ptable-row");
                row.Add(UiUtil.Label(kv.Key, "ptable-name"));
                row.Add(UiUtil.Label(Fmt.Number(kv.Value.Value, 2) + " " + DisplayUnits.Of(kv.Value.Unit), "ptable-value"));
                var stBox = UiUtil.Box("ptable-status", "col");
                stBox.Add(UiUtil.Chip(kv.Value.Status, UiUtil.StatusChipClass(kv.Value.Status)));
                row.Add(stBox);
                row.Add(UiUtil.Label("Sai", "ptable-owner"));
                row.Add(UiUtil.Label(kv.Value.Purpose ?? "", "ptable-source"));
                _list.Add(row);
            }
        }

        public void ShowFrame(int frame) { }

        public void Unbind()
        {
            _s = null;
            if (IsOpen) Render();
        }
    }
}
