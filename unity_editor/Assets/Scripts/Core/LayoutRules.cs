using System;

namespace Neram.Core
{
    public enum LayoutBreakpoint { Wide, Compact, Narrow }

    /// <summary>
    /// Display-only layout arithmetic for the dashboard (no replay values). The panel uses a 1600 x 900 reference with
    /// PanelScreenMatchMode.Shrink: scale = max(width / 1600, height / 900). 16:9 gives exactly 1600 x 900; narrower
    /// screens keep the logical height at 900 (logical width = 900 x aspect); wider screens keep the logical width at 1600
    /// (logical height = 1600 / aspect), so text never shrinks just because a window is wide and short.
    /// </summary>
    public static class LayoutRules
    {
        public const float ReferenceWidth = 1600f, ReferenceHeight = 900f;
        public const float CompactBelow = 1500f, NarrowBelow = 1300f;
        /// <summary>Logical heights below this get the "short" layout (wider than about 2:1).</summary>
        public const float ShortBelow = 800f;

        /// <summary>Breakpoint for a resolved logical panel width.</summary>
        public static LayoutBreakpoint Breakpoint(float logicalWidth)
        {
            if (float.IsNaN(logicalWidth) || logicalWidth <= 0) return LayoutBreakpoint.Wide;
            if (logicalWidth < NarrowBelow) return LayoutBreakpoint.Narrow;
            if (logicalWidth < CompactBelow) return LayoutBreakpoint.Compact;
            return LayoutBreakpoint.Wide;
        }

        /// <summary>UI scale factor (physical px per logical px): max(width / 1600, height / 900) (Shrink).</summary>
        public static float Scale(int screenWidth, int screenHeight)
        {
            if (screenWidth <= 0 || screenHeight <= 0) return 1f;
            return Math.Max(screenWidth / ReferenceWidth, screenHeight / ReferenceHeight);
        }

        /// <summary>Logical width of the dashboard for a screen.</summary>
        public static float LogicalWidth(int screenWidth, int screenHeight) => screenWidth <= 0 || screenHeight <= 0 ? ReferenceWidth : screenWidth / Scale(screenWidth, screenHeight);

        /// <summary>Logical height of the dashboard for a screen (900 unless the screen is wider than 16:9).</summary>
        public static float LogicalHeight(int screenWidth, int screenHeight) => screenWidth <= 0 || screenHeight <= 0 ? ReferenceHeight : screenHeight / Scale(screenWidth, screenHeight);

        /// <summary>True for logical heights that need the short layout.</summary>
        public static bool IsShort(float logicalHeight) => !float.IsNaN(logicalHeight) && logicalHeight > 0 && logicalHeight < ShortBelow;
    }
}
