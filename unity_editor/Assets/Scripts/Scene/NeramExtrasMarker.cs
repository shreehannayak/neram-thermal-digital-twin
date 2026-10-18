using UnityEngine;

namespace Neram.Unity
{
    /// <summary>Marks objects created by Editor/NeramSceneExtras.cs so a re-apply can replace them.</summary>
    [DisallowMultipleComponent]
    public sealed class NeramExtrasMarker : MonoBehaviour { }
}
