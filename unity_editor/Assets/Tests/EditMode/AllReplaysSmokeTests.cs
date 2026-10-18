using System;
using System.IO;
using System.Linq;
using Neram.Core;
using NUnit.Framework;

namespace Neram.Tests
{
    /// <summary>
    /// Every shipped replay: validates, carries an allowed cohort (holdout guard), and every display rule evaluates on
    /// every frame without exceptions. Also checks frame-level invariants the viewer relies on.
    /// </summary>
    [TestFixture]
    public class AllReplaysSmokeTests
    {
        private static string[] ReplayFiles() =>
            Directory.GetFiles(TestEnv.ReplayDir).Where(ScenarioCatalog.IsReplayFile).OrderBy(p => p, StringComparer.Ordinal).ToArray();

        [Test]
        public void ThereAreReplaysToTest()
        {
            Assert.That(ReplayFiles().Length, Is.GreaterThanOrEqualTo(10));
        }

        [Test]
        public void EveryReplayIsValidAndNeverFromTheHoldout()
        {
            foreach (var path in ReplayFiles())
            {
                var r = ReplayValidator.ParseFile(path, TestEnv.Options());
                Assert.IsTrue(r.Report.IsValid, Path.GetFileName(path) + ": " + r.Report.Summary());
                Assert.That(r.Header.Cohort, Is.EqualTo("SYNTHETIC").Or.EqualTo("DEVELOPMENT"), Path.GetFileName(path));
                if (r.Header.IsSynthetic) StringAssert.StartsWith("SYN_", r.Header.ScenarioId, "synthetic scenario ids are prefixed SYN_");
            }
        }

        [Test]
        public void EveryDisplayRuleEvaluatesOnEveryFrame()
        {
            foreach (var path in ReplayFiles())
            {
                var id = Path.GetFileName(path).Replace(".jsonl.gz", "").Replace(".jsonl", "");
                var s = TestEnv.Session(id);
                int n = s.Table.FrameCount;
                for (int f = 0; f < n; f++)
                {
                    var fc = ForecastRules.Compute(s, f);
                    var tv = s.Table.GetInt(s.F.TwinValid, f);
                    var st = s.Table.GetInt(s.F.State, f);
                    if (fc.Visible)
                    {
                        Assert.AreEqual(s.TvValid, tv, id + " frame " + f + ": forecast visible while Twin_Valid != VALID");
                        Assert.AreNotEqual(s.StDegraded, st, id + " frame " + f + ": forecast visible in TWIN_DEGRADED");
                        Assert.IsFalse(string.IsNullOrEmpty(fc.Label));
                    }
                    else Assert.IsFalse(string.IsNullOrEmpty(fc.HiddenMessage), id + " frame " + f + ": hidden forecast needs a reason");

                    var safety = SafetyRules.Compute(s, f);
                    var banner = BannerRules.Compute(s, f);
                    Assert.IsNotNull(banner.StateName, id + " frame " + f);
                    for (int ch = 1; ch <= 4; ch++)
                    {
                        var cv = ChannelRules.Compute(s, f, ch);
                        if (safety.InShutdown) Assert.AreEqual(ChannelStatus.Shutdown, cv.Status, id + " frame " + f + " CH" + ch);
                        Assert.IsFalse(string.IsNullOrEmpty(cv.StatusText));
                    }
                    ThermalRules.Compute(s, f);
                    Assert.IsNotEmpty(ProvenanceRules.Compute(s, f));
                }
            }
        }

        [Test]
        public void ReplayTextNeverCallsTheSignalCoreTemperature()
        {
            foreach (var path in ReplayFiles())
            {
                using (var rd = ReplayFileReader.OpenText(path))
                {
                    // The only allowed mention is the explicit negation "not core temperature" in the disclaimer.
                    var header = (rd.ReadLine() ?? "").ToLowerInvariant().Replace("not core temperature", "");
                    StringAssert.DoesNotContain("core temperature", header, Path.GetFileName(path));
                }
            }
        }
    }
}
