using System.Collections.Generic;
using UnityEngine;

namespace Neram.Unity
{
    /// <summary>One vessel of the ILLUSTRATIVE network shown in Internal View ("artery" or "vein"). Its waypoint children
    /// (wp*) give the path the illustrative pulses travel along. Not patient-specific anatomy or flow data.</summary>
    [DisallowMultipleComponent]
    public sealed class NeramVessel : MonoBehaviour
    {
        public string kind = "artery";

        public Vector3[] Waypoints()
        {
            var list = new List<Transform>();
            foreach (Transform c in transform) if (c.name.StartsWith("wp")) list.Add(c);
            list.Sort((a, b) => string.CompareOrdinal(a.name, b.name));
            var pts = new Vector3[list.Count];
            for (int i = 0; i < list.Count; i++) pts[i] = list[i].position;
            return pts;
        }
    }
}
