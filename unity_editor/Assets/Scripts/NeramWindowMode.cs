using UnityEngine;

namespace Neram
{
    /// <summary>
    /// The built player always starts as a normal maximised desktop window, even if an earlier run was left in
    /// fullscreen (Unity remembers the last screen mode per user). F11 / FULLSCREEN still switch modes during a session.
    /// Display behaviour only; no replay data is touched. (Sai, 18 Oct 2026)
    /// </summary>
    public static class NeramWindowMode
    {
        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        private static void StartWindowed()
        {
            if (Application.isEditor || Application.platform != RuntimePlatform.WindowsPlayer) return;
            Screen.fullScreenMode = FullScreenMode.MaximizedWindow;
        }
    }
}
