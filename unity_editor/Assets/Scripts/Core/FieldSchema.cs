using System;
using System.Collections.Generic;

namespace Neram.Core
{
    /// <summary>JSON value kind of a replay field (see unity/schema/replay_fields.json).</summary>
    public enum FieldKind { Number, Bool, Int, Enum, String, StringEnum }

    /// <summary>How a [min, max] range is enforced: not at all, as a hard error, or as a warning.</summary>
    public enum RangeMode { None, Error, Warn }

    /// <summary>
    /// Definition of one replay field. Instances are generated into ReplayFields.g.cs from
    /// replay_fields.json; nothing here is hand-maintained.
    /// </summary>
    public sealed class FieldDef
    {
        public readonly int Id;
        public readonly string Group;
        public readonly string Name;
        public readonly FieldKind Kind;
        public readonly bool Nullable;
        public readonly string Unit;
        public readonly double Min;
        public readonly double Max;
        public readonly RangeMode RangeMode;
        public readonly int Decimals;
        public readonly bool Optional;
        public readonly string EnumName;
        public readonly string Label;
        public readonly bool Proposed;

        public FieldDef(int id, string group, string name, FieldKind kind, bool nullable, string unit, double min, double max,
            RangeMode rangeMode, int decimals, bool optional, string enumName, string label, bool proposed)
        {
            Id = id; Group = group; Name = name; Kind = kind; Nullable = nullable; Unit = unit; Min = min; Max = max;
            RangeMode = rangeMode; Decimals = decimals; Optional = optional; EnumName = enumName; Label = label; Proposed = proposed;
        }

        /// <summary>"group.name", the key used in reports and lookups.</summary>
        public string Key => Group + "." + Name;

        /// <summary>True when the field is stored as a per-frame column (everything except meta strings).</summary>
        public bool IsColumn => !(Group == "meta" && Kind == FieldKind.String);

        public override string ToString() => Key;
    }

    /// <summary>Lookup helpers over the generated field table.</summary>
    public static partial class ReplayFields
    {
        private static Dictionary<string, FieldDef> _byKey;
        private static Dictionary<string, List<FieldDef>> _byGroup;

        private static void EnsureIndex()
        {
            if (_byKey != null) return;
            var byKey = new Dictionary<string, FieldDef>(StringComparer.Ordinal);
            var byGroup = new Dictionary<string, List<FieldDef>>(StringComparer.Ordinal);
            foreach (var g in Groups) byGroup[g] = new List<FieldDef>();
            for (int i = 0; i < All.Length; i++)
            {
                var f = All[i];
                if (f.Id != i) throw new InvalidOperationException("ReplayFields ids must equal their index: " + f.Key);
                byKey[f.Key] = f;
                byGroup[f.Group].Add(f);
            }
            _byGroup = byGroup;
            _byKey = byKey;
        }

        public static int Count => All.Length;

        public static FieldDef Get(string group, string name)
        {
            EnsureIndex();
            if (_byKey.TryGetValue(group + "." + name, out var f)) return f;
            throw new KeyNotFoundException("Unknown replay field " + group + "." + name);
        }

        public static bool TryGet(string group, string name, out FieldDef field)
        {
            EnsureIndex();
            return _byKey.TryGetValue(group + "." + name, out field);
        }

        public static IReadOnlyList<FieldDef> InGroup(string group)
        {
            EnsureIndex();
            return _byGroup.TryGetValue(group, out var list) ? (IReadOnlyList<FieldDef>)list : Array.Empty<FieldDef>();
        }

        public static bool IsGroup(string group)
        {
            EnsureIndex();
            return _byGroup.ContainsKey(group);
        }

        /// <summary>The forecast fields that must be null unless Twin_Valid is VALID (rule E040/E041).</summary>
        public static readonly string[] ForecastFieldNames = BuildForecastNames();

        public static readonly int[] Horizons = { 20, 30, 60 };

        private static string[] BuildForecastNames()
        {
            var list = new List<string>();
            foreach (var h in new[] { 20, 30, 60 })
            {
                list.Add("T_pred_" + h);
                list.Add("L80_" + h);
                list.Add("U80_" + h);
                list.Add("L95_" + h);
                list.Add("U95_" + h);
                list.Add("P_below_hypo_" + h);
            }
            return list.ToArray();
        }
    }

    /// <summary>Canonical string-enum values. These names are FROZEN in the plan (section 0.4).</summary>
    public static class StringEnums
    {
        public static readonly string[] SourceTags = { "REAL_DEV", "MODEL", "SIMULATED", "ASSUMED" };
        public static readonly string[] PlantModes = { "OPEN_LOOP", "STANDIN", "TWIN_IN_LOOP" };

        public static string[] ValuesFor(string enumName)
        {
            switch (enumName)
            {
                case "SourceTag": return SourceTags;
                case "PlantMode": return PlantModes;
                default: return null;
            }
        }

        public static int IndexOf(string enumName, string value)
        {
            var values = ValuesFor(enumName);
            if (values == null || value == null) return -1;
            return Array.IndexOf(values, value);
        }
    }

    /// <summary>Integer values of the FROZEN enum names used by display rules. Resolved through the EnumRegistry
    /// so that a PROVISIONAL renumbering in config/enums.json is honoured.</summary>
    public static class EnumNames
    {
        public const string ControllerState = "ControllerState";
        public const string DegradedSubstate = "DegradedSubstate";
        public const string TwinValid = "TwinValid";
        public const string TriggerReason = "TriggerReason";
        public const string AlertCode = "AlertCode";
    }
}
