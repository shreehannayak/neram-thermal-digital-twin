using System;
using Neram.Core;
using NUnit.Framework;

namespace Neram.Tests
{
    [TestFixture]
    public class PipelineTests
    {
        [Test]
        public void WarmingChannelStageReportsReplayedCommandsExactly()
        {
            var s = TestEnv.Session("SYN_SCN_B");
            for (int frame = 0; frame < s.Table.FrameCount; frame += 97)
            {
                var v = PipelineRules.Compute(s, frame);
                for (int i = 0; i < 4; i++)
                {
                    var replay = s.Table.Get(s.F.Heat[i], frame);
                    Assert.AreEqual(replay, v.Heat[i], 0.0, "CH" + (i + 1) + " at frame " + frame);
                }
            }
        }

        [Test]
        public void NoCommandIsInventedWhileTheReplayCommandIsZero()
        {
            // SYN_SCN_B: the patient signal falls during the first 20 min while the controller is still NORMAL and Heat_i = 0.
            var s = TestEnv.Session("SYN_SCN_B");
            var f = TestEnv.FrameAt(s, 19, 30);
            var v = PipelineRules.Compute(s, f);
            for (int i = 0; i < 4; i++) Assert.AreEqual(0.0, v.Heat[i]);
            StringAssert.Contains("CH1 0%", v.Stages[3].Value);
        }

        [Test]
        public void ControllerTransitionThenRisingCommandsBecomeTheActiveStages()
        {
            var s = TestEnv.Session("SYN_SCN_B");
            // 21:00 = controller NORMAL -> PREDICTIVE_WARMING and the first non-zero command (same frame)
            var atStart = PipelineRules.Compute(s, TestEnv.FrameAt(s, 21, 0));
            Assert.IsTrue(atStart.ActiveStage == 2 || atStart.ActiveStage == 3, "active stage " + atStart.ActiveStage);
            Assert.IsFalse(double.IsNaN(atStart.Stages[2].LastChange));
            Assert.Greater(atStart.Heat[0], 0);
            // stage 5 follows stage 4
            Assert.AreEqual(atStart.Stages[3].LastChange, atStart.Stages[4].LastChange);
        }

        [Test]
        public void MissingObservationIsReportedAsUnavailable()
        {
            var s = TestEnv.Session("SYN_SCN_D");
            int f = -1;
            for (int i = 0; i < s.Table.FrameCount; i++)
                if (s.Table.GetBool(s.F.ObsMissing, i)) { f = i; break; }
            Assert.GreaterOrEqual(f, 0, "SYN_SCN_D contains missing observations");
            var v = PipelineRules.Compute(s, f);
            Assert.IsFalse(v.Stages[0].Available);
            Assert.AreEqual("no observation", v.Stages[0].Value);
        }

        [Test]
        public void TemperatureInputIsNeverCalledCoreTemperature()
        {
            var s = TestEnv.Session("SYN_SCN_A0");
            var v = PipelineRules.Compute(s, 100);
            foreach (var st in v.Stages)
            {
                StringAssert.DoesNotContain("core", (st.Title + " " + st.Detail).ToLowerInvariant());
            }
        }
    }

    [TestFixture]
    public class ThermalScaleTests
    {
        [Test]
        public void MonotonicWarmthAndNoRedChannelDominance()
        {
            double prevR = -1;
            for (double c = 33.0; c <= 39.0; c += 0.25)
            {
                ThermalScale.Color(c, out var r, out var g, out var b);
                Assert.That(r, Is.InRange(0.0, 1.0));
                Assert.GreaterOrEqual(r + 1e-9, prevR, "red component rises with temperature");
                prevR = r;
                Assert.IsFalse(r > 0.8 && g < 0.3 && b < 0.3, "pure red is reserved for critical states");
            }
        }

        [Test]
        public void MissingValueIsNeutralGrey()
        {
            ThermalScale.Color(double.NaN, out var r, out var g, out var b);
            Assert.AreEqual(r, g);
            Assert.AreEqual(g, b);
            Assert.IsTrue(double.IsNaN(ThermalScale.Position(double.NaN)));
        }
    }

    [TestFixture]
    public class NavBoundsTests
    {
        private static readonly NavBounds.Box Room = new NavBounds.Box(0, 0.65, -0.35, 3.4, 1.5, 3.65);
        private static readonly NavBounds.Box[] KeepOut = { new NavBounds.Box(0, -0.2, 0, 0.5, 0.65, 1.1) };

        [Test]
        public void CameraIsPushedOutOfThePatientAndTable()
        {
            double x = 0.05, y = 0.1, z = 0.2;
            Assert.IsTrue(NavBounds.Resolve(ref x, ref y, ref z, 0.2, Room, KeepOut));
            Assert.IsFalse(KeepOut[0].Contains(x, y, z, 0.2 - 1e-4));
        }

        [Test]
        public void CameraStaysInsideTheRoom()
        {
            double x = 9, y = -5, z = 20;
            NavBounds.Resolve(ref x, ref y, ref z, 0.2, Room, KeepOut);
            Assert.LessOrEqual(x, Room.Cx + Room.Hx - 0.2 + 1e-9);
            Assert.GreaterOrEqual(y, Room.Cy - Room.Hy + 0.2 - 1e-9);
            Assert.LessOrEqual(z, Room.Cz + Room.Hz - 0.2 + 1e-9);
        }

        [Test]
        public void FreePositionIsUnchanged()
        {
            double x = 1.5, y = 1.0, z = -2.0;
            Assert.IsFalse(NavBounds.Resolve(ref x, ref y, ref z, 0.2, Room, KeepOut));
            Assert.AreEqual(1.5, x);
        }
    }
}
