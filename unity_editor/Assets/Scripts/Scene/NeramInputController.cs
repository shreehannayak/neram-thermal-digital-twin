using System;
using UnityEngine;
using UnityEngine.UIElements;

namespace Neram.Unity
{
    /// <summary>
    /// Camera + 3D selection input, polled every frame (NeramInput). It works even if the dashboard failed to build, and
    /// it never acts on a pointer that is over a dashboard element: a pointer is "over UI" when the UI Toolkit panel picks an
    /// element inside a container with the class <c>ui-block</c> (header, side columns, charts, transport, toolbars, drawers).
    ///
    /// Inspect mode: left-drag orbit · right/middle-drag pan · wheel zoom · click selects a region · hover identifies it.
    /// Free Roam (toggle from the toolbar or R): WASD move · mouse look (cursor locked) · Space up · Ctrl down ·
    /// Shift faster · Esc leaves Free Roam and releases the mouse.
    /// </summary>
    [DefaultExecutionOrder(50)]
    public sealed class NeramInputController : MonoBehaviour
    {
        public CameraRig rig;
        public UIDocument document;
        [Tooltip("Pixels the pointer may move between press and release and still count as a click.")]
        public float clickSlop = 6f;

        public event Action<NeramRegion> Picked;
        public event Action<NeramRegion> HoverChanged;
        /// <summary>Raised when Free Roam is entered (true) or left (false).</summary>
        public event Action<bool> FreeRoamChanged;

        public NeramRegion Hovered { get; private set; }
        public bool PointerOverUi { get; private set; }
        public Vector2 PointerPanelPosition { get; private set; }
        /// <summary>Frame on which Free Roam was last left (so Esc is not also handled as "deselect" that frame).</summary>
        public int RoamExitFrame { get; private set; } = -1;

        private enum Drag { None, Orbit, Pan }
        private Drag _drag;
        private Vector2 _downPos;
        private bool _moved;
        private int _hoverFrame;
        private int _lockFrame = -10;

        private void Awake()
        {
            if (rig == null) rig = GetComponent<CameraRig>();
            if (rig == null) rig = FindAnyObjectByType<CameraRig>();
            if (document == null) document = FindAnyObjectByType<UIDocument>();
            if (rig != null) rig.FreeRoamChanged += OnRigRoam;
        }

        private void OnDestroy()
        {
            if (rig != null) rig.FreeRoamChanged -= OnRigRoam;
            ReleaseCursor();
        }

        private void OnRigRoam(bool on)
        {
            if (on)
            {
                UnityEngine.Cursor.lockState = CursorLockMode.Locked;
                UnityEngine.Cursor.visible = false;
                _lockFrame = Time.frameCount;
                SetHover(null);
                _drag = Drag.None;
            }
            else { ReleaseCursor(); RoamExitFrame = Time.frameCount; }
            FreeRoamChanged?.Invoke(on);
        }

        private static void ReleaseCursor()
        {
            UnityEngine.Cursor.lockState = CursorLockMode.None;
            UnityEngine.Cursor.visible = true;
        }

        public void ToggleFreeRoam()
        {
            if (rig != null) rig.SetFreeRoam(!rig.FreeRoam);
        }

        private void Update()
        {
            if (rig == null || !NeramInput.HasMouse) return;
            float dt = Time.unscaledDeltaTime;
            if (rig.FreeRoam)
            {
                if (NeramInput.Pressed(KeyCode.Escape)) { rig.SetFreeRoam(false); return; }
                var move = new Vector3(
                    (NeramInput.Held(KeyCode.D) ? 1 : 0) - (NeramInput.Held(KeyCode.A) ? 1 : 0),
                    (NeramInput.Held(KeyCode.Space) ? 1 : 0) - (NeramInput.CtrlHeld ? 1 : 0),
                    (NeramInput.Held(KeyCode.W) ? 1 : 0) - (NeramInput.Held(KeyCode.S) ? 1 : 0));
                // locking the cursor recentres it; ignore that jump for two frames
                var look = Time.frameCount <= _lockFrame + 2 ? Vector2.zero : NeramInput.MouseDelta;
                rig.Roam(move, look, NeramInput.ShiftHeld, dt);
                return;
            }

            var mouse = NeramInput.MousePosition;
            PointerOverUi = IsOverUi(mouse);

            if (NeramInput.LeftDown || NeramInput.RightDown)
            {
                _downPos = mouse;
                _moved = false;
                _drag = PointerOverUi ? Drag.None : NeramInput.LeftDown ? Drag.Orbit : Drag.Pan;
            }
            if (_drag != Drag.None)
            {
                var d = NeramInput.MouseDelta;
                if ((mouse - _downPos).sqrMagnitude > clickSlop * clickSlop) _moved = true;
                if (_moved)
                {
                    SetHover(null);
                    if (_drag == Drag.Orbit && NeramInput.LeftHeld) rig.Orbit(new Vector2(d.x, -d.y));
                    else if (_drag == Drag.Pan && NeramInput.RightHeld) rig.Pan(d);
                }
                if (_drag == Drag.Orbit && NeramInput.LeftUp)
                {
                    if (!_moved) Picked?.Invoke(Raycast(mouse));
                    _drag = Drag.None;
                }
                else if (_drag == Drag.Pan && !NeramInput.RightHeld) _drag = Drag.None;
                else if (_drag == Drag.Orbit && !NeramInput.LeftHeld) _drag = Drag.None;
            }
            else if (!PointerOverUi)
            {
                var wheel = NeramInput.Scroll;
                if (Mathf.Abs(wheel) > 0.01f) rig.Zoom(wheel);
                if (++_hoverFrame % 2 == 0) SetHover(Raycast(mouse));
            }
            else SetHover(null);
        }

        private void SetHover(NeramRegion r)
        {
            if (r == Hovered) return;
            if (Hovered != null) Hovered.SetHover(false);
            Hovered = r;
            if (Hovered != null) Hovered.SetHover(true);
            HoverChanged?.Invoke(Hovered);
        }

        /// <summary>Region under a screen position (null if none).</summary>
        public NeramRegion Raycast(Vector2 screen)
        {
            var cam = rig != null ? rig.cam : null;
            if (cam == null) return null;
            var ray = cam.ScreenPointToRay(screen);
            if (!Physics.Raycast(ray, out var hit, 60f)) return null;
            return hit.collider.GetComponentInParent<NeramRegion>();
        }

        /// <summary>True when the pointer is over a dashboard element (container with class "ui-block").</summary>
        public bool IsOverUi(Vector2 screen)
        {
            if (document == null) return false;
            var root = document.rootVisualElement;
            var panel = root != null ? root.panel : null;
            if (panel == null || Screen.width <= 0 || Screen.height <= 0) return false;
            var rb = panel.visualTree.worldBound;
            if (rb.width <= 0 || rb.height <= 0) return false;
            // RuntimePanelUtils.ScreenToPanel expects a top-left origin (hence the y flip)
            var p = RuntimePanelUtils.ScreenToPanel(panel, new Vector2(screen.x, Screen.height - screen.y));
            PointerPanelPosition = p;
            for (var e = panel.Pick(p); e != null; e = e.parent)
                if (e.ClassListContains("ui-block")) return true;
            return false;
        }
    }
}
