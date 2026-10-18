using System.Collections.Generic;
using UnityEngine;

namespace Neram.Unity
{
    /// <summary>Selectable anatomical / device regions of the 3D twin view.</summary>
    public enum RegionId
    {
        None = 0,
        HandLeft, HandRight, ArmLeft, ArmRight, Torso, LegLeft, LegRight, FootLeft, FootRight, Wearable, Controller,
        /// <summary>The bedside patient monitor prop (v4): clicking it opens the MONITOR screen; it is never "selected".</summary>
        Monitor,
    }

    /// <summary>
    /// Marks a clickable region (hand, arm, torso, leg, foot, wrist wearable, bedside controller). Hover and selection
    /// highlight every renderer below it by tinting its emission through a MaterialPropertyBlock. Renderers named
    /// "*_Heater" are skipped because their emission is reserved for the replayed heating command (ModuleView).
    /// The highlight is a display cue only; it never changes any replay value.
    /// </summary>
    [DisallowMultipleComponent]
    public sealed class NeramRegion : MonoBehaviour
    {
        public RegionId region = RegionId.None;
        [Tooltip("Warming channel 1-4 when this region carries a module, 0 otherwise.")]
        [Range(0, 4)] public int channel;
        [ColorUsage(false, true)] public Color hoverEmission = new Color(0.05f, 0.30f, 0.33f);
        [ColorUsage(false, true)] public Color selectedEmission = new Color(0.10f, 0.62f, 0.70f);

        private static readonly int EmissionId = Shader.PropertyToID("_EmissionColor");
        private readonly List<Renderer> _renderers = new List<Renderer>();
        private MaterialPropertyBlock _mpb;
        private bool _hover, _selected;

        public bool Hovered => _hover;
        public bool Selected => _selected;

        public static string Title(RegionId r)
        {
            switch (r)
            {
                case RegionId.HandLeft: return "LEFT HAND — CH1";
                case RegionId.HandRight: return "RIGHT HAND — CH2";
                case RegionId.FootLeft: return "LEFT FOOT — CH3";
                case RegionId.FootRight: return "RIGHT FOOT — CH4";
                case RegionId.ArmLeft: return "LEFT ARM";
                case RegionId.ArmRight: return "RIGHT ARM";
                case RegionId.LegLeft: return "LEFT LEG";
                case RegionId.LegRight: return "RIGHT LEG";
                case RegionId.Torso: return "CHEST / TORSO";
                case RegionId.Wearable: return "WRIST WEARABLE \u00b7 DISPLAY ONLY (right wrist)";
                case RegionId.Controller: return "BEDSIDE CONTROLLER";
                case RegionId.Monitor: return "PATIENT MONITOR";
                default: return "";
            }
        }

        /// <summary>Channel carried by a region (1..4) or 0.</summary>
        public static int ChannelOf(RegionId r)
        {
            switch (r)
            {
                case RegionId.HandLeft: return 1;
                case RegionId.HandRight: return 2;
                case RegionId.FootLeft: return 3;
                case RegionId.FootRight: return 4;
                default: return 0;
            }
        }

        public static RegionId ForChannel(int ch)
        {
            switch (ch)
            {
                case 1: return RegionId.HandLeft;
                case 2: return RegionId.HandRight;
                case 3: return RegionId.FootLeft;
                case 4: return RegionId.FootRight;
                default: return RegionId.None;
            }
        }

        /// <summary>Parses the region keys written by tools/gen_neram_scene.py (e.g. "hand_left").</summary>
        public static RegionId Parse(string key)
        {
            switch (key)
            {
                case "hand_left": return RegionId.HandLeft;
                case "hand_right": return RegionId.HandRight;
                case "arm_left": return RegionId.ArmLeft;
                case "arm_right": return RegionId.ArmRight;
                case "torso": return RegionId.Torso;
                case "leg_left": return RegionId.LegLeft;
                case "leg_right": return RegionId.LegRight;
                case "foot_left": return RegionId.FootLeft;
                case "foot_right": return RegionId.FootRight;
                case "wearable": return RegionId.Wearable;
                case "controller": return RegionId.Controller;
                default: return RegionId.None;
            }
        }

        private void Awake() => Collect();

        public void Collect()
        {
            _renderers.Clear();
            foreach (var r in GetComponentsInChildren<Renderer>(true))
            {
                var n = r.gameObject.name;
                if (n.StartsWith("__") || n.StartsWith("BC_LED") || n == "BC_Display" || BelowHeater(r.transform)) continue;
                var m = r.sharedMaterial;
                if (m != null && m.name.StartsWith("MAT_TEX_")) continue; // screens/labels keep their own (texture) emission
                _renderers.Add(r);
            }
            if (_mpb == null) _mpb = new MaterialPropertyBlock();
        }

        /// <summary>True when the renderer is a heater part (or below one): its emission belongs to ModuleView (Heat_i).</summary>
        private bool BelowHeater(Transform t)
        {
            for (var p = t; p != null && p != transform; p = p.parent)
                if (p.name.EndsWith("_Heater")) return true;
            return false;
        }

        public void SetHover(bool on)
        {
            if (_hover == on) return;
            _hover = on;
            Apply();
        }

        public void SetSelected(bool on)
        {
            if (_selected == on) return;
            _selected = on;
            Apply();
        }

        private void Apply()
        {
            if (_mpb == null) Collect();
            var c = _selected ? selectedEmission : _hover ? hoverEmission : Color.black;
            foreach (var r in _renderers)
            {
                if (r == null) continue;
                r.GetPropertyBlock(_mpb);
                _mpb.SetColor(EmissionId, c);
                r.SetPropertyBlock(_mpb);
            }
        }

        /// <summary>World-space centre of the region (renderer bounds), used for camera focus.</summary>
        public Vector3 Center
        {
            get
            {
                bool any = false;
                var b = new Bounds(transform.position, Vector3.zero);
                foreach (var r in _renderers)
                {
                    if (r == null) continue;
                    if (!any) { b = r.bounds; any = true; }
                    else b.Encapsulate(r.bounds);
                }
                return b.center;
            }
        }

        public float Radius
        {
            get
            {
                bool any = false;
                var b = new Bounds(transform.position, Vector3.zero);
                foreach (var r in _renderers)
                {
                    if (r == null) continue;
                    if (!any) { b = r.bounds; any = true; }
                    else b.Encapsulate(r.bounds);
                }
                return b.extents.magnitude;
            }
        }
    }
}
