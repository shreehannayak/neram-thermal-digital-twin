using UnityEngine;

namespace Neram.Unity
{
    /// <summary>Records which NERAM setup version generated the open scene. Validation and the first-run helper compare it
    /// with <see cref="NeramVersion.Value"/> so an outdated scene (e.g. one saved by an older setup with an empty
    /// PanelSettings reference) is detected instead of silently running with new scripts.</summary>
    [DisallowMultipleComponent]
    public sealed class NeramSceneStamp : MonoBehaviour
    {
        public string generatorVersion = "";
        public string generatedUtc = "";
    }
}
