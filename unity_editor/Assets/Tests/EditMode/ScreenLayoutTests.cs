using Neram.Core;
using NUnit.Framework;

namespace Neram.Tests
{
    /// <summary>v4 screens and panel visibility (display only; no replay data involved).</summary>
    [TestFixture]
    public class ScreenLayoutTests
    {
        [Test]
        public void TheatreStartsCleanAndAnalysisShowsEverything()
        {
            var l = new ScreenLayout();
            foreach (var id in ScreenLayout.LeftColumn) Assert.IsFalse(l.IsVisible(ScreenMode.Theatre, id), id);
            foreach (var id in ScreenLayout.Charts) Assert.IsFalse(l.IsVisible(ScreenMode.Theatre, id), id);
            Assert.IsFalse(l.IsVisible(ScreenMode.Theatre, ScreenLayout.Pipeline));
            Assert.IsFalse(l.IsVisible(ScreenMode.Theatre, ScreenLayout.Forecast));
            Assert.IsFalse(l.IsVisible(ScreenMode.Theatre, ScreenLayout.Details));
            Assert.IsTrue(l.IsVisible(ScreenMode.Theatre, ScreenLayout.Safety), "a latched safety shutdown stays visible by default");
            foreach (var id in ScreenLayout.All) Assert.IsTrue(l.IsVisible(ScreenMode.Analysis, id), id);
        }

        [Test]
        public void MonitorContainsValuesPipelineGraphsAndForecastButNo3DOverlays()
        {
            var l = new ScreenLayout();
            foreach (var id in new[] { ScreenLayout.Temp, ScreenLayout.Twin, ScreenLayout.ControllerInfo, ScreenLayout.Channels,
                         ScreenLayout.Pipeline, ScreenLayout.ChartA, ScreenLayout.ChartB, ScreenLayout.ChartC, ScreenLayout.Forecast,
                         ScreenLayout.Unavailable, ScreenLayout.Controller })
                Assert.IsTrue(l.IsVisible(ScreenMode.Monitor, id), id);
            foreach (var id in new[] { ScreenLayout.Details, ScreenLayout.Legend, ScreenLayout.Labels, ScreenLayout.FaultStrip })
                Assert.IsFalse(ScreenLayout.AvailableIn(ScreenMode.Monitor, id), id);
        }

        [Test]
        public void EveryPanelCanBeHiddenAndRestoredIndependently()
        {
            var l = new ScreenLayout();
            foreach (var mode in new[] { ScreenMode.Analysis, ScreenMode.Monitor })
                foreach (var id in ScreenLayout.All)
                {
                    if (!ScreenLayout.AvailableIn(mode, id)) continue;
                    l.Set(mode, id, false);
                    Assert.IsFalse(l.IsVisible(mode, id), mode + " " + id);
                    foreach (var other in ScreenLayout.All)
                        if (other != id && ScreenLayout.AvailableIn(mode, other))
                            Assert.IsTrue(l.IsVisible(mode, other), "hiding " + id + " must not hide " + other);
                    l.Set(mode, id, true);
                    Assert.IsTrue(l.IsVisible(mode, id), mode + " " + id);
                }
        }

        [Test]
        public void HideAllShowAllAndResetActOnOneScreenOnly()
        {
            var l = new ScreenLayout();
            l.HideAll(ScreenMode.Analysis);
            Assert.AreEqual(l.AvailableCount(ScreenMode.Analysis), l.HiddenCount(ScreenMode.Analysis));
            Assert.IsTrue(l.IsVisible(ScreenMode.Monitor, ScreenLayout.ChartB), "the monitor keeps its own panels");
            l.ShowAll(ScreenMode.Theatre);
            Assert.AreEqual(0, l.HiddenCount(ScreenMode.Theatre));
            l.Reset(ScreenMode.Theatre);
            Assert.IsFalse(l.IsVisible(ScreenMode.Theatre, ScreenLayout.ChartA));
            l.Reset(ScreenMode.Analysis);
            Assert.AreEqual(0, l.HiddenCount(ScreenMode.Analysis));
        }

        [Test]
        public void MonitorPagesSplitTheMonitorPanelsWithoutOverlap()
        {
            var seen = new System.Collections.Generic.HashSet<string>();
            foreach (MonitorPage page in System.Enum.GetValues(typeof(MonitorPage)))
                foreach (var id in ScreenLayout.OnPage(page))
                {
                    Assert.IsTrue(ScreenLayout.AvailableIn(ScreenMode.Monitor, id), id);
                    Assert.IsTrue(seen.Add(id), id + " appears on two monitor pages");
                }
            foreach (var id in ScreenLayout.All)
                if (ScreenLayout.AvailableIn(ScreenMode.Monitor, id) && id != ScreenLayout.Safety)
                    Assert.IsTrue(seen.Contains(id), id + " is on no monitor page");
            Assert.AreEqual(1, ScreenLayout.OnPage(MonitorPage.Channels).Length, "graph C has a page of its own");
            Assert.AreEqual(2, ScreenLayout.OnPage(MonitorPage.Graphs).Length, "graphs A and B share a page");
        }

        [Test]
        public void EveryPanelHasATitleForThePanelsList()
        {
            foreach (var id in ScreenLayout.All) Assert.AreNotEqual(id, ScreenLayout.Title(id), id);
        }
    }
}
