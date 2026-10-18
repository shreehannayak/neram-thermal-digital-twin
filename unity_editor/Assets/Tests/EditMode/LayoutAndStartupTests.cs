using Neram.Core;
using NUnit.Framework;

namespace Neram.Tests
{
    [TestFixture]
    public class LayoutAndStartupTests
    {
        [Test]
        public void ReferenceScaleAndBreakpoint()
        {
            var cases = new (int w, int h, float scale, LayoutBreakpoint bp)[]
            {
                (1920, 1080, 1.2f, LayoutBreakpoint.Wide), (1600, 900, 1.0f, LayoutBreakpoint.Wide), (1366, 768, 0.8533f, LayoutBreakpoint.Wide),
                (1920, 1200, 1.3333f, LayoutBreakpoint.Compact), (1280, 1024, 1.1378f, LayoutBreakpoint.Narrow),
            };
            foreach (var c in cases)
            {
                Assert.AreEqual(c.scale, LayoutRules.Scale(c.w, c.h), 0.001f, c.w + "x" + c.h);
                Assert.AreEqual(c.bp, LayoutRules.Breakpoint(LayoutRules.LogicalWidth(c.w, c.h)), c.w + "x" + c.h);
            }
        }

        [Test]
        public void WideWindowsScaleByWidthSoTextDoesNotShrink()
        {
            // a wide, short Editor Game view (1360 x 560) and a 21:9 monitor: the logical width stays 1600 and the text scale
            // follows the width (0.85 and 1.6) instead of the height (0.62 and 1.2)
            Assert.AreEqual(0.85f, LayoutRules.Scale(1360, 560), 0.001f);
            Assert.AreEqual(1600f, LayoutRules.LogicalWidth(1360, 560), 1f);
            Assert.AreEqual(658.8f, LayoutRules.LogicalHeight(1360, 560), 1f);
            Assert.IsTrue(LayoutRules.IsShort(LayoutRules.LogicalHeight(1360, 560)));
            Assert.AreEqual(1.6f, LayoutRules.Scale(2560, 1080), 0.001f);
            Assert.IsTrue(LayoutRules.IsShort(LayoutRules.LogicalHeight(2560, 1080)));
            Assert.IsFalse(LayoutRules.IsShort(LayoutRules.LogicalHeight(1920, 1080)));
            Assert.IsFalse(LayoutRules.IsShort(LayoutRules.LogicalHeight(1366, 768)));
            Assert.AreEqual(900f, LayoutRules.LogicalHeight(1920, 1200), 0.5f);
        }

        [Test]
        public void SixteenByNineScreensAllUseTheSameLogicalLayout()
        {
            foreach (var (w, h) in new[] { (1920, 1080), (1600, 900), (1366, 768), (2560, 1440) })
            {
                Assert.AreEqual(1600f, LayoutRules.LogicalWidth(w, h), 2f, w + "x" + h);
                Assert.AreEqual(900f, LayoutRules.LogicalHeight(w, h), 2f, w + "x" + h);
            }
        }

        [Test]
        public void FreshSessionStartsAtTheBeginningPausedAtOneTimesSpeed()
        {
            var s = TestEnv.Session("SYN_SCN_B");
            var c = new ReplayClockModel(s.Table);
            Assert.AreEqual(0, c.Frame);
            Assert.IsFalse(c.Playing);
            Assert.AreEqual(1.0, c.Speed);
            Assert.IsFalse(c.AtEnd);
        }

        [Test]
        public void LoadingAnotherScenarioDoesNotInheritSpeedOrPosition()
        {
            var a = new ReplayClockModel(TestEnv.Session("SYN_SCN_B").Table);
            a.SetSpeed(60);
            a.Play();
            a.Advance(30);
            var b = new ReplayClockModel(TestEnv.Session("SYN_SCN_C").Table); // what ReplayClock.Attach does on every load
            Assert.AreEqual(0, b.Frame);
            Assert.IsFalse(b.Playing);
            Assert.AreEqual(1.0, b.Speed);
        }
    }
}
