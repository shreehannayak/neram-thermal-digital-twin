using System;
using System.Collections.Generic;
using System.IO;
using Newtonsoft.Json.Linq;

namespace Neram.Core
{
    public sealed class CatalogEntry
    {
        public string Id;
        public string Title;
        public string Purpose;
        public string ExpectedDataSource;
        public string ExpectedCohort;
        public readonly List<string> Limitations = new List<string>();
        public string Producer;
        public int Order;
    }

    public enum ScenarioAvailability { Available, AwaitingData, HeaderInvalid }

    public sealed class ScenarioListing
    {
        public string Id;
        public CatalogEntry Catalog;
        public string FilePath;
        public ReplayHeader Header;
        public ValidationReport HeaderReport;
        public ScenarioAvailability Availability;

        public string Title => Header?.Info?.Title ?? Catalog?.Title ?? Id;
        public bool IsPlaceholder => Header != null && Header.Placeholder;
    }

    /// <summary>
    /// Scenario list = expected scenarios (config/unity_scenarios.json) merged with replay files found on disk.
    /// A catalogued scenario without a file is shown as "awaiting data" (for example SCN_A until Sai's
    /// build_replay.py produces it). Only headers are read here; full validation happens on load.
    /// </summary>
    public static class ScenarioCatalog
    {
        public static List<CatalogEntry> ParseCatalog(string json)
        {
            var root = JObject.Parse(json);
            var list = new List<CatalogEntry>();
            var arr = root["scenarios"] as JArray ?? throw new FormatException("unity_scenarios.json: missing 'scenarios'");
            int order = 0;
            foreach (var t in arr)
            {
                var e = new CatalogEntry
                {
                    Id = (string)t["id"],
                    Title = (string)t["title"],
                    Purpose = (string)t["purpose"],
                    ExpectedDataSource = (string)t["expected_data_source"],
                    ExpectedCohort = (string)t["expected_cohort"],
                    Producer = (string)t["producer"],
                    Order = order++,
                };
                if (string.IsNullOrEmpty(e.Id)) throw new FormatException("unity_scenarios.json: scenario without id");
                if (t["limitations"] is JArray lims) foreach (var l in lims) e.Limitations.Add((string)l);
                list.Add(e);
            }
            return list;
        }

        public static bool IsReplayFile(string path) =>
            path.EndsWith(".jsonl", StringComparison.OrdinalIgnoreCase) || path.EndsWith(".jsonl.gz", StringComparison.OrdinalIgnoreCase);

        public static List<ScenarioListing> Discover(string replayDir, List<CatalogEntry> catalog)
        {
            var result = new List<ScenarioListing>();
            var byId = new Dictionary<string, ScenarioListing>(StringComparer.Ordinal);
            if (catalog != null)
                foreach (var c in catalog)
                {
                    var l = new ScenarioListing { Id = c.Id, Catalog = c, Availability = ScenarioAvailability.AwaitingData };
                    result.Add(l);
                    byId[c.Id] = l;
                }
            if (Directory.Exists(replayDir))
            {
                var files = Directory.GetFiles(replayDir);
                Array.Sort(files, StringComparer.Ordinal);
                foreach (var path in files)
                {
                    if (!IsReplayFile(path)) continue;
                    var rep = new ValidationReport();
                    ReplayHeader h = null;
                    try { h = ReplayFileReader.ReadHeader(path, rep); }
                    catch (IOException ex) { rep.Error("E090", 0, null, ex.Message); }
                    var id = h?.ScenarioId ?? Path.GetFileName(path);
                    var avail = h != null && rep.IsValid ? ScenarioAvailability.Available : ScenarioAvailability.HeaderInvalid;
                    if (byId.TryGetValue(id, out var existing) && existing.FilePath == null)
                    {
                        existing.FilePath = path; existing.Header = h; existing.HeaderReport = rep; existing.Availability = avail;
                    }
                    else
                    {
                        var l = new ScenarioListing { Id = id, FilePath = path, Header = h, HeaderReport = rep, Availability = avail };
                        result.Add(l);
                        if (!byId.ContainsKey(id)) byId[id] = l;
                    }
                }
            }
            return result;
        }
    }
}
