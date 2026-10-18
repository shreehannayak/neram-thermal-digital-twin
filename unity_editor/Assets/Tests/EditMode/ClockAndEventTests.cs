using System.Linq;
using Neram.Core;
using NUnit.Framework;

namespace Neram.Tests
{
    [TestFixture]
    public class ClockTests
    {
        private ReplaySession _s;

        [SetUp]
        public void Load() => _s = TestEnv.Session("SYN_ENG_04");

        [Test]
        public void StartsPausedAtFirstFrame()
        {
            var c = new ReplayClockModel(_s.Table);
            Assert.AreEqual(0, c.Frame);
            Assert.IsFalse(c.Playing);
            Assert.AreEqual(1.0, c.Speed);
            Assert.IsFalse(c.Advance(10), "a paused clock does not move");
            Assert.AreEqual(0, c.Frame);
        }

        [Test]
        public void SpeedsScaleLogicalTime()
        {
            var c = new ReplayClockModel(_s.Table);
            c.Play();
            c.Advance(2.0);
            Assert.AreEqual(2, c.Frame);
            c.SetSpeed(10);
            c.Advance(1.0);
            Assert.AreEqual(12, c.Frame);
            c.SetSpeed(60);
            c.Advance(0.5);
            Assert.AreEqual(42, c.Frame);
            Assert.Throws<System.ArgumentOutOfRangeException>(() => c.SetSpeed(5));
        }

        [Test]
        public void DashboardSpeedsIncludeTwoAndFour()
        {
            CollectionAssert.AreEqual(new[] { 1.0, 2.0, 4.0, 10.0, 60.0 }, ReplayClockModel.Speeds);
            var c = new ReplayClockModel(_s.Table);
            c.Play();
            c.SetSpeed(2);
            c.Advance(1.0);
            Assert.AreEqual(2, c.Frame);
            c.SetSpeed(4);
            c.Advance(1.0);
            Assert.AreEqual(6, c.Frame);
        }

        [Test]
        public void StopsAtEndAndPlayRestarts()
        {
            var c = new ReplayClockModel(_s.Table);
            c.SetSpeed(60);
            c.Play();
            c.Advance(1e6);
            Assert.AreEqual(_s.Table.FrameCount - 1, c.Frame);
            Assert.IsFalse(c.Playing);
            Assert.IsTrue(c.AtEnd);
            c.Play();
            Assert.AreEqual(0, c.Frame, "play at end restarts from the first frame");
            Assert.IsTrue(c.Playing);
        }

        [Test]
        public void SeekIsClampedAndFrameIsLastFrameAtOrBeforeTime()
        {
            var c = new ReplayClockModel(_s.Table);
            c.Seek(-50);
            Assert.AreEqual(0, c.Frame);
            c.Seek(1e9);
            Assert.AreEqual(_s.Table.FrameCount - 1, c.Frame);
            c.Seek(100.7);
            Assert.AreEqual(100, c.Frame);
            Assert.AreEqual(100.7, c.Time, 1e-9);
        }

        [Test]
        public void StepPausesAndMovesExactlyOneFrame()
        {
            var c = new ReplayClockModel(_s.Table);
            c.Play();
            c.SeekFrame(500);
            c.StepForward();
            Assert.IsFalse(c.Playing);
            Assert.AreEqual(501, c.Frame);
            c.StepBack();
            c.StepBack();
            Assert.AreEqual(499, c.Frame);
            c.SeekFrame(0);
            c.StepBack();
            Assert.AreEqual(0, c.Frame, "cannot step before the first frame");
        }

        [Test]
        public void FrameChangedFiresOncePerChangeAndScrubIsCoherent()
        {
            var c = new ReplayClockModel(_s.Table);
            int fired = 0, last = -1;
            c.FrameChanged += f => { fired++; last = f; };
            c.SeekFraction(0.5);
            Assert.AreEqual(1, fired);
            Assert.AreEqual(c.Frame, last);
            Assert.AreEqual(_s.Table.FrameAtTime(_s.Table.StartTime + 0.5 * _s.Table.Duration), c.Frame);
            c.Seek(_s.Table.T[c.Frame] + 0.25);
            Assert.AreEqual(1, fired, "moving inside a frame does not raise FrameChanged");
            c.Restart();
            Assert.AreEqual(0, c.Frame);
            Assert.AreEqual(2, fired);
        }

        [Test]
        public void FrameLookupHandlesNonUniformTime()
        {
            var r = TestEnv.ParseText(System.IO.File.ReadAllText(System.IO.Path.Combine(TestEnv.Fixtures, "W101_nonuniform_step.jsonl")));
            Assert.IsTrue(r.Report.IsValid);
            var t = r.Table;
            for (int i = 0; i < t.FrameCount; i++)
            {
                Assert.AreEqual(i, t.FrameAtTime(t.T[i]));
                if (i + 1 < t.FrameCount) Assert.AreEqual(i, t.FrameAtTime((t.T[i] + t.T[i + 1]) / 2));
            }
        }
    }

    [TestFixture]
    public class EventIndexTests
    {
        [Test]
        public void ShutdownScenarioBookmarksAreAtTheRightTimes()
        {
            var s = TestEnv.Session("SYN_SCN_C");
            var ev = s.Events;
            var enter = ev.All.First(e => e.Kind == EventKind.SafetyShutdownEnter);
            Assert.AreEqual(46 * 60, enter.T);
            Assert.AreEqual(206, enter.Code);
            var exit = ev.All.First(e => e.Kind == EventKind.SafetyShutdownExit);
            Assert.AreEqual(60 * 60, exit.T);
            var blocked = ev.All.First(e => e.Kind == EventKind.AlertRaised && e.Code == s.AlertResetBlocked);
            Assert.AreEqual(52 * 60, blocked.T);
            Assert.IsFalse(ev.ClinicianPressesInferred, "SYN_SCN_C carries explicit Clinician_* fields");
            var resets = ev.All.Where(e => e.Kind == EventKind.ClinicianReset).Select(e => e.T).ToArray();
            CollectionAssert.AreEqual(new double[] { 52 * 60, 60 * 60 }, resets);
            var ch = ev.All.First(e => e.Kind == EventKind.ChannelFaultSet);
            Assert.AreEqual(2, ch.Channel);
        }

        [Test]
        public void ClinicianPressesAreInferredAndLabelledWhenFieldsAreAbsent()
        {
            var s = TestEnv.Session("SYN_SCN_B");
            Assert.IsTrue(s.Events.ClinicianPressesInferred);
            Assert.IsTrue(s.Events.All.Where(e => e.Category == EventCategory.Clinician).All(e => e.Inferred));
        }

        [Test]
        public void ModelProbabilityFlagsAreBookmarkedAsPossibleNotConfirmed()
        {
            var s = TestEnv.Session("SYN_SCN_B");
            var outlier = s.Events.All.Where(e => e.Kind == EventKind.FlagOutlier).ToList();
            var shift = s.Events.All.Where(e => e.Kind == EventKind.FlagLevelShift).ToList();
            Assert.IsTrue(outlier.Any(e => e.T == 70 * 60), "artefact flagged at minute 70");
            Assert.IsTrue(shift.Any(e => e.T == 105 * 60), "level shift accepted at minute 105");
            foreach (var e in outlier.Concat(shift))
            {
                StringAssert.StartsWith("Possible", e.Title);
                StringAssert.Contains("not a confirmed physiological event", e.Detail);
                Assert.IsFalse(double.IsNaN(e.Probability));
            }
        }

        [Test]
        public void NavigationFindsNextAndPreviousByCategory()
        {
            var s = TestEnv.Session("SYN_ENG_03");
            var ev = s.Events;
            var firstFault = ev.Next(0, EventCategory.Safety);
            Assert.IsNotNull(firstFault);
            Assert.AreEqual(20 * 60 + 2, firstFault.T);
            var nextSafety = ev.Next(firstFault.Frame, EventCategory.Safety);
            Assert.IsNotNull(nextSafety);
            Assert.Greater(nextSafety.T, firstFault.T);
            var prev = ev.Previous(nextSafety.Frame, EventCategory.Safety);
            Assert.AreEqual(firstFault.Frame, prev.Frame);
            Assert.IsNull(ev.Previous(0, EventCategory.All));
            var lastFrame = s.Table.FrameCount - 1;
            Assert.IsNull(ev.Next(lastFrame, EventCategory.All));
        }

        [Test]
        public void EventsAreSortedByFrame()
        {
            foreach (var id in new[] { "SYN_SCN_A0", "SYN_SCN_B", "SYN_SCN_C", "SYN_SCN_D", "SYN_ENG_02" })
            {
                var all = TestEnv.Session(id).Events.All;
                for (int i = 1; i < all.Count; i++) Assert.LessOrEqual(all[i - 1].Frame, all[i].Frame, id);
            }
        }

        [Test]
        public void EveryStateChangeInTheDataHasExactlyOneTransitionEvent()
        {
            var s = TestEnv.Session("SYN_SCN_D");
            int changes = 0;
            for (int f = 1; f < s.Table.FrameCount; f++)
                if (s.Table.GetInt(s.F.State, f) != s.Table.GetInt(s.F.State, f - 1)) changes++;
            Assert.AreEqual(changes, s.Events.All.Count(e => e.Kind == EventKind.StateChange));
        }
    }
}
