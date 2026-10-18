using System.IO;
using System.Linq;
using Neram.Core;
using Newtonsoft.Json.Linq;
using NUnit.Framework;

namespace Neram.Tests
{
    [TestFixture]
    public class ForecastVisibilityTests
    {
        [Test]
        public void HiddenWhileInitialisingAndShownWhenValid()
        {
            var s = TestEnv.Session("SYN_SCN_B");
            var early = ForecastRules.Compute(s, TestEnv.FrameAt(s, 5));
            Assert.IsFalse(early.Visible);
            Assert.AreEqual(ForecastRules.MsgInitialising, early.HiddenMessage);
            var valid = ForecastRules.Compute(s, TestEnv.FrameAt(s, 25));
            Assert.IsTrue(valid.Visible);
            Assert.IsNull(valid.HiddenMessage);
            Assert.IsTrue(valid.Horizons.All(h => !double.IsNaN(h.Mean) && !double.IsNaN(h.PBelow)));
            Assert.IsTrue(valid.Horizons[2].InformationOnly, "+60 min is information only");
            Assert.IsFalse(valid.Horizons[0].InformationOnly);
        }

        [Test]
        public void HiddenWhenTwinDegradedWithMonitoringMessage()
        {
            var s = TestEnv.Session("SYN_SCN_D");
            var v = ForecastRules.Compute(s, TestEnv.FrameAt(s, 45));
            Assert.AreEqual(s.StDegraded, s.Table.GetInt(s.F.State, TestEnv.FrameAt(s, 45)));
            Assert.IsFalse(v.Visible);
            Assert.AreEqual("Twin unreliable — monitoring only", v.HiddenMessage);
        }

        [Test]
        public void HiddenInTwinDegradedStateEvenWhenValidityHasRecovered()
        {
            // SYN_SCN_D: Twin_Valid is VALID again at 57:00 but the controller stays TWIN_DEGRADED until 59:00 (recovery dwell).
            var s = TestEnv.Session("SYN_SCN_D");
            int f = TestEnv.FrameAt(s, 58);
            Assert.AreEqual(s.TvValid, s.Table.GetInt(s.F.TwinValid, f));
            Assert.AreEqual(s.StDegraded, s.Table.GetInt(s.F.State, f));
            Assert.IsFalse(ForecastRules.Compute(s, f).Visible);
        }

        [Test]
        public void ClinicianFixedSubstateHasItsOwnMessage()
        {
            var s = TestEnv.Session("SYN_ENG_05");
            var v = ForecastRules.Compute(s, TestEnv.FrameAt(s, 40));
            Assert.IsFalse(v.Visible);
            Assert.AreEqual(ForecastRules.MsgDegradedClinician, v.HiddenMessage);
        }

        [Test]
        public void LabelSaysNoInterventionWhenHeatingInOpenLoopOrStandIn()
        {
            var a0 = TestEnv.Session("SYN_SCN_A0");
            int f = TestEnv.FrameAt(a0, 40);
            Assert.IsTrue(a0.AnyHeat(f));
            Assert.AreEqual(ForecastRules.LabelNoIntervention, ForecastRules.Compute(a0, f).Label);
            var b = TestEnv.Session("SYN_SCN_B");
            int g = TestEnv.FrameAt(b, 40);
            Assert.IsTrue(b.AnyHeat(g));
            Assert.AreEqual(ForecastRules.LabelNoIntervention, ForecastRules.Compute(b, g).Label);
            StringAssert.Contains("stand-in", ForecastRules.Compute(b, g).Provenance);
        }

        [Test]
        public void LabelIsPlainForecastWhenNoHeating()
        {
            var s = TestEnv.Session("SYN_ENG_06");
            int f = TestEnv.FrameAt(s, 30);
            Assert.IsFalse(s.AnyHeat(f));
            Assert.AreEqual(ForecastRules.LabelPlain, ForecastRules.Compute(s, f).Label);
        }

        [Test]
        public void LabelSaysAssumedWarmingOnlyForTwinInTheLoop()
        {
            var lines = File.ReadAllText(Path.Combine(TestEnv.Fixtures, "valid_minimal.jsonl")).TrimEnd('\n').Split('\n').ToList();
            for (int i = 1; i < lines.Count; i++)
            {
                var fr = JObject.Parse(lines[i]);
                fr["plant"]["plant_mode"] = "TWIN_IN_LOOP";
                lines[i] = fr.ToString(Newtonsoft.Json.Formatting.None);
            }
            var r = TestEnv.ParseText(string.Join("\n", lines));
            Assert.IsTrue(r.Report.IsValid, r.Report.Summary());
            var s = new ReplaySession(r.Header, r.Table, r.Report, TestEnv.Enums(), TestEnv.Params(), TestEnv.Faults(), TestEnv.Display(), "mem");
            Assert.IsTrue(s.AnyHeat(0));
            Assert.AreEqual(ForecastRules.LabelAssumedWarming, ForecastRules.Compute(s, 0).Label);
        }
    }

    [TestFixture]
    public class SafetyAndChannelDisplayTests
    {
        [Test]
        public void ShutdownBannerShowsLatchedFaultChannelAndAwaitingReset()
        {
            var s = TestEnv.Session("SYN_SCN_C");
            var v = SafetyRules.Compute(s, TestEnv.FrameAt(s, 48));
            Assert.IsTrue(v.InShutdown);
            Assert.AreEqual(SafetyRules.ShutdownTitle, v.Title);
            Assert.AreEqual(206, v.FaultCode);
            Assert.AreEqual("OVERTEMP_SW", v.FaultName);
            Assert.AreEqual(1, v.AffectedChannels.Count);
            StringAssert.StartsWith("CH2", v.AffectedChannels[0]);
            Assert.AreEqual(ResetState.AwaitingReset, v.Reset);
            Assert.AreEqual(46 * 60, v.LatchedAtT);
        }

        [Test]
        public void ResetBlockedThenReleased()
        {
            var s = TestEnv.Session("SYN_SCN_C");
            Assert.AreEqual(ResetState.Blocked, SafetyRules.Compute(s, TestEnv.FrameAt(s, 52, 5)).Reset);
            Assert.AreEqual(ResetState.AwaitingReset, SafetyRules.Compute(s, TestEnv.FrameAt(s, 55)).Reset);
            var rel = SafetyRules.Compute(s, TestEnv.FrameAt(s, 60, 10));
            Assert.IsFalse(rel.InShutdown);
            Assert.AreEqual(ResetState.Released, rel.Reset);
            Assert.AreEqual(ResetState.None, SafetyRules.Compute(s, TestEnv.FrameAt(s, 65)).Reset, "the released notice is temporary");
        }

        [Test]
        public void HeatersAreOffInEveryShutdownFrame()
        {
            foreach (var id in new[] { "SYN_SCN_C", "SYN_ENG_03", "SYN_ENG_04" })
            {
                var s = TestEnv.Session(id);
                for (int f = 0; f < s.Table.FrameCount; f++)
                {
                    if (!s.Table.GetBool(s.F.SafetyShutdown, f)) continue;
                    for (int ch = 1; ch <= 4; ch++)
                    {
                        var cv = ChannelRules.Compute(s, f, ch);
                        Assert.AreEqual(ChannelStatus.Shutdown, cv.Status, id);
                        Assert.AreEqual(0.0, cv.Heat, id);
                    }
                }
            }
        }

        [Test]
        public void SingleChannelFaultsIsolateOnlyThatChannel()
        {
            var s = TestEnv.Session("SYN_ENG_02");
            int f = TestEnv.FrameAt(s, 40);
            var c1 = ChannelRules.Compute(s, f, 1);
            var c3 = ChannelRules.Compute(s, f, 3);
            var c4 = ChannelRules.Compute(s, f, 4);
            Assert.AreEqual(ChannelStatus.Heating, c1.Status);
            Assert.Greater(c1.Heat, 0);
            Assert.AreEqual(ChannelStatus.Fault, c3.Status);
            Assert.AreEqual(303, c3.FaultCode);
            Assert.AreEqual(0.0, c3.Heat);
            Assert.IsTrue(double.IsNaN(c3.TempB), "an open sensor reads as missing, never as a temperature");
            Assert.AreEqual(ChannelStatus.Disconnected, c4.Status);
            Assert.AreEqual(0.0, c4.Heat);
            var safety = SafetyRules.Compute(s, f);
            Assert.IsFalse(safety.InShutdown);
            Assert.AreEqual(2, safety.ChannelFaults.Count);
        }

        [Test]
        public void HardwareCutoffShowsAsCutoffBeforeShutdownOverlay()
        {
            var s = TestEnv.Session("SYN_ENG_03");
            int f = TestEnv.FrameAt(s, 45);
            Assert.IsTrue(s.Table.GetBool(s.F.Cutoff[2], f));
            var v = SafetyRules.Compute(s, f);
            Assert.IsTrue(v.InShutdown);
            Assert.IsTrue(v.AffectedChannels.Any(a => a.Contains("hardware cutoff")));
            Assert.AreEqual(307, v.FaultCode);
        }

        [Test]
        public void UnknownFaultCodeIsNeverGivenAMeaning()
        {
            var t = TestEnv.Faults();
            StringAssert.StartsWith("Unknown fault code 777", t.Describe(777));
            Assert.AreEqual("UNKNOWN_777", t.NameOf(777));
            Assert.AreEqual("No fault", t.Describe(0));
        }
    }

    [TestFixture]
    public class BannerAndThermalTests
    {
        [Test]
        public void BannerUsesEnumLabelsAndTones()
        {
            var s = TestEnv.Session("SYN_SCN_C");
            var warm = BannerRules.Compute(s, TestEnv.FrameAt(s, 30));
            Assert.AreEqual("CLINICIAN_WARMING", warm.StateName);
            Assert.AreEqual(BannerTone.Warming, warm.Tone);
            Assert.IsTrue(warm.ClinicianMode);
            var sd = BannerRules.Compute(s, TestEnv.FrameAt(s, 47));
            Assert.AreEqual(BannerTone.Critical, sd.Tone);
            Assert.IsTrue(sd.SafetyShutdown && sd.FaultLatched);
            Assert.AreEqual("Safety fault", sd.ReasonLabel);
            Assert.AreEqual(46 * 60, sd.SinceT);
        }

        [Test]
        public void ThermalBandLabelsPlaceholderThresholds()
        {
            var s = TestEnv.Session("SYN_SCN_B");
            var v = ThermalRules.Compute(s, TestEnv.FrameAt(s, 30));
            StringAssert.Contains("PLACEHOLDER", v.ThresholdNote);
            Assert.AreEqual(36.0, v.THypo);
            Assert.AreEqual(36.5, v.TTarget, "SYN replays carry their own labelled t_target placeholder");
            Assert.AreEqual(ThermalBand.BetweenHypoAndTarget, v.Band);
        }

        [Test]
        public void ThermalBandWithoutTargetDoesNotInventOne()
        {
            var r = TestEnv.ParseText(File.ReadAllText(Path.Combine(TestEnv.Fixtures, "valid_minimal.jsonl")));
            var h = r.Header;
            h.ParamsUsed = null; // use project config only: t_target is TBD without a placeholder there
            var s = new ReplaySession(h, r.Table, r.Report, TestEnv.Enums(), TestEnv.Params(), TestEnv.Faults(), TestEnv.Display(), "mem");
            var v = ThermalRules.Compute(s, 0);
            Assert.IsTrue(double.IsNaN(v.TTarget));
            StringAssert.Contains("t_target not established", v.ThresholdNote);
            Assert.AreNotEqual(ThermalBand.AtOrAboveTarget, v.Band);
        }

        [Test]
        public void HeaderSnapshotDisagreementsAreRecorded()
        {
            var s = TestEnv.Session("SYN_SCN_B");
            Assert.IsTrue(s.Params.Notes.Any(n => n.StartsWith("t_target_degC")), string.Join("\n", s.Params.Notes));
            Assert.AreEqual("replay header params_used (SYN_SCN_B)", s.Params.GetOrNull("t_target_degC").Origin);
        }

        [Test]
        public void ProvenanceIsReportedForEveryGroup()
        {
            var s = TestEnv.Session("SYN_SCN_A0");
            var p = ProvenanceRules.Compute(s, 100);
            CollectionAssert.AreEqual(new[] { "SIMULATED", "SIMULATED", "SIMULATED", "SIMULATED", "ASSUMED" }, p.Select(x => x.Tag).ToArray());
            StringAssert.Contains("Open loop", p[4].Meaning);
        }
    }
}
