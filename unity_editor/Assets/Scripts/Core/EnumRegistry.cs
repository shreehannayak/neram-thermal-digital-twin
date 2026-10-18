using System;
using System.Collections.Generic;
using Newtonsoft.Json.Linq;

namespace Neram.Core
{
    public sealed class EnumValue
    {
        public int Value;
        public string Name;
        public string Label;
        public string Description;
        /// <summary>"none" | "info" | "warning" | "critical" (AlertCode only); null otherwise.</summary>
        public string Severity;
    }

    public sealed class EnumDef
    {
        public string Name;
        public bool IsString;
        public string NamesStatus;
        public string ValuesStatus;
        public readonly Dictionary<int, EnumValue> ByValue = new Dictionary<int, EnumValue>();
        public readonly Dictionary<string, EnumValue> ByName = new Dictionary<string, EnumValue>(StringComparer.Ordinal);

        public void Add(EnumValue v)
        {
            if (!IsString)
            {
                if (ByValue.ContainsKey(v.Value)) throw new FormatException($"Enum {Name}: duplicate value {v.Value}");
                ByValue[v.Value] = v;
            }
            if (ByName.ContainsKey(v.Name)) throw new FormatException($"Enum {Name}: duplicate name {v.Name}");
            ByName[v.Name] = v;
        }
    }

    /// <summary>
    /// Enum names, integers and display labels. Loaded from config/enums.json (owner: Sai).
    /// Names are FROZEN in the plan; integers are PROVISIONAL until CP2, so code never hard-codes
    /// an integer: it asks the registry for the value of a frozen name.
    /// </summary>
    public sealed class EnumRegistry
    {
        public readonly Dictionary<string, EnumDef> Enums = new Dictionary<string, EnumDef>(StringComparer.Ordinal);
        public string SpecVersion { get; private set; }
        /// <summary>Where the registry came from: "config/enums.json" or "built-in default (plan v0.1)".</summary>
        public string Origin { get; private set; }

        public static readonly string[] RequiredEnums =
            { "ControllerState", "DegradedSubstate", "TwinValid", "TriggerReason", "AlertCode" };

        public static EnumRegistry FromJson(string json, string origin)
        {
            var root = JObject.Parse(json);
            var reg = new EnumRegistry { SpecVersion = (string)root["spec_version"], Origin = origin };
            var enums = root["enums"] as JObject ?? throw new FormatException("enums.json: missing 'enums' object");
            foreach (var prop in enums.Properties())
            {
                var obj = prop.Value as JObject ?? throw new FormatException($"enums.json: '{prop.Name}' is not an object");
                var def = new EnumDef
                {
                    Name = prop.Name,
                    IsString = (string)obj["type"] == "string",
                    NamesStatus = (string)obj["names_status"],
                    ValuesStatus = (string)obj["values_status"],
                };
                var values = obj["values"] as JArray ?? throw new FormatException($"enums.json: '{prop.Name}.values' missing");
                foreach (var t in values)
                {
                    var v = new EnumValue
                    {
                        Name = def.IsString ? (string)t["value"] : (string)t["name"],
                        Label = (string)t["label"],
                        Description = (string)t["description"],
                        Severity = (string)t["severity"],
                    };
                    if (!def.IsString)
                    {
                        var tok = t["value"];
                        if (tok == null || tok.Type != JTokenType.Integer)
                            throw new FormatException($"enums.json: {prop.Name} value must be an integer");
                        v.Value = (int)tok;
                    }
                    if (string.IsNullOrEmpty(v.Name)) throw new FormatException($"enums.json: {prop.Name} has a value without a name");
                    if (string.IsNullOrEmpty(v.Label)) v.Label = v.Name;
                    def.Add(v);
                }
                reg.Enums[def.Name] = def;
            }
            foreach (var req in RequiredEnums)
                if (!reg.Enums.ContainsKey(req)) throw new FormatException("enums.json: required enum missing: " + req);
            return reg;
        }

        public EnumDef Get(string enumName)
        {
            if (Enums.TryGetValue(enumName, out var d)) return d;
            throw new KeyNotFoundException("Enum not defined: " + enumName);
        }

        public bool IsKnown(string enumName, int value) => Enums.TryGetValue(enumName, out var d) && d.ByValue.ContainsKey(value);

        /// <summary>Integer value of a FROZEN name, e.g. ValueOf("ControllerState", "SAFETY_SHUTDOWN").</summary>
        public int ValueOf(string enumName, string name)
        {
            var d = Get(enumName);
            if (d.ByName.TryGetValue(name, out var v)) return v.Value;
            throw new KeyNotFoundException($"{enumName} has no value named {name}");
        }

        public string NameOf(string enumName, int value)
        {
            if (Enums.TryGetValue(enumName, out var d) && d.ByValue.TryGetValue(value, out var v)) return v.Name;
            return "UNKNOWN(" + value + ")";
        }

        public string LabelOf(string enumName, int value)
        {
            if (Enums.TryGetValue(enumName, out var d) && d.ByValue.TryGetValue(value, out var v)) return v.Label;
            return "Unknown value " + value;
        }

        public EnumValue Find(string enumName, int value)
        {
            if (Enums.TryGetValue(enumName, out var d) && d.ByValue.TryGetValue(value, out var v)) return v;
            return null;
        }

        /// <summary>The plan v0.1 enumeration (section 0.4), used only when config/enums.json cannot be read.
        /// The UI shows a warning whenever this fallback is active.</summary>
        public static EnumRegistry BuiltInDefault()
        {
            const string json = @"{
 ""spec_version"": ""0.1"",
 ""enums"": {
  ""ControllerState"": {""type"":""uint8"",""values"":[
    {""value"":0,""name"":""NORMAL"",""label"":""Normal""},
    {""value"":1,""name"":""PREDICTIVE_WARMING"",""label"":""Predictive warming""},
    {""value"":2,""name"":""ACTIVE_WARMING"",""label"":""Active warming""},
    {""value"":3,""name"":""TARGET_MAINTENANCE"",""label"":""Target maintenance""},
    {""value"":4,""name"":""CLINICIAN_WARMING"",""label"":""Clinician warming""},
    {""value"":5,""name"":""TWIN_DEGRADED"",""label"":""Twin degraded""},
    {""value"":6,""name"":""SAFETY_SHUTDOWN"",""label"":""Safety shutdown""}]},
  ""DegradedSubstate"": {""type"":""uint8"",""values"":[
    {""value"":0,""name"":""NONE"",""label"":""-""},
    {""value"":1,""name"":""MONITOR"",""label"":""Monitor only""},
    {""value"":2,""name"":""CLINICIAN_FIXED"",""label"":""Clinician fixed demand""}]},
  ""TwinValid"": {""type"":""uint8"",""values"":[
    {""value"":0,""name"":""NO_DATA"",""label"":""No data""},
    {""value"":1,""name"":""INITIALISING"",""label"":""Initialising""},
    {""value"":2,""name"":""VALID"",""label"":""Valid""},
    {""value"":3,""name"":""DEGRADED"",""label"":""Degraded""}]},
  ""TriggerReason"": {""type"":""uint8"",""values"":[
    {""value"":0,""name"":""NONE"",""label"":""None""},
    {""value"":1,""name"":""FORECAST_P20"",""label"":""Forecast risk (+20 min)""},
    {""value"":2,""name"":""FORECAST_P30"",""label"":""Forecast risk (+30 min)""},
    {""value"":3,""name"":""TEST_BELOW_HYPO"",""label"":""T_est below t_hypo""},
    {""value"":4,""name"":""CLINICIAN_START"",""label"":""Clinician START""},
    {""value"":5,""name"":""TARGET_REACHED"",""label"":""Target reached""},
    {""value"":6,""name"":""TARGET_LOST"",""label"":""Target lost""},
    {""value"":7,""name"":""CLINICIAN_STOP"",""label"":""Clinician STOP""},
    {""value"":8,""name"":""SAFETY_FAULT"",""label"":""Safety fault""},
    {""value"":9,""name"":""TWIN_DEGRADED"",""label"":""Twin degraded""},
    {""value"":10,""name"":""TWIN_RECOVERED"",""label"":""Twin recovered""},
    {""value"":11,""name"":""CLINICIAN_RESET"",""label"":""Clinician RESET""}]},
  ""AlertCode"": {""type"":""uint8"",""values"":[
    {""value"":0,""name"":""NONE"",""label"":""No alert"",""severity"":""none""},
    {""value"":1,""name"":""FORECAST_RISK_20_30"",""label"":""Forecast risk at +20/+30 min"",""severity"":""info""},
    {""value"":2,""name"":""FORECAST_RISK_60_INFO"",""label"":""Forecast risk at +60 min (information only)"",""severity"":""info""},
    {""value"":3,""name"":""TWIN_DEGRADED"",""label"":""Twin unreliable - monitoring only"",""severity"":""warning""},
    {""value"":4,""name"":""CHANNEL_FAULT"",""label"":""Channel fault"",""severity"":""warning""},
    {""value"":5,""name"":""SAFETY_SHUTDOWN"",""label"":""Safety shutdown"",""severity"":""critical""},
    {""value"":6,""name"":""DATA_STALE"",""label"":""Data stale"",""severity"":""warning""},
    {""value"":7,""name"":""CLINICIAN_STOP_ACK"",""label"":""Clinician STOP acknowledged"",""severity"":""info""},
    {""value"":8,""name"":""RESET_BLOCKED"",""label"":""Reset blocked - condition still present"",""severity"":""critical""}]}
 }
}";
            return FromJson(json, "built-in default (plan v0.1)");
        }
    }
}
