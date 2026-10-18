using System.Collections.Generic;
using System.IO;
using System.Linq;
using Neram.Core;
using Newtonsoft.Json.Linq;
using NUnit.Framework;

namespace Neram.Tests
{
    [TestFixture]
    public class ConfigTests
    {
        [Test]
        public void EnumsJsonMatchesPlanNamesAndBuiltInDefault()
        {
            var cfg = TestEnv.Enums();
            var def = EnumRegistry.BuiltInDefault();
            foreach (var name in EnumRegistry.RequiredEnums)
            {
                var a = cfg.Get(name);
                var b = def.Get(name);
                CollectionAssert.AreEquivalent(b.ByName.Keys.ToList(), a.ByName.Keys.ToList(), name + " names");
                foreach (var kv in b.ByName) Assert.AreEqual(kv.Value.Value, a.ByName[kv.Key].Value, name + "." + kv.Key);
            }
            CollectionAssert.AreEqual(new[] { "NORMAL", "PREDICTIVE_WARMING", "ACTIVE_WARMING", "TARGET_MAINTENANCE", "CLINICIAN_WARMING", "TWIN_DEGRADED", "SAFETY_SHUTDOWN" },
                Enumerable.Range(0, 7).Select(v => cfg.NameOf("ControllerState", v)).ToArray(), "frozen ControllerState order (plan 0.4)");
        }

        [Test]
        public void StringEnumsMatchEnumsJson()
        {
            var o = JObject.Parse(File.ReadAllText(TestEnv.ConfigPath("enums.json")));
            CollectionAssert.AreEqual(StringEnums.SourceTags, o["enums"]["SourceTag"]["values"].Select(v => (string)v["value"]).ToArray());
            CollectionAssert.AreEqual(StringEnums.PlantModes, o["enums"]["PlantMode"]["values"].Select(v => (string)v["value"]).ToArray());
        }

        [Test]
        public void ParamsUseOnlyAllowedStatusesAndNoTbdHasAValue()
        {
            var p = TestEnv.Params();
            Assert.IsTrue(p.Entries.Count >= 40);
            foreach (var e in p.Entries.Values)
            {
                CollectionAssert.Contains(ParamsRegistry.AllowedStatuses, e.Status, e.Name);
                if (e.Status == "TBD") Assert.IsFalse(e.HasValue, e.Name + " is TBD but has a value");
                Assert.IsFalse(string.IsNullOrEmpty(e.Owner), e.Name + " has no owner");
                Assert.IsFalse(string.IsNullOrEmpty(e.Source), e.Name + " has no source");
            }
            Assert.AreEqual("FROZEN", p.GetOrNull("ts_twin_s").Status);
            Assert.AreEqual(60.0, p.GetOrNull("ts_twin_s").EffectiveScalar);
            var hypo = p.GetOrNull("t_hypo_degC");
            Assert.AreEqual("TBD", hypo.Status);
            Assert.IsTrue(hypo.IsPlaceholderInUse);
            StringAssert.Contains("PLACEHOLDER", hypo.DisplayValue());
            Assert.IsTrue(double.IsNaN(p.GetOrNull("t_target_degC").EffectiveScalar), "the project config does not invent a target");
            Assert.IsTrue(double.IsNaN(p.GetOrNull("t_surface_limit_degC").EffectiveScalar), "no surface limit is invented");
        }

        [Test]
        public void ParamsRejectATbdEntryWithAValue()
        {
            const string bad = "{\"params_version\":\"x\",\"params\":{\"a\":{\"value\":1,\"status\":\"TBD\",\"unit\":\"s\",\"source\":\"s\",\"owner\":\"o\"}}}";
            Assert.Throws<System.FormatException>(() => ParamsRegistry.FromJson(bad, "test"));
            const string badStatus = "{\"params_version\":\"x\",\"params\":{\"a\":{\"value\":1,\"status\":\"VALIDATED\",\"unit\":\"s\",\"source\":\"s\",\"owner\":\"o\"}}}";
            Assert.Throws<System.FormatException>(() => ParamsRegistry.FromJson(badStatus, "test"));
        }

        [Test]
        public void DisplayConfigIsDisplayOnlyAndComplete()
        {
            var d = TestEnv.Display();
            Assert.AreEqual(3600.0, d.HistoryWindowS);
            Assert.AreEqual(3600.0, d.ForecastWindowS);
            foreach (var s in d.Settings.Values) CollectionAssert.Contains(ParamsRegistry.AllowedStatuses, s.Status, s.Name);
        }

        [Test]
        public void PlaceholderFaultTableFollowsThePlanPattern()
        {
            var t = TestEnv.Faults();
            Assert.IsTrue(t.IsPlaceholder);
            Assert.AreEqual(9 + 4 * 11, t.Count);
            for (int ch = 1; ch <= 4; ch++)
            {
                Assert.AreEqual("OVERTEMP_SW", t.NameOf(100 * ch + 6));
                Assert.AreEqual("STUCK_ON", t.NameOf(100 * ch + 11));
                Assert.AreEqual(ch, t.Find(100 * ch + 8).Channel);
            }
            StringAssert.Contains("[placeholder text]", t.Describe(206));
        }

        [Test]
        public void CsvParserHandlesQuotesAndNewlines()
        {
            var rows = Csv.Parse("a,b\n\"x, y\",\"he said \"\"hi\"\"\"\r\n\"multi\nline\",z\n");
            Assert.AreEqual(3, rows.Count);
            Assert.AreEqual("x, y", rows[1][0]);
            Assert.AreEqual("he said \"hi\"", rows[1][1]);
            Assert.AreEqual("multi\nline", rows[2][0]);
        }
    }

    [TestFixture]
    public class SchemaConsistencyTests
    {
        [Test]
        public void GeneratedFieldTableMatchesReplayFieldsJson()
        {
            var path = Path.Combine(TestEnv.UnityAssets, "..", "schema", "replay_fields.json");
            if (!File.Exists(path)) Assert.Ignore("unity/schema not present next to Assets");
            var doc = JObject.Parse(File.ReadAllText(path));
            var names = ((JArray)doc["fields"]).Select(f => (string)f["group"] + "." + (string)f["name"]).ToArray();
            CollectionAssert.AreEqual(names, ReplayFields.All.Select(f => f.Key).ToArray(),
                "ReplayFields.g.cs is stale: run tools/gen_replay_schema.py");
        }

        [Test]
        public void EveryReplaySignalInTheInterfaceSpecExistsInTheSchema()
        {
            var spec = TestEnv.ConfigPath("interface_spec.csv");
            var rows = Csv.Parse(File.ReadAllText(spec));
            var header = rows[0];
            int iSig = header.IndexOf("signal"), iDst = header.IndexOf("destination"), iGrp = header.IndexOf("replay_group");
            var missing = new List<string>();
            foreach (var r in rows.Skip(1))
            {
                if (r.Count <= iGrp || !r[iDst].Contains("Replay")) continue;
                var g = r[iGrp];
                if (g == "" || g.StartsWith("header")) continue;
                if (g == "src") continue;
                if (!ReplayFields.TryGet(g, r[iSig], out _)) missing.Add(g + "." + r[iSig]);
            }
            Assert.IsEmpty(missing, "interface_spec.csv replay signals missing from replay_fields.json: " + string.Join(", ", missing));
        }

        [Test]
        public void ForecastFieldListCoversAllHorizonFields()
        {
            Assert.AreEqual(18, ReplayFields.ForecastFieldNames.Length);
            foreach (var n in ReplayFields.ForecastFieldNames) Assert.IsTrue(ReplayFields.TryGet("twin", n, out _), n);
        }

        [Test]
        public void NoFieldIsNamedCoreTemperature()
        {
            foreach (var f in ReplayFields.All)
            {
                StringAssert.DoesNotContain("core", f.Name.ToLowerInvariant());
                StringAssert.DoesNotContain("core temperature", (f.Label ?? "").ToLowerInvariant());
            }
        }
    }

    [TestFixture]
    public class ScenarioCatalogTests
    {
        [Test]
        public void CatalogMarksMissingScenariosAsAwaitingData()
        {
            var catalog = ScenarioCatalog.ParseCatalog(File.ReadAllText(TestEnv.ConfigPath("unity_scenarios.json")));
            var list = ScenarioCatalog.Discover(TestEnv.ReplayDir, catalog);
            var a = list.First(l => l.Id == "SCN_A");
            Assert.AreEqual(ScenarioAvailability.AwaitingData, a.Availability);
            Assert.IsNull(a.FilePath);
            var b = list.First(l => l.Id == "SYN_SCN_B");
            Assert.AreEqual(ScenarioAvailability.Available, b.Availability);
            Assert.IsTrue(b.IsPlaceholder);
            Assert.IsTrue(list.Count(l => l.Availability == ScenarioAvailability.Available) >= 10);
        }

        [Test]
        public void AnInvalidHeaderIsListedButNotLoadable()
        {
            var dir = Path.Combine(Path.GetTempPath(), "neram_catalog_test_" + System.Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(dir);
            try
            {
                File.Copy(Path.Combine(TestEnv.Fixtures, "E052_cohort_holdout.jsonl"), Path.Combine(dir, "bad.jsonl"));
                File.Copy(Path.Combine(TestEnv.Fixtures, "valid_minimal.jsonl"), Path.Combine(dir, "good.jsonl"));
                File.WriteAllText(Path.Combine(dir, "notes.txt"), "ignored");
                var list = ScenarioCatalog.Discover(dir, null);
                Assert.AreEqual(2, list.Count);
                Assert.AreEqual(1, list.Count(l => l.Availability == ScenarioAvailability.HeaderInvalid));
                Assert.AreEqual(1, list.Count(l => l.Availability == ScenarioAvailability.Available));
            }
            finally { Directory.Delete(dir, true); }
        }
    }
}
