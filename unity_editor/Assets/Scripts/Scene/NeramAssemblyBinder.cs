using System.Collections.Generic;
using System.Globalization;
using System.IO;
using Neram.Core;
using UnityEngine;

namespace Neram.Unity
{
    /// <summary>
    /// Binds replay data to the 3D assembly by NAME, so Neharika's CAD/FBX can replace the placeholders without code
    /// changes. For every role (Left_Hand_Module, Bedside_Controller, Cable_CH1, ...) the binder prefers an object with the
    /// exact CAD name and disables the "&lt;role&gt;_PLACEHOLDER" object. Modules get a ModuleView, the controller a
    /// ControllerView3D, and any renderer without a collider gets a MeshCollider for picking.
    /// </summary>
    [DefaultExecutionOrder(-100)]
    public sealed class NeramAssemblyBinder : MonoBehaviour
    {
        public Material haloMaterial;
        public Transform thermalAnchor;

        public readonly ModuleView[] Modules = new ModuleView[4];
        public ControllerView3D Controller { get; private set; }
        public readonly Transform[] Connectors = new Transform[4];
        private readonly Vector3[] _connectorBase = new Vector3[4];
        /// <summary>Which roles use CAD geometry and which still use placeholders (shown in Diagnostics / inspector).</summary>
        public readonly List<string> Report = new List<string>();

        public bool IsBound { get; private set; }

        private void Awake() => EnsureBound();

        /// <summary>Bind once (safe to call from any script regardless of execution order).</summary>
        public void EnsureBound()
        {
            if (!IsBound) Bind();
        }

        public void Bind()
        {
            IsBound = true;
            Report.Clear();
            var offsets = LoadExplodedOffsets();
            for (int i = 0; i < 4; i++)
            {
                var go = Resolve(SceneNames.Modules[i]);
                if (go == null) { Report.Add(SceneNames.Modules[i] + ": MISSING"); continue; }
                var mv = go.GetComponent<ModuleView>();
                if (mv == null) mv = go.AddComponent<ModuleView>(); // no '??': Unity fake-null objects
                mv.channel = i + 1;
                if (mv.haloMaterial == null) mv.haloMaterial = haloMaterial;
                EnsureColliders(go);
                mv.Build(offsets);
                if (!mv.HasCadHeater) Report.Add(SceneNames.Modules[i] + ": no " + SceneNames.Part(i + 1, "Heater") + " part found (heater glow unavailable)");
                Modules[i] = mv;
                var cable = Resolve(SceneNames.Cable(i + 1));
                var conn = cable != null ? FindDeep(cable.transform, SceneNames.Connector(i + 1)) : FindDeep(transform, SceneNames.Connector(i + 1));
                Connectors[i] = conn;
                if (conn != null) _connectorBase[i] = conn.localPosition;
            }
            var ctrl = Resolve(SceneNames.Controller);
            if (ctrl != null)
            {
                Controller = ctrl.GetComponent<ControllerView3D>();
                if (Controller == null) Controller = ctrl.AddComponent<ControllerView3D>();
                EnsureColliders(ctrl);
                Controller.Build();
            }
            else Report.Add(SceneNames.Controller + ": MISSING");
            Resolve(SceneNames.Mannequin);
            Resolve(SceneNames.Table);
            if (thermalAnchor == null)
            {
                var a = GameObject.Find(SceneNames.ThermalAnchor);
                if (a != null) thermalAnchor = a.transform;
            }
        }

        /// <summary>CAD object if present (placeholder then disabled), otherwise the placeholder.</summary>
        private GameObject Resolve(string role)
        {
            Transform cad = transform.Find(role), ph = transform.Find(role + SceneNames.PlaceholderSuffix);
            if (cad != null)
            {
                if (ph != null) ph.gameObject.SetActive(false);
                Report.Add(role + ": CAD");
                return cad.gameObject;
            }
            if (ph != null)
            {
                Report.Add(role + ": PLACEHOLDER");
                return ph.gameObject;
            }
            return null;
        }

        private static Transform FindDeep(Transform root, string name)
        {
            foreach (var t in root.GetComponentsInChildren<Transform>(true)) if (t.name == name) return t;
            return null;
        }

        private static void EnsureColliders(GameObject go)
        {
            foreach (var r in go.GetComponentsInChildren<MeshRenderer>(true))
            {
                if (r.gameObject.name.StartsWith("__") || r.GetComponent<Collider>() != null) continue;
                var mf = r.GetComponent<MeshFilter>();
                if (mf != null && mf.sharedMesh != null) r.gameObject.AddComponent<MeshCollider>().sharedMesh = mf.sharedMesh;
            }
        }

        /// <summary>Optional CAD file StreamingAssets/cad/exploded_offsets.csv (object, dx_m, dy_m, dz_m).</summary>
        private static Dictionary<string, Vector3> LoadExplodedOffsets()
        {
            var path = Path.Combine(Application.streamingAssetsPath, "cad", "exploded_offsets.csv");
            if (!File.Exists(path)) return null;
            var d = new Dictionary<string, Vector3>();
            try
            {
                var rows = Csv.Parse(File.ReadAllText(path));
                for (int i = 1; i < rows.Count; i++)
                {
                    var r = rows[i];
                    if (r.Count < 4) continue;
                    d[r[0]] = new Vector3(float.Parse(r[1], CultureInfo.InvariantCulture), float.Parse(r[2], CultureInfo.InvariantCulture), float.Parse(r[3], CultureInfo.InvariantCulture));
                }
            }
            catch (System.Exception ex) { Debug.LogWarning("[NERAM] exploded_offsets.csv ignored: " + ex.Message); return null; }
            return d;
        }

        public void ShowFrame(ReplaySession s, int frame, bool snap)
        {
            for (int i = 0; i < 4; i++)
            {
                if (Modules[i] == null) continue;
                var cv = ChannelRules.Compute(s, frame, i + 1);
                Modules[i].Show(cv, snap);
                if (Connectors[i] != null)
                    Connectors[i].localPosition = _connectorBase[i] + (cv.Connected ? Vector3.zero : Connectors[i].parent.InverseTransformDirection(Vector3.down) * 0.035f);
            }
            if (Controller != null) Controller.Show(s, frame);
        }

        public void Clear()
        {
            for (int i = 0; i < 4; i++)
            {
                if (Modules[i] != null) Modules[i].Show(new ChannelView { Channel = i + 1, Heat = 0, Connected = true }, true);
                if (Connectors[i] != null) Connectors[i].localPosition = _connectorBase[i];
            }
        }
    }
}
