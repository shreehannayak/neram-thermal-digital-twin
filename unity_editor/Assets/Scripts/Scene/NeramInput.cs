using UnityEngine;
#if NERAM_INPUT_SYSTEM && ENABLE_INPUT_SYSTEM
using UnityEngine.InputSystem;
#endif

namespace Neram.Unity
{
    /// <summary>
    /// Thin polling layer over the active input backend: the Input System when the package is installed and enabled
    /// (Active Input Handling = Input System, as in this project), otherwise the legacy Input Manager. Camera, selection
    /// and keyboard shortcuts read input here every frame, so they keep working even if the dashboard UI failed to build.
    /// Mouse positions are screen pixels with the origin at the bottom-left (Unity screen space).
    /// </summary>
    public static class NeramInput
    {
#if NERAM_INPUT_SYSTEM && ENABLE_INPUT_SYSTEM
        public static bool HasMouse => Mouse.current != null;
        public static Vector2 MousePosition => Mouse.current != null ? Mouse.current.position.ReadValue() : Vector2.zero;
        public static Vector2 MouseDelta => Mouse.current != null ? Mouse.current.delta.ReadValue() : Vector2.zero;
        /// <summary>Wheel in "notches" (positive = away from the user).</summary>
        public static float Scroll
        {
            get
            {
                if (Mouse.current == null) return 0f;
                float y = Mouse.current.scroll.ReadValue().y;
                // Input System default (UniformAcrossAllPlatforms) reports about +-1 per notch; the platform-specific
                // range (Windows: +-120 per notch) only applies when the project opts into it.
                return InputSystem.settings != null && InputSystem.settings.scrollDeltaBehavior == InputSettings.ScrollDeltaBehavior.KeepPlatformSpecificInputRange ? y / 120f : y;
            }
        }
        public static bool LeftDown => Mouse.current != null && Mouse.current.leftButton.wasPressedThisFrame;
        public static bool LeftUp => Mouse.current != null && Mouse.current.leftButton.wasReleasedThisFrame;
        public static bool LeftHeld => Mouse.current != null && Mouse.current.leftButton.isPressed;
        public static bool RightDown => Mouse.current != null && (Mouse.current.rightButton.wasPressedThisFrame || Mouse.current.middleButton.wasPressedThisFrame);
        public static bool RightHeld => Mouse.current != null && (Mouse.current.rightButton.isPressed || Mouse.current.middleButton.isPressed);

        public static bool Held(KeyCode k)
        {
            var c = Control(k);
            return c != null && c.isPressed;
        }

        public static bool Pressed(KeyCode k)
        {
            var c = Control(k);
            return c != null && c.wasPressedThisFrame;
        }

        private static UnityEngine.InputSystem.Controls.KeyControl Control(KeyCode k)
        {
            var kb = Keyboard.current;
            if (kb == null) return null;
            switch (k)
            {
                case KeyCode.W: return kb.wKey;
                case KeyCode.A: return kb.aKey;
                case KeyCode.S: return kb.sKey;
                case KeyCode.D: return kb.dKey;
                case KeyCode.R: return kb.rKey;
                case KeyCode.T: return kb.tKey;
                case KeyCode.F: return kb.fKey;
                case KeyCode.C: return kb.cKey;
                case KeyCode.P: return kb.pKey;
                case KeyCode.B: return kb.bKey;
                case KeyCode.M: return kb.mKey;
                case KeyCode.N: return kb.nKey;
                case KeyCode.I: return kb.iKey;   // surgeon figure (SurgeonController)
                case KeyCode.J: return kb.jKey;
                case KeyCode.K: return kb.kKey;
                case KeyCode.L: return kb.lKey;
                case KeyCode.U: return kb.uKey;
                case KeyCode.O: return kb.oKey;
                case KeyCode.F11: return kb.f11Key;
                case KeyCode.Space: return kb.spaceKey;
                case KeyCode.LeftControl: return kb.leftCtrlKey;
                case KeyCode.RightControl: return kb.rightCtrlKey;
                case KeyCode.LeftShift: return kb.leftShiftKey;
                case KeyCode.RightShift: return kb.rightShiftKey;
                case KeyCode.Escape: return kb.escapeKey;
                case KeyCode.LeftArrow: return kb.leftArrowKey;
                case KeyCode.RightArrow: return kb.rightArrowKey;
                case KeyCode.Home: return kb.homeKey;
                case KeyCode.Alpha1: return kb.digit1Key;
                case KeyCode.Alpha2: return kb.digit2Key;
                case KeyCode.Alpha3: return kb.digit3Key;
                case KeyCode.Alpha4: return kb.digit4Key;
                case KeyCode.Alpha5: return kb.digit5Key;
                case KeyCode.Keypad1: return kb.numpad1Key;
                case KeyCode.Keypad2: return kb.numpad2Key;
                case KeyCode.Keypad3: return kb.numpad3Key;
                case KeyCode.Keypad4: return kb.numpad4Key;
                case KeyCode.Keypad5: return kb.numpad5Key;
                default: return null;
            }
        }
#elif ENABLE_LEGACY_INPUT_MANAGER
        public static bool HasMouse => true;
        public static Vector2 MousePosition => Input.mousePosition;
        public static Vector2 MouseDelta => new Vector2(Input.GetAxisRaw("Mouse X"), Input.GetAxisRaw("Mouse Y")) * 10f;
        public static float Scroll => Input.mouseScrollDelta.y;
        public static bool LeftDown => Input.GetMouseButtonDown(0);
        public static bool LeftUp => Input.GetMouseButtonUp(0);
        public static bool LeftHeld => Input.GetMouseButton(0);
        public static bool RightDown => Input.GetMouseButtonDown(1) || Input.GetMouseButtonDown(2);
        public static bool RightHeld => Input.GetMouseButton(1) || Input.GetMouseButton(2);
        public static bool Held(KeyCode k) => Input.GetKey(k);
        public static bool Pressed(KeyCode k) => Input.GetKeyDown(k);
#else
        public static bool HasMouse => false;
        public static Vector2 MousePosition => Vector2.zero;
        public static Vector2 MouseDelta => Vector2.zero;
        public static float Scroll => 0f;
        public static bool LeftDown => false;
        public static bool LeftUp => false;
        public static bool LeftHeld => false;
        public static bool RightDown => false;
        public static bool RightHeld => false;
        public static bool Held(KeyCode k) => false;
        public static bool Pressed(KeyCode k) => false;
#endif

        public static bool ShiftHeld => Held(KeyCode.LeftShift) || Held(KeyCode.RightShift);
        public static bool CtrlHeld => Held(KeyCode.LeftControl) || Held(KeyCode.RightControl);
    }
}
