using System;
using System.Collections.Generic;
using Newtonsoft.Json.Linq;

namespace Neram.Core
{
    /// <summary>Optional descriptive block (PROPOSED header field "scenario_info").</summary>
    public sealed class ScenarioInfo
    {
        public string Title;
        public string Purpose;
        public string DataSource;
        public string LoopDescription;
        public readonly List<string> Limitations = new List<string>();
    }

    /// <summary>Line 1 of a replay file (plan section 4G).</summary>
    public sealed class ReplayHeader
    {
        public string SchemaVersion;
        public string ScenarioId;
        public string CreatedUtc;
        public string ParamsVersion;
        public string SpecVersion;
        public readonly Dictionary<string, string> Inputs = new Dictionary<string, string>(StringComparer.Ordinal);
        public string Disclaimer;
        /// <summary>PROPOSED, required by the holdout guard: SYNTHETIC or DEVELOPMENT.</summary>
        public string Cohort;
        public JObject StaticContext;
        /// <summary>PROPOSED: true for development scaffolding (not produced by the NERAM twin/controller).</summary>
        public bool Placeholder;
        public string Generator;
        public ScenarioInfo Info;
        public JObject ParamsUsed;
        public JObject Raw;

        public bool IsSynthetic => Cohort == "SYNTHETIC";
        public string Title => Info != null && !string.IsNullOrEmpty(Info.Title) ? Info.Title : ScenarioId;

        private static readonly string[] Required =
            { "type", "schema_version", "scenario_id", "created_utc", "params_version", "spec_version", "inputs", "disclaimer", "cohort" };
        private static readonly string[] OptionalFields =
            { "static_context", "placeholder", "generator", "scenario_info", "params_used" };
        public static readonly string[] ProposedFields = { "cohort", "placeholder", "generator", "scenario_info", "params_used" };

        /// <summary>Parse and validate a header object. Returns null only when the object cannot serve as a header at all.</summary>
        public static ReplayHeader Parse(JObject o, int line, ValidationReport report)
        {
            if (o == null || (string)o["type"] != "header")
            {
                report.Error("E001", line, "type", "first line must be a header object (\"type\": \"header\")");
                return null;
            }
            var h = new ReplayHeader { Raw = o };
            foreach (var name in Required)
            {
                var tok = o[name];
                if (tok == null)
                {
                    if (name == "cohort")
                        report.Error("E053", line, "cohort", "header.cohort is missing; it must be SYNTHETIC or DEVELOPMENT (holdout guard)");
                    else
                        report.Error("E002", line, name, "required header field missing");
                    continue;
                }
                var expectObject = name == "inputs";
                if (expectObject ? tok.Type != JTokenType.Object : tok.Type != JTokenType.String)
                    report.Error("E002", line, name, "header field has the wrong JSON type (expected " + (expectObject ? "object" : "string") + ")");
            }
            foreach (var p in o.Properties())
            {
                if (Array.IndexOf(Required, p.Name) < 0 && Array.IndexOf(OptionalFields, p.Name) < 0)
                    report.Error("E003", line, p.Name, "unknown header field");
            }

            h.SchemaVersion = Str(o, "schema_version");
            h.ScenarioId = Str(o, "scenario_id");
            h.CreatedUtc = Str(o, "created_utc");
            h.ParamsVersion = Str(o, "params_version");
            h.SpecVersion = Str(o, "spec_version");
            h.Disclaimer = Str(o, "disclaimer");
            h.Cohort = Str(o, "cohort");
            h.Generator = Str(o, "generator");

            if (h.SchemaVersion != null && Array.IndexOf(ReplayFields.SupportedSchemaVersions, h.SchemaVersion) < 0)
                report.Error("E071", line, "schema_version", "unsupported schema_version '" + h.SchemaVersion + "' (supported: " + string.Join(", ", ReplayFields.SupportedSchemaVersions) + ")");
            if (h.ScenarioId != null && h.ScenarioId.Length == 0)
                report.Error("E002", line, "scenario_id", "scenario_id is empty");
            if (h.Disclaimer != null && h.Disclaimer.Trim().Length == 0)
                report.Error("E002", line, "disclaimer", "disclaimer is empty");
            if (h.Cohort != null && Array.IndexOf(ReplayFields.AllowedCohorts, h.Cohort) < 0)
                report.Error("E052", line, "cohort", "cohort '" + h.Cohort + "' is not allowed; only SYNTHETIC or DEVELOPMENT may be displayed (the final holdout never enters Unity)");

            if (o["inputs"] is JObject inputs)
            {
                foreach (var p in inputs.Properties())
                {
                    if (p.Value.Type != JTokenType.String)
                        report.Error("E002", line, "inputs." + p.Name, "input hash must be a string");
                    else h.Inputs[p.Name] = (string)p.Value;
                }
            }

            var sc = o["static_context"];
            if (sc != null && sc.Type != JTokenType.Null && sc.Type != JTokenType.Object)
                report.Error("E002", line, "static_context", "static_context must be an object or null");
            h.StaticContext = sc as JObject;

            var ph = o["placeholder"];
            if (ph != null)
            {
                if (ph.Type != JTokenType.Boolean) report.Error("E002", line, "placeholder", "placeholder must be true/false");
                else h.Placeholder = (bool)ph;
            }
            if (o["generator"] != null && o["generator"].Type != JTokenType.String)
                report.Error("E002", line, "generator", "generator must be a string");

            var si = o["scenario_info"];
            if (si != null)
            {
                if (si.Type != JTokenType.Object) report.Error("E002", line, "scenario_info", "scenario_info must be an object");
                else h.Info = ParseInfo((JObject)si, line, report);
            }
            var pu = o["params_used"];
            if (pu != null)
            {
                if (pu.Type != JTokenType.Object) report.Error("E002", line, "params_used", "params_used must be an object");
                else h.ParamsUsed = (JObject)pu;
            }

            var proposed = new List<string>();
            foreach (var f in ProposedFields) if (o[f] != null) proposed.Add(f);
            if (proposed.Count > 0)
                report.Info("I201", line, null, "proposed header fields present (not yet in interface spec v0.1): " + string.Join(", ", proposed));
            if (h.Placeholder)
                report.Info("I202", line, "placeholder", "placeholder file: development scaffolding, not an output of the NERAM twin or controller");
            return h;
        }

        private static ScenarioInfo ParseInfo(JObject o, int line, ValidationReport report)
        {
            var info = new ScenarioInfo
            {
                Title = Str(o, "title"),
                Purpose = Str(o, "purpose"),
                DataSource = Str(o, "data_source"),
                LoopDescription = Str(o, "loop_description"),
            };
            if (o["limitations"] is JArray lims)
            {
                foreach (var l in lims)
                    if (l.Type == JTokenType.String) info.Limitations.Add((string)l);
                    else report.Error("E002", line, "scenario_info.limitations", "limitations must be strings");
            }
            return info;
        }

        private static string Str(JObject o, string name)
        {
            var t = o[name];
            return t != null && t.Type == JTokenType.String ? (string)t : null;
        }
    }
}
