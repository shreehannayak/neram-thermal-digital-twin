using UnityEngine;

namespace Neram.Unity
{
    /// <summary>
    /// Lets the viewer walk the ILLUSTRATIVE surgeon figure round the theatre and look through it: I / K walk forward /
    /// back, J / L turn, U / O side-step, V cycles the camera: room camera -> behind the surgeon -> surgeon's eyes. In
    /// the two surgeon views, hold the right mouse button and move the mouse to look around. The figure stays inside the
    /// room and is kept out of the table and arm boards; a gentle walking bob plays while it moves. Purely a scene prop
    /// for inspecting the theatre: it does not interact with the replay, the twin or the controller.
    /// </summary>
    [DisallowMultipleComponent]
    [DefaultExecutionOrder(1000)]   // after CameraRig.LateUpdate, so the surgeon view wins while it is active
    public sealed class SurgeonController : MonoBehaviour
    {
        public enum ViewMode { Room, Behind, Eyes }

        public float walkSpeed = 0.9f;        // m/s
        public float turnSpeed = 95f;         // deg/s
        public Vector2 roomMinXZ = new Vector2(-3.1f, -3.7f), roomMaxXZ = new Vector2(3.1f, 3.0f);
        [Tooltip("Keep-out rectangles in the parent's frame: x half-extent, z min, z max (table, arm boards, head equipment).")]
        public Vector3[] keepOut =
        {
            new Vector3(0.52f, -1.12f, 1.10f),   // table + standing room for the body
            new Vector3(1.06f, 0.40f, 0.70f),    // arm boards
        };
        public bool showHint = true;
        [Tooltip("Eye height above the figure origin (floor), metres.")]
        public float eyeHeight = 1.672f;
        public float lookSensitivity = 0.15f;

        public ViewMode View { get; private set; } = ViewMode.Room;

        private float _baseY, _walkPhase, _lookYaw, _lookPitch = 14f;
        private Vector3 _camPos;
        private Quaternion _camRot;
        private bool _camInit;
        private float _savedFov;
        private GUIStyle _style;
        private Renderer[] _headRenderers;

        private void Start()
        {
            _baseY = transform.localPosition.y;
            var list = new System.Collections.Generic.List<Renderer>();
            foreach (var r in GetComponentsInChildren<Renderer>(true))
            {
                var n = r.gameObject.name;
                if (n.Contains("Head") || n.Contains("Cap") || n.Contains("Mask") || n.Contains("Eyes") || n.Contains("Iris") ||
                    n.Contains("Pupil") || n.Contains("Brows") || n.Contains("Hair") || n.Contains("Loop")) list.Add(r);
            }
            _headRenderers = list.ToArray();
        }

        private void Update()
        {
            float dt = Mathf.Min(Time.unscaledDeltaTime, 0.1f);
            if (NeramInput.Pressed(KeyCode.V)) SetView((ViewMode)(((int)View + 1) % 3));
            float fwd = (NeramInput.Held(KeyCode.I) ? 1f : 0f) - (NeramInput.Held(KeyCode.K) ? 1f : 0f);
            float side = (NeramInput.Held(KeyCode.O) ? 1f : 0f) - (NeramInput.Held(KeyCode.U) ? 1f : 0f);
            float turn = (NeramInput.Held(KeyCode.L) ? 1f : 0f) - (NeramInput.Held(KeyCode.J) ? 1f : 0f);
            if (turn != 0f) transform.localRotation *= Quaternion.Euler(0f, turn * turnSpeed * dt, 0f);
            if (View != ViewMode.Room && NeramInput.RightHeld)
            {
                var d = NeramInput.MouseDelta * lookSensitivity;
                _lookYaw = Mathf.Clamp(_lookYaw + d.x, -100f, 100f);
                _lookPitch = Mathf.Clamp(_lookPitch - d.y, -60f, 75f);
            }
            var p = transform.localPosition;
            bool moving = fwd != 0f || side != 0f;
            if (moving)
            {
                var f = transform.localRotation * Vector3.forward;
                var r = transform.localRotation * Vector3.right;
                var step = (f * fwd + r * side).normalized * walkSpeed * dt;
                var q = p + new Vector3(step.x, 0f, step.z);
                q.x = Mathf.Clamp(q.x, roomMinXZ.x, roomMaxXZ.x);
                q.z = Mathf.Clamp(q.z, roomMinXZ.y, roomMaxXZ.y);
                if (!Blocked(q)) p = q;
                else if (!Blocked(new Vector3(q.x, p.y, p.z))) p.x = q.x;      // slide along the obstacle
                else if (!Blocked(new Vector3(p.x, p.y, q.z))) p.z = q.z;
                _walkPhase += dt * 9f;
            }
            else _walkPhase = Mathf.MoveTowards(_walkPhase, Mathf.Round(_walkPhase / Mathf.PI) * Mathf.PI, dt * 6f);
            p.y = _baseY + Mathf.Abs(Mathf.Sin(_walkPhase)) * 0.012f;
            transform.localPosition = p;
        }

        public void SetView(ViewMode v)
        {
            var cam = Camera.main;
            if (cam != null)
            {
                if (View == ViewMode.Room && v != ViewMode.Room) _savedFov = cam.fieldOfView;
                if (v == ViewMode.Room && View != ViewMode.Room && _savedFov > 1f) cam.fieldOfView = _savedFov;
            }
            View = v;
            _camInit = false;
            if (v == ViewMode.Room) { _lookYaw = 0f; _lookPitch = 14f; }
            // hide the head from inside it in the eyes view (the camera sits where the eyes are)
            if (_headRenderers != null)
                foreach (var r in _headRenderers) if (r != null) r.enabled = v != ViewMode.Eyes;
        }

        private void LateUpdate()
        {
            if (View == ViewMode.Room) return;
            var cam = Camera.main;
            if (cam == null) return;
            var look = transform.rotation * Quaternion.Euler(_lookPitch, _lookYaw, 0f);
            var eye = transform.TransformPoint(new Vector3(0f, eyeHeight, 0.06f));
            Vector3 pos;
            if (View == ViewMode.Eyes) { pos = eye; cam.fieldOfView = 62f; }
            else
            {
                // over the right shoulder, slightly above head height
                pos = transform.TransformPoint(new Vector3(-0.32f, eyeHeight + 0.18f, -0.75f));
                look = Quaternion.LookRotation((transform.TransformPoint(new Vector3(0f, 1.05f, 0.9f)) - pos).normalized, Vector3.up)
                       * Quaternion.Euler(_lookPitch - 14f, _lookYaw, 0f);
                cam.fieldOfView = 55f;
            }
            if (!_camInit) { _camPos = pos; _camRot = look; _camInit = true; }
            float k = 1f - Mathf.Exp(-Time.unscaledDeltaTime * 12f);
            _camPos = Vector3.Lerp(_camPos, pos, k);
            _camRot = Quaternion.Slerp(_camRot, look, k);
            cam.transform.SetPositionAndRotation(_camPos, _camRot);
        }

        private bool Blocked(Vector3 q)
        {
            foreach (var k in keepOut)
                if (Mathf.Abs(q.x) < k.x && q.z > k.y && q.z < k.z) return true;
            return false;
        }

        private void OnGUI()
        {
            if (!showHint) return;
            if (_style == null)
            {
                _style = new GUIStyle(GUI.skin.label) { fontSize = Mathf.Max(11, Screen.height / 80), alignment = TextAnchor.MiddleRight };
                _style.normal.textColor = new Color(0.85f, 0.9f, 0.95f, 0.75f);
            }
            float h = _style.fontSize * 1.8f;
            string mode = View == ViewMode.Room ? "room camera" : View == ViewMode.Behind ? "behind the surgeon (right-drag to look)" : "surgeon's eyes (right-drag to look)";
            GUI.Label(new Rect(Screen.width - 760f - 12f, Screen.height - h - Screen.height * 0.115f, 760f, h),
                      "Surgeon (illustrative): I / K walk · J / L turn · U / O side-step · V view: " + mode, _style);
        }
    }
}
