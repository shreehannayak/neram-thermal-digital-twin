using UnityEngine;

namespace Neram.Unity
{
    /// <summary>Camera preset: its transform position is the orbit pivot; yaw/pitch/distance define the view.</summary>
    public sealed class CameraPreset : MonoBehaviour
    {
        public string label = "Overview";
        public float yaw = -35f;
        public float pitch = 32f;
        public float distance = 3.2f;
        public int order;
    }
}
