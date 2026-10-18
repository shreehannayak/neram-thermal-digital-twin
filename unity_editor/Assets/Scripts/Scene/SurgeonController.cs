using UnityEngine;

namespace Neram.Unity
{
    /// <summary>
    /// Lets the viewer walk the ILLUSTRATIVE surgeon figure round the theatre: I / K walk forward / back, J / L turn,
    /// U / O side-step. The figure stays inside the room and is kept out of the table and arm boards. A gentle walking
    /// bob plays while it moves. Purely a scene prop: it does not interact with the replay, the twin or the controller.
    /// </summary>
    [DisallowMultipleComponent]
    public sealed class SurgeonController : MonoBehaviour
    {
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

        private float _baseY, _walkPhase;
        private GUIStyle _style;

        private void Start() => _baseY = transform.localPosition.y;

        private void Update()
        {
            float dt = Mathf.Min(Time.unscaledDeltaTime, 0.1f);
            float fwd = (NeramInput.Held(KeyCode.I) ? 1f : 0f) - (NeramInput.Held(KeyCode.K) ? 1f : 0f);
            float side = (NeramInput.Held(KeyCode.O) ? 1f : 0f) - (NeramInput.Held(KeyCode.U) ? 1f : 0f);
            float turn = (NeramInput.Held(KeyCode.L) ? 1f : 0f) - (NeramInput.Held(KeyCode.J) ? 1f : 0f);
            if (turn != 0f) transform.localRotation *= Quaternion.Euler(0f, turn * turnSpeed * dt, 0f);
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
            GUI.Label(new Rect(Screen.width - 520f - 12f, Screen.height - h - Screen.height * 0.115f, 520f, h),
                      "Surgeon figure (illustrative): I / K walk · J / L turn · U / O side-step", _style);
        }
    }
}
