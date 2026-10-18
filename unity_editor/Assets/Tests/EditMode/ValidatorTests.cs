using System.Collections.Generic;
using System.IO;
using System.Linq;
using Neram.Core;
using Newtonsoft.Json.Linq;
using NUnit.Framework;

namespace Neram.Tests
{
    /// <summary>Shared fixture corpus: the same manifest is checked by tests/test_validate_replay.py (Python).</summary>
    [TestFixture]
    public class FixtureCorpusTests
    {
        [Test]
        public void EveryFixtureProducesExactlyTheExpectedErrors()
        {
            var manifest = JObject.Parse(File.ReadAllText(Path.Combine(TestEnv.Fixtures, "fixtures_manifest.json")));
            var failures = new List<string>();
            int n = 0;
            foreach (var m in (JArray)manifest["fixtures"])
            {
                n++;
                var file = (string)m["file"];
                var r = ReplayValidator.ParseFile(Path.Combine(TestEnv.Fixtures, file), TestEnv.Options());
                bool expectValid = (bool)m["valid"];
                var expectedErrors = ((JArray)m["errors"]).Select(x => (string)x).OrderBy(x => x).ToList();
                var gotErrors = r.Report.Codes.Where(c => c.StartsWith("E")).OrderBy(x => x).ToList();
                if (r.Report.IsValid != expectValid) failures.Add(file + ": valid=" + r.Report.IsValid + " expected " + expectValid + " (" + r.Report.Summary() + ")");
                if (!gotErrors.SequenceEqual(expectedErrors)) failures.Add(file + ": errors [" + string.Join(",", gotErrors) + "] expected [" + string.Join(",", expectedErrors) + "]");
                foreach (var w in (JArray)m["warnings"])
                    if (!r.Report.Has((string)w)) failures.Add(file + ": missing warning " + (string)w);
                if (!r.Report.IsValid && r.Table != null) failures.Add(file + ": invalid replay must not produce a table");
                if (r.Report.IsValid && r.Table == null) failures.Add(file + ": valid replay must produce a table");
            }
            Assert.IsTrue(n >= 50, "fixture corpus unexpectedly small: " + n);
            Assert.IsEmpty(failures, string.Join("\n", failures));
        }
    }

    [TestFixture]
    public class ParserTests
    {
        private static string Fixture(string name) => File.ReadAllText(Path.Combine(TestEnv.Fixtures, name));

        [Test]
        public void NullValuesAreStoredAsMissingNeverZero()
        {
            var r = TestEnv.ParseText(Fixture("valid_initialising.jsonl"));
            Assert.IsTrue(r.Report.IsValid, r.Report.Summary());
            var f = ReplayFields.Get("twin", "T_pred_20");
            Assert.IsTrue(r.Table.IsNull(f, 0), "INITIALISING frames carry null forecasts");
            Assert.IsTrue(double.IsNaN(r.Table.Get(f, 0)));
            Assert.AreEqual(Fmt.Missing, Fmt.Value(r.Table.Get(f, 0), f), "missing values display as an em dash");
        }

        [Test]
        public void MissingObservationIsNullAndFlagged()
        {
            var lines = Fixture("valid_minimal.jsonl").TrimEnd('\n').Split('\n').ToList();
            var fr = JObject.Parse(lines[2]);
            fr["obs"]["T_obs"] = null;
            fr["obs"]["obs_missing"] = true;
            lines[2] = fr.ToString(Newtonsoft.Json.Formatting.None);
            var r = TestEnv.ParseText(string.Join("\n", lines));
            Assert.IsTrue(r.Report.IsValid, r.Report.Summary());
            Assert.IsTrue(r.Table.IsNull(ReplayFields.Get("obs", "T_obs"), 1));
            Assert.IsTrue(r.Table.GetBool(ReplayFields.Get("obs", "obs_missing"), 1));
        }

        [Test]
        public void OptionalFieldsAbsentStayMissing()
        {
            var lines = Fixture("valid_minimal.jsonl").TrimEnd('\n').Split('\n').ToList();
            for (int i = 1; i < lines.Count; i++)
            {
                var fr = JObject.Parse(lines[i]);
                ((JObject)fr["ctrl"]).Remove("Clinician_Start");
                ((JObject)fr["ctrl"]).Remove("Data_Stale_HW");
                lines[i] = fr.ToString(Newtonsoft.Json.Formatting.None);
            }
            var r = TestEnv.ParseText(string.Join("\n", lines));
            Assert.IsTrue(r.Report.IsValid, r.Report.Summary());
            Assert.IsTrue(r.Table.IsNull(ReplayFields.Get("ctrl", "Clinician_Start"), 0));
            Assert.IsTrue(r.Table.IsNull(ReplayFields.Get("ctrl", "Data_Stale_HW"), 0));
        }

        [Test]
        public void RequiredFieldAbsentIsRejected()
        {
            var lines = Fixture("valid_minimal.jsonl").TrimEnd('\n').Split('\n').ToList();
            var fr = JObject.Parse(lines[1]);
            ((JObject)fr["ctrl"]).Remove("Heat_3");
            lines[1] = fr.ToString(Newtonsoft.Json.Formatting.None);
            var r = TestEnv.ParseText(string.Join("\n", lines));
            Assert.IsFalse(r.Report.IsValid);
            Assert.IsTrue(r.Report.Has("E010"));
            Assert.IsNull(r.Table);
        }

        [Test]
        public void EnumsAndSourceTagsParse()
        {
            var r = TestEnv.ParseText(Fixture("valid_shutdown.jsonl"));
            Assert.IsTrue(r.Report.IsValid, r.Report.Summary());
            var enums = TestEnv.Enums();
            int st = r.Table.GetInt(ReplayFields.Get("ctrl", "Controller_State"), 0);
            Assert.AreEqual("SAFETY_SHUTDOWN", enums.NameOf("ControllerState", st));
            Assert.AreEqual("SIMULATED", r.Table.GetString(ReplayFields.Get("src", "ctrl"), 0));
            Assert.AreEqual("ASSUMED", r.Table.GetString(ReplayFields.Get("src", "plant"), 0));
            Assert.AreEqual("STANDIN", r.Table.GetString(ReplayFields.Get("plant", "plant_mode"), 0));
        }

        [Test]
        public void UnknownEnumValueIsRejectedNotDisplayed()
        {
            var r = TestEnv.ParseText(Fixture("E014_unknown_state.jsonl"));
            Assert.IsFalse(r.Report.IsValid);
            Assert.IsNull(r.Table);
        }

        [Test]
        public void HeaderFieldsAreRead()
        {
            var r = TestEnv.ParseText(Fixture("valid_minimal.jsonl"));
            Assert.AreEqual("SYNTHETIC", r.Header.Cohort);
            Assert.IsTrue(r.Header.Placeholder);
            Assert.AreEqual("1.0", r.Header.SchemaVersion);
            Assert.IsNotNull(r.Header.Info);
            Assert.IsTrue(r.Header.Info.Limitations.Count > 0);
            Assert.IsNotNull(r.Header.ParamsUsed);
            Assert.IsTrue(r.Report.Has("I201"), "proposed header fields are reported as info");
        }

        [Test]
        public void GzipAndPlainFilesGiveIdenticalTables()
        {
            var a = ReplayValidator.ParseFile(Path.Combine(TestEnv.Fixtures, "valid_minimal.jsonl"), TestEnv.Options());
            var b = ReplayValidator.ParseFile(Path.Combine(TestEnv.Fixtures, "valid_minimal_gz.jsonl.gz"), TestEnv.Options());
            Assert.AreEqual(a.Table.FrameCount, b.Table.FrameCount);
            foreach (var f in ReplayFields.All)
                for (int i = 0; i < a.Table.FrameCount; i++)
                    Assert.AreEqual(a.Table.Get(f, i), b.Table.Get(f, i), f.Key);
        }

        [Test]
        public void TimestampsMustIncreaseStrictly()
        {
            var r = TestEnv.ParseText(Fixture("E020_time_not_increasing.jsonl"));
            Assert.IsTrue(r.Report.Has("E020"));
            Assert.IsNull(r.Table);
        }

        [Test]
        public void ErrorFloodIsCappedAndStillRejected()
        {
            var lines = Fixture("valid_minimal.jsonl").TrimEnd('\n').Split('\n').ToList();
            var bad = JObject.Parse(lines[1]);
            bad["ctrl"]["Heat_1"] = 500.0;
            var sb = new System.Text.StringBuilder(lines[0]).Append('\n');
            for (int i = 0; i < 400; i++)
            {
                bad["meta"]["t_s"] = 10000 + i;
                sb.Append(bad.ToString(Newtonsoft.Json.Formatting.None)).Append('\n');
            }
            var r = TestEnv.ParseText(sb.ToString());
            Assert.IsFalse(r.Report.IsValid);
            Assert.IsTrue(r.Report.Has("E099"));
            Assert.IsTrue(r.Report.Issues.Count <= ValidationReport.MaxStoredPerCode * 3 + 2, "issue storage is bounded");
        }

        [Test]
        public void HoldoutCohortIsRejectedEvenIfOtherwiseValid()
        {
            var lines = Fixture("valid_minimal.jsonl").TrimEnd('\n').Split('\n').ToList();
            var h = JObject.Parse(lines[0]);
            foreach (var cohort in new[] { "HOLDOUT", "FINAL", "final_holdout", "" })
            {
                h["cohort"] = cohort;
                lines[0] = h.ToString(Newtonsoft.Json.Formatting.None);
                var r = TestEnv.ParseText(string.Join("\n", lines));
                Assert.IsTrue(r.Report.Has("E052"), "cohort '" + cohort + "' must be rejected");
                Assert.IsNull(r.Table);
            }
        }

        [Test]
        public void CancellationStopsParsingWithoutATable()
        {
            var cts = new System.Threading.CancellationTokenSource();
            cts.Cancel();
            var opt = TestEnv.Options();
            opt.Cancel = cts.Token;
            var r = ReplayValidator.ParseString(Fixture("valid_minimal.jsonl"), opt);
            Assert.IsTrue(r.Cancelled);
            Assert.IsNull(r.Table);
        }

        [Test]
        public void MinuteBucketsFollowTwinPeriod()
        {
            var s = TestEnv.Session("SYN_ENG_04");
            var t = s.Table;
            Assert.AreEqual(t.FrameCount / 60, t.MinuteStartFrames.Length);
            for (int m = 0; m < t.MinuteStartFrames.Length; m++)
                Assert.AreEqual(m * 60.0, t.T[t.MinuteStartFrames[m]]);
            Assert.AreEqual(5, t.FrameMinute[t.FrameAtTime(5 * 60 + 59)]);
        }
    }
}
