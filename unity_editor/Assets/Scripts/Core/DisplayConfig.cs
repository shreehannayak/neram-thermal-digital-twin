using System;
using System.Collections.Generic;
using Newtonsoft.Json.Linq;

namespace Neram.Core
{
    public sealed class DisplaySetting
    {
        public string Name;
        public double Value;
        public string Unit;
        public string Status;
        public string Purpose;
    }

    /// <summary>
    /// DISPLAY-ONLY settings from config/unity_display.json (owner Sai). These decide what the UI draws
    /// (flag thresholds, window widths, axis padding); they are never model, controller or clinical parameters.
    /// </summary>
    public sealed class DisplayConfig
    {
        public readonly Dictionary<string, DisplaySetting> Settings = new Dictionary<string, DisplaySetting>(StringComparer.Ordinal);
        public string Version { get; private set; }
        public string Origin { get; private set; }

        public static readonly string[] Required =
        {
            "flag_p_outlier_display", "flag_p_level_shift_display", "history_window_min", "forecast_window_min",
            "y_axis_min_span_degC", "y_axis_padding_degC", "trend_deadband_degC", "module_label_offset_m",
        };

        public static DisplayConfig FromJson(string json, string origin)
        {
            var root = JObject.Parse(json);
            var cfg = new DisplayConfig { Version = (string)root["display_config_version"], Origin = origin };
            var s = root["settings"] as JObject ?? throw new FormatException("unity_display.json: missing 'settings'");
            foreach (var p in s.Properties())
            {
                var o = p.Value as JObject ?? throw new FormatException("unity_display.json: '" + p.Name + "' is not an object");
                var v = o["value"];
                if (v == null || (v.Type != JTokenType.Integer && v.Type != JTokenType.Float))
                    throw new FormatException("unity_display.json: '" + p.Name + "' needs a numeric value");
                cfg.Settings[p.Name] = new DisplaySetting
                {
                    Name = p.Name, Value = (double)v, Unit = (string)o["unit"], Status = (string)o["status"], Purpose = (string)o["purpose"],
                };
            }
            foreach (var r in Required)
                if (!cfg.Settings.ContainsKey(r)) throw new FormatException("unity_display.json: missing setting " + r);
            return cfg;
        }

        public double this[string name] => Settings[name].Value;

        public double FlagOutlier => this["flag_p_outlier_display"];
        public double FlagLevelShift => this["flag_p_level_shift_display"];
        public double HistoryWindowS => this["history_window_min"] * 60.0;
        public double ForecastWindowS => this["forecast_window_min"] * 60.0;
        public double YMinSpan => this["y_axis_min_span_degC"];
        public double YPadding => this["y_axis_padding_degC"];
        public double TrendDeadband => this["trend_deadband_degC"];
        public double ModuleLabelOffsetM => this["module_label_offset_m"];

        /// <summary>Copy of config/unity_display.json v0.1, used only if the file cannot be read (the UI then shows a warning).</summary>
        public static DisplayConfig BuiltInDefault()
        {
            const string json = @"{""display_config_version"":""0.1-builtin"",""settings"":{
 ""flag_p_outlier_display"":{""value"":0.5,""unit"":""1"",""status"":""PROVISIONAL"",""purpose"":""display only""},
 ""flag_p_level_shift_display"":{""value"":0.5,""unit"":""1"",""status"":""PROVISIONAL"",""purpose"":""display only""},
 ""history_window_min"":{""value"":60,""unit"":""min"",""status"":""FROZEN"",""purpose"":""plan 4J""},
 ""forecast_window_min"":{""value"":60,""unit"":""min"",""status"":""FROZEN"",""purpose"":""plan 4K""},
 ""y_axis_min_span_degC"":{""value"":2.0,""unit"":""degC"",""status"":""PROVISIONAL"",""purpose"":""layout only""},
 ""y_axis_padding_degC"":{""value"":0.3,""unit"":""degC"",""status"":""PROVISIONAL"",""purpose"":""layout only""},
 ""trend_deadband_degC"":{""value"":0.02,""unit"":""degC"",""status"":""PROVISIONAL"",""purpose"":""display only""},
 ""module_label_offset_m"":{""value"":0.12,""unit"":""m"",""status"":""PROVISIONAL"",""purpose"":""layout only""}}}";
            return FromJson(json, "built-in default (display config v0.1)");
        }
    }
}
