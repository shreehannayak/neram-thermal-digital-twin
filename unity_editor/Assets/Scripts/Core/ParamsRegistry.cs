using System;
using System.Collections.Generic;
using System.Globalization;
using Newtonsoft.Json.Linq;

namespace Neram.Core
{
    /// <summary>One parameter as declared in config/params.json (or in a replay header's params_used block).</summary>
    public sealed class ParamEntry
    {
        public string Name;
        /// <summary>Established value (null when not established). May be a scalar or an array (e.g. w_ch).</summary>
        public JToken Value;
        /// <summary>Labelled placeholder that lets simulations/displays run while Value is not established.</summary>
        public JToken Placeholder;
        public string Unit;
        /// <summary>FROZEN | PROVISIONAL | TBD | ASSUMED (copied verbatim, never re-interpreted).</summary>
        public string Status;
        public string Source;
        public string Owner;
        public string Purpose;
        public string UsedBy;
        /// <summary>"config/params.json v0.1" or "replay header params_used".</summary>
        public string Origin;

        public bool HasValue => Value != null && Value.Type != JTokenType.Null;
        public bool HasPlaceholder => Placeholder != null && Placeholder.Type != JTokenType.Null;

        /// <summary>Value if established, else placeholder, else null. Use IsPlaceholderInUse to label it.</summary>
        public JToken Effective => HasValue ? Value : (HasPlaceholder ? Placeholder : null);
        public bool IsPlaceholderInUse => !HasValue && HasPlaceholder;

        /// <summary>Scalar numeric effective value, or NaN when not established and no placeholder.</summary>
        public double EffectiveScalar
        {
            get
            {
                var t = Effective;
                if (t == null) return double.NaN;
                if (t.Type == JTokenType.Integer || t.Type == JTokenType.Float) return (double)t;
                return double.NaN;
            }
        }

        /// <summary>Human-readable value with its status, e.g. "36.0 degC (PLACEHOLDER, status TBD)".</summary>
        public string DisplayValue()
        {
            var t = Effective;
            string v;
            if (t == null) v = "not established";
            else if (t.Type == JTokenType.Array) v = "[" + string.Join(", ", ToStrings((JArray)t)) + "]";
            else v = TokenToString(t);
            if (t != null && Unit != null && Unit != "1" && Unit != "-") v += " " + DisplayUnits.Of(Unit);
            if (IsPlaceholderInUse) v += " (PLACEHOLDER)";
            return v;
        }

        private static IEnumerable<string> ToStrings(JArray a)
        {
            foreach (var x in a) yield return TokenToString(x);
        }

        private static string TokenToString(JToken t)
        {
            if (t.Type == JTokenType.Float) return ((double)t).ToString("0.###", CultureInfo.InvariantCulture);
            if (t.Type == JTokenType.Integer) return ((long)t).ToString(CultureInfo.InvariantCulture);
            if (t.Type == JTokenType.Null) return "null";
            return t.ToString();
        }
    }

    /// <summary>
    /// Read-only view of config/params.json, optionally overlaid with the params_used snapshot from a replay
    /// header. Unity only DISPLAYS these values; it never uses them to make a controller decision.
    /// </summary>
    public sealed class ParamsRegistry
    {
        public readonly Dictionary<string, ParamEntry> Entries = new Dictionary<string, ParamEntry>(StringComparer.Ordinal);
        public string ParamsVersion { get; private set; }
        public string SpecVersion { get; private set; }
        public string Origin { get; private set; }

        /// <summary>Notes produced when a header snapshot disagrees with the config file.</summary>
        public readonly List<string> Notes = new List<string>();

        public static readonly string[] AllowedStatuses = { "FROZEN", "PROVISIONAL", "TBD", "ASSUMED" };

        public static ParamsRegistry FromJson(string json, string origin)
        {
            var root = JObject.Parse(json);
            var reg = new ParamsRegistry
            {
                ParamsVersion = (string)root["params_version"],
                SpecVersion = (string)root["spec_version"],
                Origin = origin,
            };
            var ps = root["params"] as JObject ?? throw new FormatException("params.json: missing 'params' object");
            foreach (var p in ps.Properties())
                reg.Entries[p.Name] = ParseEntry(p.Name, p.Value as JObject, origin + " v" + reg.ParamsVersion);
            return reg;
        }

        public static ParamsRegistry Empty(string origin) => new ParamsRegistry { Origin = origin, ParamsVersion = "none", SpecVersion = "none" };

        private static ParamEntry ParseEntry(string name, JObject o, string origin)
        {
            if (o == null) throw new FormatException($"parameter '{name}' is not an object");
            var e = new ParamEntry
            {
                Name = name,
                Value = o["value"],
                Placeholder = o["placeholder"],
                Unit = (string)o["unit"],
                Status = (string)o["status"],
                Source = (string)o["source"],
                Owner = (string)o["owner"],
                Purpose = (string)o["purpose"],
                UsedBy = (string)o["used_by"],
                Origin = origin,
            };
            if (Array.IndexOf(AllowedStatuses, e.Status) < 0)
                throw new FormatException($"parameter '{name}': status '{e.Status}' is not one of FROZEN/PROVISIONAL/TBD/ASSUMED");
            if (e.Status == "TBD" && e.HasValue)
                throw new FormatException($"parameter '{name}': status TBD but a value is set (use a placeholder or change the status)");
            return e;
        }

        /// <summary>Overlay a replay header's params_used block. Header entries win for display because they are what
        /// the replay was generated with; every disagreement with the config file is recorded in Notes.</summary>
        public void OverlayHeaderSnapshot(JObject paramsUsed, string scenarioId)
        {
            if (paramsUsed == null) return;
            foreach (var p in paramsUsed.Properties())
            {
                var e = ParseEntry(p.Name, p.Value as JObject, "replay header params_used (" + scenarioId + ")");
                if (Entries.TryGetValue(p.Name, out var cfg))
                {
                    if (!JToken.DeepEquals(cfg.Effective, e.Effective) || cfg.Status != e.Status)
                        Notes.Add($"{p.Name}: replay used {e.DisplayValue()} [{e.Status}], config has {cfg.DisplayValue()} [{cfg.Status}]");
                }
                else
                {
                    Notes.Add($"{p.Name}: present only in the replay header ({e.DisplayValue()} [{e.Status}])");
                }
                Entries[p.Name] = e;
            }
        }

        public bool TryGet(string name, out ParamEntry e) => Entries.TryGetValue(name, out e);

        public ParamEntry GetOrNull(string name) => Entries.TryGetValue(name, out var e) ? e : null;
    }

    /// <summary>Display spelling of unit strings used in config files.</summary>
    public static class DisplayUnits
    {
        public static string Of(string unit)
        {
            switch (unit)
            {
                case null: return "";
                case "degC": return "°C";
                case "degC^2": return "°C²";
                case "degC/h at 100% on all channels": return "°C/h at 100 % on all channels";
                case "%/degC": return "%/°C";
                case "%/(degC*s)": return "%/(°C·s)";
                case "-":
                case "1": return "";
                default: return unit;
            }
        }
    }
}
