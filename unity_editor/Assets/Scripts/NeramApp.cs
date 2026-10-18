using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using Neram.Core;
using UnityEngine;
using UnityEngine.UIElements;

namespace Neram.Unity
{
    /// <summary>
    /// Composition root of the replay-driven digital-twin dashboard. Wires the loader, the single replay clock and every
    /// view; nothing here computes model, controller or physiology values (the canonical model and controller run
    /// outside Unity and arrive as replay files). Device glow, charts, pipeline and animations all follow the replay frame.
    ///
    /// Robust start-up (v3): if the scene's UIDocument has no PanelSettings or no UXML, both are loaded from
    /// Resources/NERAM (PanelSettings, UI/NeramMain) and the UXML is cloned explicitly when the document is still empty, with
    /// an error in the Console telling you to re-run setup. Camera and 3D selection input live in NeramInputController and
    /// keep working even if the dashboard cannot be built.
    ///
    /// Frame pipeline: the clock raises FrameChanged (possibly several times per Unity frame at x60); NeramApp records only
    /// the latest frame and renders once in LateUpdate (render coalescing). Text-heavy panels refresh at most
    /// <see cref="textRefreshHz"/> while playing; on any jump (seek, step, event navigation, pause) everything refreshes
    /// immediately so all views always show the same replay frame.
    ///
    /// Keyboard (Inspect mode): Space play/pause · Left/Right step · Shift+Left/Right previous/next event · Home restart ·
    /// 1-5 speed x1/x2/x4/x10/x60 · T transition · F fault · S safety · C camera preset · R Free Roam · P presentation ·
    /// B badges · D diagnostics · M menu · N monitor screen · F11 fullscreen · Esc close/deselect. In Free Roam only movement keys and Esc
    /// are active.
    ///
    /// Layout (final release): the panel is laid out on a 1600 x 900 reference that scales with the screen height, so the
    /// logical height is always 900 and the logical width follows the aspect ratio. Breakpoint classes on the root
    /// (bp-compact below 1500 logical px, bp-narrow below 1300) reflow the side panels instead of shrinking text. Secondary
    /// panels open from the collapsible sidebar (#sidebar), one drawer at a time. Display options never touch the clock.
    ///
    /// Screens (v4): THEATRE (default: the operating theatre and patient; every statistic, graph and panel hidden),
    /// MONITOR (an opaque in-app monitoring screen in large type, opened from the header tab, the N key, or by clicking the
    /// 3D bedside patient monitor) and FULL ANALYSIS (the full dashboard). Every panel has its own "×" button; HIDE ALL
    /// PANELS / SHOW PANELS / RESET LAYOUT and the Panels drawer act on the current screen (ScreenPanels). Switching screens
    /// or hiding panels never changes the replay time, scenario, speed or camera.
    /// </summary>
    [DefaultExecutionOrder(100)]
    public sealed class NeramApp : MonoBehaviour
    {
        public const string PanelSettingsResource = "NERAM/NeramPanelSettings";
        public const string UxmlResource = "NERAM/UI/NeramMain";

        public UIDocument document;
        public ReplayLoader loader;
        public ReplayClock clock;
        public CameraRig cameraRig;
        public NeramAssemblyBinder assembly;
        public NeramInputController inputController;
        public VisualModeController visualModes;
        [Tooltip("Screen anchor of the wrist wearable (Wearable_Screen_Anchor).")]
        public Transform wearableAnchor;
        [Tooltip("Maximum refresh rate of text panels while playing (render coalescing). Display setting only.")]
        [Range(2, 60)] public float textRefreshHz = 15f;

        private VisualElement _root;
        private ThermalPanel _thermal;
        private ForecastFan _forecast;
        private ControllerStatePanel _banner;
        private SafetyOverlay _safety;
        private DisclaimerBanner _footer;
        private TelemetryPanel _telemetry;
        private EventLogPanel _events;
        private ParametersPanel _params;
        private DiagnosticsPanel _diagnostics;
        private TransportBar _transport;
        private ScenarioSelector _scenarios;
        private DataErrorScreen _error;
        private LoadingOverlay _loading;
        private ModuleInspector _inspector;
        private WorldLabels _labels;
        private HeaderStatus _header;
        private OverviewPanel _overview;
        private ChartsPanel _charts;
        private RegionDetailPanel _detail;
        private WearableScreen _wearable;
        private PipelinePanel _pipeline;
        private ThermalLegendElement _thermalBar;
        private ScreenPanels _panels;
        private VisualElement _drawerPanels;
        private WorldLabelMode _labelMode = WorldLabelMode.Compact;

        private readonly List<IReplayView> _fastViews = new List<IReplayView>();
        private readonly List<IReplayView> _textViews = new List<IReplayView>();
        private readonly Dictionary<RegionId, NeramRegion> _regions = new Dictionary<RegionId, NeramRegion>();
        private readonly List<IvDripAnimator> _drips = new List<IvDripAnimator>();
        private Label _scenarioTitle, _scenarioId, _placeholderMark, _hoverTip, _freeRoamHint, _presetLabel, _thermalValue, _explodedTitle;
        private VisualElement _scenarioChips, _stage, _modeLegend, _internalLegend, _thermalLegend, _explodedLegend, _expControls, _drawerEvents, _drawerFields;
        private Button _btnBadges, _btnPresentation, _btnInspect, _btnRoam, _btnFullscreen, _btnDetails, _badgesToggle;
        private VisualElement _sidebar, _drawerSources, _drawerSettings;
        private readonly Dictionary<string, Button> _nav = new Dictionary<string, Button>();
        private readonly Dictionary<string, Button> _settings = new Dictionary<string, Button>();
        private Label _displayInfo;
        private bool _detailsUserSet, _autoDetails = true;
        private string _breakpoint = "";
        private int _windowedW, _windowedH;
        private readonly Dictionary<VisualMode, Button> _modeButtons = new Dictionary<VisualMode, Button>();
        private readonly Button[] _expButtons = new Button[4];

        private ReplaySession _session;
        private int _pendingFrame = -1;
        private bool _pendingJump;
        private int _shownFrame = -1;
        private float _lastTextRefresh;
        private int _textFrame = -1;
        private int _presetIndex = -1;
        private float _frameMs;
        private Label _toast;
        private float _toastUntil;
        private float _loadStart;
        private string _loadingFile = "";
        private RegionId _selected = RegionId.None;
        private bool _built;
        private VisualElement _tree;

        // ------------------------------------------------------------------ start-up

        private void Awake()
        {
            if (document == null) document = GetComponent<UIDocument>();
            if (loader == null) loader = GetComponent<ReplayLoader>();
            if (clock == null) clock = GetComponent<ReplayClock>();
            if (cameraRig == null) cameraRig = FindAnyObjectByType<CameraRig>();
            if (assembly == null) assembly = FindAnyObjectByType<NeramAssemblyBinder>();
            if (wearableAnchor == null)
            {
                var a = GameObject.Find("Wearable_Screen_Anchor");
                if (a != null) wearableAnchor = a.transform;
            }
            // Camera + selection input is independent of the dashboard (added at runtime for scenes from older setups).
            if (inputController == null) inputController = FindAnyObjectByType<NeramInputController>();
            if (inputController == null && cameraRig != null)
            {
                inputController = cameraRig.gameObject.AddComponent<NeramInputController>();
                inputController.rig = cameraRig;
                Debug.LogWarning("[NERAM] Scene has no NeramInputController (older setup): added one for this session. Re-run NERAM > 1. Run full setup.");
            }
            if (inputController != null && inputController.document == null) inputController.document = document;
            if (visualModes == null) visualModes = FindAnyObjectByType<VisualModeController>();
            _drips.AddRange(FindObjectsByType<IvDripAnimator>(FindObjectsInactive.Exclude, FindObjectsSortMode.None));
            if (document != null && document.panelSettings == null)
            {
                var ps = Resources.Load<PanelSettings>(PanelSettingsResource);
                if (ps != null)
                {
                    document.panelSettings = ps;
                    Debug.LogError("[NERAM] The scene's UIDocument has no PanelSettings (scene generated by an older or failed setup). " +
                                   "Using Resources/" + PanelSettingsResource + " for this session. Fix permanently: NERAM > 1. Run full setup.");
                }
                else Debug.LogError("[NERAM] UIDocument has no PanelSettings and Resources/" + PanelSettingsResource + " is missing: the dashboard cannot be shown.");
            }
        }

        /// <summary>Returns the dashboard's "root" element, repairing a scene whose UIDocument has no UXML or an empty tree.</summary>
        private VisualElement EnsureDashboardTree()
        {
            if (document.visualTreeAsset == null)
            {
                var vta = Resources.Load<VisualTreeAsset>(UxmlResource);
                if (vta == null) { Debug.LogError("[NERAM] Resources/" + UxmlResource + ".uxml is missing: the dashboard cannot be shown."); return null; }
                document.visualTreeAsset = vta;
                Debug.LogError("[NERAM] The scene's UIDocument has no UXML; using Resources/" + UxmlResource + " for this session. Re-run NERAM > 1. Run full setup.");
            }
            var top = document.rootVisualElement;
            if (top == null) { Debug.LogError("[NERAM] UIDocument has no root visual element (PanelSettings missing?)."); return null; }
            var ui = top.Q<VisualElement>("root");
            if (ui == null)
            {
                document.visualTreeAsset.CloneTree(top);
                ui = top.Q<VisualElement>("root");
                Debug.LogWarning("[NERAM] UIDocument tree was empty at start-up; the dashboard UXML was cloned explicitly.");
            }
            if (ui == null) Debug.LogError("[NERAM] The dashboard UXML has no element named 'root': wrong UXML assigned to the UIDocument.");
            return ui;
        }

        private void Start()
        {
            // CameraRig.Start (earlier execution order) has applied preset 0; the theatre opens on the theatre framing
            TheatreFraming(true);
            if (_presetLabel != null) _presetLabel.text = "Theatre view";
        }

        /// <summary>
        /// Default THEATRE framing (chosen by projecting the scene's key points with the view toolbar at the top and the
        /// replay bar at the bottom): the patient with the four warming devices and the wrist wearable, the ceiling-boom
        /// patient monitor, the wall display, the ventilator, the bedside controller and the O2 cylinders inside the frame. Reset View returns
        /// here; C cycles the scene's camera presets. Camera only (no replay state).
        /// </summary>
        private void TheatreFraming(bool instant)
        {
            if (cameraRig == null) return;
            cameraRig.Set(new Vector3(0.6f, 0.6f, 0.6f), -26f, 12f, 3.6f, instant);
        }

        private void OnEnable()
        {
            if (document == null || loader == null || clock == null)
            {
                Debug.LogError("[NERAM] NeramApp needs UIDocument, ReplayLoader and ReplayClock. Run NERAM > 1. Run full setup.");
                enabled = false;
                return;
            }
            if (!_built)
            {
                var ui = EnsureDashboardTree();
                if (ui == null) { enabled = false; return; }
                _root = ui;
                try
                {
                    BuildUi();
                    _built = true;
                }
                catch (Exception ex)
                {
                    Debug.LogError("[NERAM] UI setup failed: " + ex.Message + "\n" + ex.StackTrace);
                    var l = new Label("NERAM UI setup error:\n" + ex.Message + "\nRun NERAM > 4. Validate project (camera and 3D selection still work).");
                    l.style.color = new Color(0.98f, 0.75f, 0.2f);
                    l.style.fontSize = 18;
                    l.style.position = Position.Absolute;
                    l.style.left = 20;
                    l.style.top = 70;
                    _root.Add(l);
                    enabled = false;
                    return;
                }
            }
            loader.CatalogChanged += OnCatalog;
            loader.LoadStarted += OnLoadStarted;
            loader.SessionLoaded += OnSessionLoaded;
            loader.LoadFailed += OnLoadFailed;
            loader.LoadCancelled += OnLoadCancelled;
            clock.FrameChanged += OnFrame;
            clock.StateChanged += OnClockState;
            if (inputController != null)
            {
                inputController.Picked += OnPicked;
                inputController.HoverChanged += OnHover;
                inputController.FreeRoamChanged += OnFreeRoam;
            }
            if (visualModes != null) visualModes.ModeChanged += OnModeChanged;
        }

        private void OnDisable()
        {
            if (loader != null)
            {
                loader.CatalogChanged -= OnCatalog;
                loader.LoadStarted -= OnLoadStarted;
                loader.SessionLoaded -= OnSessionLoaded;
                loader.LoadFailed -= OnLoadFailed;
                loader.LoadCancelled -= OnLoadCancelled;
            }
            if (clock != null)
            {
                clock.FrameChanged -= OnFrame;
                clock.StateChanged -= OnClockState;
            }
            if (inputController != null)
            {
                inputController.Picked -= OnPicked;
                inputController.HoverChanged -= OnHover;
                inputController.FreeRoamChanged -= OnFreeRoam;
            }
            if (visualModes != null) visualModes.ModeChanged -= OnModeChanged;
        }

        // ------------------------------------------------------------------ UI construction

        private void BuildUi()
        {
            var r = _root;
            _tree = r;
            r.AddToClassList("neram-root");

            _thermal = new ThermalPanel(r);
            _forecast = new ForecastFan(r);
            _banner = new ControllerStatePanel(r);
            _safety = new SafetyOverlay(r);
            _footer = new DisclaimerBanner(r);
            _telemetry = new TelemetryPanel(r);
            _events = new EventLogPanel(r, f => clock.SeekFrame(f));
            _params = new ParametersPanel(r);
            _diagnostics = new DiagnosticsPanel(r, loader);
            _transport = new TransportBar(r, clock);
            _scenarios = new ScenarioSelector(r, l => { _scenarios.Close(); loader.Load(l); }, () => loader.RefreshCatalog());
            _error = new DataErrorScreen(r, () => { _error.Hide(); _scenarios.Toggle(); });
            _loading = new LoadingOverlay(r, () => loader.Cancel());
            if (assembly != null) assembly.EnsureBound(); // binder Awake may not have run yet (script order)
            _inspector = new ModuleInspector(r, assembly, cameraRig);
            _header = new HeaderStatus(r, clock);
            _overview = new OverviewPanel(r);
            _charts = new ChartsPanel(r);
            _detail = new RegionDetailPanel(r);
            _pipeline = new PipelinePanel(r);

            _thermal.PointInspected += f => { _events.Inspect(f); ShowDrawer(_drawerEvents, true); };
            _overview.ChannelClicked += ch => SetRegion(NeramRegion.ForChannel(ch), false);
            _charts.SeekRequested += t => clock.SeekTime(t);
            _detail.FocusRequested += FocusSelected;
            _detail.ExplodeRequested += () => { int ch = NeramRegion.ChannelOf(_selected); if (ch > 0) SetMode(VisualMode.Exploded, ch); };
            _detail.InspectorRequested += () => { int ch = NeramRegion.ChannelOf(_selected); if (ch > 0) _inspector.Select(ch, Math.Max(0, _shownFrame)); };
            _detail.RegionRequested += reg => SetRegion(reg, true);

            // Fast views: cheap, update every rendered frame. Text views: throttled while playing.
            _fastViews.Add(_thermal);
            _fastViews.Add(_banner);
            _fastViews.Add(_safety);
            _fastViews.Add(_transport);
            _fastViews.Add(_forecast);
            _fastViews.Add(_charts);
            _fastViews.Add(_header);
            _fastViews.Add(_pipeline);
            _textViews.Add(_telemetry);
            _textViews.Add(_events);
            _textViews.Add(_inspector);
            _textViews.Add(_diagnostics);
            _textViews.Add(_footer);
            _textViews.Add(_params);
            _textViews.Add(_overview);
            _textViews.Add(_detail);

            UiUtil.Req<VisualElement>(r, "viewport");
            _stage = UiUtil.Req<VisualElement>(r, "stage");
            _hoverTip = UiUtil.Req<Label>(r, "hover-tip");
            _freeRoamHint = UiUtil.Req<Label>(r, "freeroam-hint");
            var cam = cameraRig != null ? cameraRig.cam : Camera.main;
            _wearable = new WearableScreen(r, cam, wearableAnchor);
            _textViews.Add(_wearable);
            _detail.WearableModeRequested += m => _wearable.SetMode(m);
            _labels = new WorldLabels(UiUtil.Req<VisualElement>(r, "world-layer"), cam, assembly);
            // channel chips report 1..4; the controller chip reports 0 (found in Unity: it cleared the selection instead)
            _labels.ChipClicked += ch => SetRegion(ch == 0 ? RegionId.Controller : NeramRegion.ForChannel(ch), false);
            SetupMonitorProps(r);
            foreach (var reg in FindObjectsByType<NeramRegion>(FindObjectsInactive.Exclude, FindObjectsSortMode.None))
                if (reg.region != RegionId.None && reg.region != RegionId.Monitor) _regions[reg.region] = reg;
            _diagnostics.AssemblyReport = assembly != null ? assembly.Report : null;
            _diagnostics.PerformanceText = () => string.Format(CultureInfo.InvariantCulture,
                "frame {0:0.0} ms · text panels ≤ {1:0} Hz while playing · {2} selectable regions · input: {3} · view mode: {4}",
                _frameMs, textRefreshHz, _regions.Count, inputController != null ? "polled (Input System)" : "MISSING",
                visualModes != null ? visualModes.Mode.ToString() : "n/a");
            if (_regions.Count == 0) Debug.LogWarning("[NERAM] No NeramRegion components in the scene: 3D selection is unavailable. Run NERAM > 1. Run full setup.");

            // header + drawers
            _scenarioTitle = UiUtil.Req<Label>(r, "scenario-title");
            _scenarioId = UiUtil.Req<Label>(r, "scenario-id");
            _scenarioChips = UiUtil.Req<VisualElement>(r, "scenario-chips");
            _placeholderMark = UiUtil.Req<Label>(r, "placeholder-mark");
            _drawerEvents = UiUtil.Req<VisualElement>(r, "drawer-events");
            _drawerFields = UiUtil.Req<VisualElement>(r, "drawer-fields");
            _drawerSources = UiUtil.Req<VisualElement>(r, "drawer-sources");
            _drawerSettings = UiUtil.Req<VisualElement>(r, "drawer-settings");
            _drawerPanels = UiUtil.Req<VisualElement>(r, "drawer-panels");
            _sidebar = UiUtil.Req<VisualElement>(r, "sidebar");
            UiUtil.Req<Button>(r, "btn-menu").clicked += ToggleSidebar;
            UiUtil.Req<Button>(r, "sidebar-close").clicked += () => SetSidebar(false);
            Nav(r, "btn-scenarios", () => { bool open = !_scenarios.IsOpen; CloseDrawers(null); if (open) _scenarios.Toggle(); });
            Nav(r, "btn-events", () => ToggleDrawer(_drawerEvents));
            Nav(r, "btn-fields", () => ToggleDrawer(_drawerFields));
            Nav(r, "btn-params", () => { bool open = !_params.IsOpen; CloseDrawers(null); if (open) _params.Toggle(); });
            Nav(r, "btn-diagnostics", ToggleDiagnostics);
            Nav(r, "btn-badges", () => ToggleDrawer(_drawerSources));
            Nav(r, "btn-settings", () => { ToggleDrawer(_drawerSettings); RefreshDisplayInfo(); });
            Nav(r, "btn-panels-drawer", () => ToggleDrawer(_drawerPanels));
            _btnBadges = _nav["btn-badges"];
            _btnPresentation = UiUtil.Req<Button>(r, "btn-presentation");
            _btnPresentation.clicked += TogglePresentation;
            UiUtil.Req<Button>(r, "events-close").clicked += () => ShowDrawer(_drawerEvents, false);
            UiUtil.Req<Button>(r, "fields-close").clicked += () => ShowDrawer(_drawerFields, false);
            UiUtil.Req<Button>(r, "sources-close").clicked += () => ShowDrawer(_drawerSources, false);
            UiUtil.Req<Button>(r, "settings-close").clicked += () => ShowDrawer(_drawerSettings, false);
            UiUtil.Req<Button>(r, "panels-close").clicked += () => ShowDrawer(_drawerPanels, false);
            _badgesToggle = UiUtil.Req<Button>(r, "badges-toggle");
            _badgesToggle.clicked += ToggleBadges;
            UiUtil.Req<Button>(r, "btn-capture").clicked += Capture;
            UiUtil.Req<Button>(r, "btn-capture-side").clicked += () => { SetSidebar(false); Capture(); };
            _btnFullscreen = UiUtil.Req<Button>(r, "btn-fullscreen");
            _btnFullscreen.clicked += ToggleFullscreen;
            UiUtil.Req<Label>(r, "brand-sub").text = "Perioperative Thermal Digital Twin · replay viewer v" + NeramVersion.Value;

            // settings drawer (display options only)
            Setting(r, "set-labels-off", () => SetLabelMode(WorldLabelMode.Off));
            Setting(r, "set-labels-compact", () => SetLabelMode(WorldLabelMode.Compact));
            Setting(r, "set-labels-detailed", () => SetLabelMode(WorldLabelMode.Detailed));
            Setting(r, "set-details", () => { _detailsUserSet = true; SetDetails(!DetailsOpen); });
            Setting(r, "set-autodetails", () => { _autoDetails = !_autoDetails; SyncSettings(); });
            Setting(r, "set-pipeline", () => _panels.Set(ScreenLayout.Pipeline, !_panels.IsVisible(ScreenLayout.Pipeline)));
            Setting(r, "set-charts-tall", () => { _root.ToggleInClassList("charts-tall"); SyncSettings(); });
            Setting(r, "set-presentation", TogglePresentation);
            Setting(r, "set-fullscreen", ToggleFullscreen);
            _displayInfo = UiUtil.Req<Label>(r, "set-display-info");
            _btnDetails = UiUtil.Req<Button>(r, "btn-details");
            _btnDetails.clicked += () => { _detailsUserSet = true; SetDetails(!DetailsOpen); };
            UiUtil.Req<Button>(r, "dp-collapse").clicked += () => { _detailsUserSet = true; SetDetails(false); };
            r.RegisterCallback<GeometryChangedEvent>(_ => ApplyBreakpoint());

            // camera toolbar
            _btnInspect = UiUtil.Req<Button>(r, "cam-inspect");
            _btnRoam = UiUtil.Req<Button>(r, "cam-freeroam");
            _presetLabel = UiUtil.Req<Label>(r, "cam-preset-label");
            _btnInspect.clicked += () => { if (cameraRig != null) cameraRig.SetFreeRoam(false); };
            _btnRoam.clicked += () => { if (cameraRig != null) cameraRig.SetFreeRoam(true); };
            UiUtil.Req<Button>(r, "btn-camera").clicked += NextCameraPreset;
            UiUtil.Req<Button>(r, "cam-reset").clicked += () => { if (cameraRig != null && cameraRig.FreeRoam) cameraRig.SetFreeRoam(false); TheatreFraming(false); _presetIndex = -1; _presetLabel.text = "Theatre view"; };

            // visualisation modes
            _modeLegend = UiUtil.Req<VisualElement>(r, "mode-legend");
            _internalLegend = UiUtil.Req<VisualElement>(r, "internal-legend");
            _thermalLegend = UiUtil.Req<VisualElement>(r, "thermal-mode-legend");
            _explodedLegend = UiUtil.Req<VisualElement>(r, "exploded-legend");
            _explodedTitle = UiUtil.Req<Label>(r, "exploded-title");
            _thermalValue = UiUtil.Req<Label>(r, "thermal-legend-value");
            _thermalBar = new ThermalLegendElement();
            UiUtil.Req<VisualElement>(r, "thermal-legend-bar").Add(_thermalBar);
            _expControls = UiUtil.Req<VisualElement>(r, "exp-controls");
            foreach (var (mode, name) in new[] { (VisualMode.External, "view-external"), (VisualMode.Internal, "view-internal"), (VisualMode.Thermal, "view-thermal"), (VisualMode.Exploded, "view-exploded") })
            {
                var b = UiUtil.Req<Button>(r, name);
                var m = mode;
                b.clicked += () => SetMode(m, m == VisualMode.Exploded ? DefaultExplodeChannel() : 0);
                _modeButtons[mode] = b;
            }
            _expButtons[0] = UiUtil.Req<Button>(r, "exp-ch1");
            _expButtons[1] = UiUtil.Req<Button>(r, "exp-ch2");
            _expButtons[2] = UiUtil.Req<Button>(r, "exp-ch3");
            _expButtons[3] = UiUtil.Req<Button>(r, "exp-ch4");
            for (int i = 0; i < 4; i++)
            {
                int ch = i + 1;
                _expButtons[i].clicked += () => SetMode(VisualMode.Exploded, ch);
            }
            UiUtil.Req<Button>(r, "exp-reset").clicked += () => SetMode(VisualMode.External);
            if (visualModes == null) foreach (var b in _modeButtons.Values) b.SetEnabled(false);
            _presetLabel.text = "Theatre view";

            _toast = UiUtil.Label("", "toast", "hidden");
            _toast.pickingMode = PickingMode.Ignore;
            r.Add(_toast);
            BuildPanels(r);
            SetLabelMode(WorldLabelMode.Compact);
            _panels.SetMode(ScreenMode.Theatre); // v4: the audience first sees the theatre and the patient
            SyncSettings();

            // Buttons are operated by pointer only; keyboard shortcuts are polled in Update (no double "submit").
            r.Query<Button>().ForEach(b => b.focusable = false);
        }

        /// <summary>
        /// Registers every hideable panel with its "×" button (ScreenPanels) and wires the screen tabs, the Panels drawer
        /// and the global HIDE ALL PANELS / SHOW PANELS / RESET LAYOUT buttons. Display only.
        /// </summary>
        private void BuildPanels(VisualElement r)
        {
            _panels = new ScreenPanels(r);
            _panels.Register(ScreenLayout.Controller, UiUtil.Req<VisualElement>(r, "banner-head"), UiUtil.Req<VisualElement>(r, "controller-banner"));
            _panels.Register(ScreenLayout.Temp, UiUtil.Req<VisualElement>(r, "ov-head-temp"), UiUtil.Req<VisualElement>(r, "ov-card-temp"));
            _panels.Register(ScreenLayout.Twin, UiUtil.Req<VisualElement>(r, "ov-head-twin"), UiUtil.Req<VisualElement>(r, "ov-card-twin"));
            _panels.Register(ScreenLayout.ControllerInfo, UiUtil.Req<VisualElement>(r, "sec-ctrl-head"), UiUtil.Req<VisualElement>(r, "sec-ctrl"));
            _panels.Register(ScreenLayout.Channels, UiUtil.Req<VisualElement>(r, "sec-ch-head"), UiUtil.Req<VisualElement>(r, "sec-ch"));
            _panels.Register(ScreenLayout.Quality, UiUtil.Req<VisualElement>(r, "sec-quality-head"), UiUtil.Req<VisualElement>(r, "sec-quality"));
            _panels.Register(ScreenLayout.Unavailable, UiUtil.Req<VisualElement>(r, "sec-na-head"), UiUtil.Req<VisualElement>(r, "sec-na"));
            _panels.Register(ScreenLayout.Pipeline, UiUtil.Req<VisualElement>(r, "pipeline-head"), UiUtil.Req<VisualElement>(r, "pipeline-strip"));
            _panels.Register(ScreenLayout.Details, null, UiUtil.Req<VisualElement>(r, "detail-panel")); // its own "×" is dp-collapse
            _panels.Register(ScreenLayout.Forecast, UiUtil.Req<VisualElement>(r, "forecast-head"), UiUtil.Req<VisualElement>(r, "forecast-panel"));
            _panels.Register(ScreenLayout.ChartA, UiUtil.Req<VisualElement>(r, "chart-a-head"), UiUtil.Req<VisualElement>(r, "chart-a-panel"));
            _panels.Register(ScreenLayout.ChartB, UiUtil.Req<VisualElement>(r, "thermal-head"), UiUtil.Req<VisualElement>(r, "thermal-panel"));
            _panels.Register(ScreenLayout.ChartC, UiUtil.Req<VisualElement>(r, "chart-c-head"), UiUtil.Req<VisualElement>(r, "chart-c-panel"));
            var legendHide = _panels.HideButton(ScreenLayout.Legend);
            legendHide.AddToClassList("hide-float");
            _modeLegend.Add(legendHide);
            _panels.Register(ScreenLayout.Legend, null, _modeLegend);
            _panels.Register(ScreenLayout.Safety, UiUtil.Req<VisualElement>(r, "safety-banner"), UiUtil.Req<VisualElement>(r, "safety-banner"));
            _panels.Register(ScreenLayout.FaultStrip, UiUtil.Req<VisualElement>(r, "channel-fault-strip"), UiUtil.Req<VisualElement>(r, "channel-fault-strip"));
            _panels.Register(ScreenLayout.Labels, null);
            _panels.Hook(ScreenLayout.Labels, vis => { if (_labels != null) _labels.Mode = vis ? _labelMode : WorldLabelMode.Off; });
            _panels.Hook(ScreenLayout.Details, vis =>
            {
                if (_btnDetails == null) return;
                _btnDetails.text = vis ? "Details ▸" : "◂ Details";
                _btnDetails.EnableInClassList("selected", vis);
            });
            _safety.BannerVisible = () => _panels.IsVisible(ScreenLayout.Safety);
            _panels.PanelsButton.clicked += () => ToggleDrawer(_drawerPanels);
            _panels.Changed += OnScreenChanged;
        }

        /// <summary>After a screen or visibility change: leave Free Roam for the monitor (the 3D view is covered), sync buttons.</summary>
        private void OnScreenChanged()
        {
            if (_panels.Mode == ScreenMode.Monitor)
            {
                if (cameraRig != null && cameraRig.FreeRoam) cameraRig.SetFreeRoam(false);
                UiUtil.Show(_hoverTip, false);
            }
            float textScale = _panels.Mode == ScreenMode.Monitor ? 1.3f : 1f; // graph labels follow the monitor's larger type
            _charts.SetTextScale(textScale);
            _thermal.SetTextScale(textScale);
            if (_session != null && _shownFrame >= 0) _safety.ShowFrame(_shownFrame); // re-evaluate the safety-banner space
            SyncSettings();
        }

        private bool DetailsOpen => _panels != null && _panels.IsVisible(ScreenLayout.Details);

        // ------------------------------------------------------------------ clickable 3D screens (open MONITOR pages)

        private sealed class MonitorProp
        {
            public NeramRegion Region;
            public Renderer Anchor;
            public Button Chip;
            public MonitorPage Page;
            public string Name;
        }

        private readonly List<MonitorProp> _monitorProps = new List<MonitorProp>();

        /// <summary>
        /// Makes three generated theatre screens clickable (RegionId.Monitor, mesh colliders added at runtime so scenes
        /// from earlier setups work unchanged), each opening one MONITOR page: the ceiling-boom patient monitor -> VALUES,
        /// the large head-wall display -> TEMPERATURE GRAPHS, the ventilator display -> PIPELINE · FORECAST (the CHANNEL GRAPH
        /// page opens from the monitor's page buttons). A small chip is drawn
        /// over each screen in the theatre. The screens themselves stay labelled demonstration props (no data of their own).
        /// </summary>
        private void SetupMonitorProps(VisualElement r)
        {
            var layer = UiUtil.Req<VisualElement>(r, "world-layer");
            int insertAt = r.IndexOf(layer) + 1;
            foreach (var (node, page, name, chipText) in new[]
                     {
                         ("OT_Patient_Monitor", MonitorPage.Values, "PATIENT MONITOR", "MONITOR · VALUES ▸"),
                         ("Wall_Display_Frame", MonitorPage.Graphs, "WALL DISPLAY", "TEMPERATURE GRAPHS ▸"),
                         ("OT_Ventilator", MonitorPage.Flow, "VENTILATOR SCREEN", "PIPELINE · FORECAST ▸"),
                     })
            {
                var go = GameObject.Find(node);
                if (go == null) { Debug.LogWarning("[NERAM] " + node + " not found: its screen cannot open the MONITOR " + ScreenLayout.PageTitle(page) + " page (the MONITOR tab still works)."); continue; }
                AddPickBoxes(go);
                var reg = go.GetComponent<NeramRegion>();
                if (reg == null) reg = go.AddComponent<NeramRegion>();
                reg.region = RegionId.Monitor;
                reg.channel = 0;
                reg.Collect();
                Renderer anchor = null;
                foreach (var rend in go.GetComponentsInChildren<Renderer>(true))
                    if (rend.gameObject.name.Contains("Screen") || rend.gameObject.name.Contains("Display") || rend.gameObject.name == "Monitor_Body") { anchor = rend; break; }
                if (anchor == null) anchor = go.GetComponentInChildren<Renderer>();
                var p = new MonitorProp { Region = reg, Anchor = anchor, Page = page, Name = name };
                var pg = page;
                p.Chip = UiUtil.Button(chipText, () => _panels.SetPage(pg), "monitor-chip", "ui-block", "hidden");
                p.Chip.name = "monitor-chip-" + page.ToString().ToLowerInvariant();
                p.Chip.tooltip = "Open the MONITOR screen on its " + ScreenLayout.PageTitle(page) + " page. Same replay, same time.";
                p.Chip.focusable = false;
                r.Insert(insertAt++, p.Chip);
                _monitorProps.Add(p);
            }
        }

        /// <summary>
        /// Click targets for a theatre prop: one box per renderer, built from the renderer's world bounds. Mesh colliders
        /// are not used here: in a player build the static theatre props are static-batched (their MeshFilter then holds the
        /// combined world-space mesh), so a runtime MeshCollider ends up misplaced. Verified: the 3D monitor opened its page
        /// in the Editor but not in the built player with mesh colliders. Boxes are children of the prop, so the picker's
        /// GetComponentInParent finds the prop's NeramRegion.
        /// </summary>
        private static void AddPickBoxes(GameObject prop)
        {
            foreach (var rend in prop.GetComponentsInChildren<Renderer>(true))
            {
                if (rend.gameObject.name.StartsWith("__")) continue;
                var b = rend.bounds;
                if (b.size.x <= 0f && b.size.y <= 0f && b.size.z <= 0f) continue;
                var go = new GameObject("__pick_" + rend.gameObject.name);
                go.transform.SetParent(prop.transform, true);
                go.transform.SetPositionAndRotation(b.center, Quaternion.identity);
                var s = go.transform.lossyScale;
                var box = go.AddComponent<BoxCollider>();
                box.center = Vector3.zero;
                box.size = new Vector3(SafeDiv(b.size.x, s.x), SafeDiv(b.size.y, s.y), SafeDiv(b.size.z, s.z));
            }
        }

        private static float SafeDiv(float a, float b) => Mathf.Abs(b) > 1e-6f ? a / Mathf.Abs(b) : a;

        private MonitorProp PropOf(NeramRegion reg)
        {
            foreach (var p in _monitorProps) if (p.Region == reg) return p;
            return null;
        }

        private void UpdateMonitorChips()
        {
            var cam = cameraRig != null ? cameraRig.cam : Camera.main;
            // chips only in THEATRE (in FULL ANALYSIS the screens stay clickable, without chips over the dashboard)
            bool allowed = cam != null && _panels.Mode == ScreenMode.Theatre && (cameraRig == null || !cameraRig.FreeRoam) &&
                           Screen.width > 0 && Screen.height > 0;
            foreach (var p in _monitorProps)
            {
                bool show = allowed && p.Anchor != null && p.Chip.panel != null;
                Vector3 sp = Vector3.zero;
                if (show)
                {
                    var b = p.Anchor.bounds;
                    // small screens: chip just above the screen; the large wall display: chip on the screen itself
                    sp = cam.WorldToScreenPoint(p.Page == MonitorPage.Graphs ? b.center : b.center + Vector3.up * (b.extents.y + 0.04f));
                    show = sp.z > 0 && sp.x > 0 && sp.x < Screen.width && sp.y > 0 && sp.y < Screen.height;
                }
                UiUtil.Show(p.Chip, show);
                if (!show) continue;
                var rb = p.Chip.panel.visualTree.worldBound;
                p.Chip.style.left = sp.x / Screen.width * rb.width;
                p.Chip.style.top = (Screen.height - sp.y) / Screen.height * rb.height;
            }
        }

        private void ShowDrawer(VisualElement drawer, bool open) => UiUtil.Show(drawer, open);

        /// <summary>Open one drawer (closing every other one) or close it if it is already open.</summary>
        private void ToggleDrawer(VisualElement drawer)
        {
            bool open = !UiUtil.IsShown(drawer);
            CloseDrawers(null);
            ShowDrawer(drawer, open);
        }

        private void CloseDrawers(object except)
        {
            if (except != _scenarios) _scenarios.Close();
            if (except != _params) _params.Close();
            if (except != _diagnostics) _diagnostics.Close();
            ShowDrawer(_drawerEvents, false);
            ShowDrawer(_drawerFields, false);
            ShowDrawer(_drawerSources, false);
            ShowDrawer(_drawerSettings, false);
            ShowDrawer(_drawerPanels, false);
        }

        private bool AnyDrawerOpen => _scenarios.IsOpen || _params.IsOpen || _diagnostics.IsOpen || UiUtil.IsShown(_drawerEvents) ||
                                      UiUtil.IsShown(_drawerFields) || UiUtil.IsShown(_drawerSources) || UiUtil.IsShown(_drawerSettings) ||
                                      UiUtil.IsShown(_drawerPanels);

        private void Nav(VisualElement r, string name, Action onClick)
        {
            var b = UiUtil.Req<Button>(r, name);
            b.clicked += onClick;
            _nav[name] = b;
        }

        private void Setting(VisualElement r, string name, Action onClick)
        {
            var b = UiUtil.Req<Button>(r, name);
            b.clicked += onClick;
            _settings[name] = b;
        }

        // ------------------------------------------------------------------ sidebar, details panel, breakpoints, fullscreen

        private bool SidebarOpen => _sidebar != null && UiUtil.IsShown(_sidebar);

        private void ToggleSidebar() => SetSidebar(!SidebarOpen);

        private void SetSidebar(bool open)
        {
            UiUtil.Show(_sidebar, open);
            _root.EnableInClassList("sidebar-open", open);
            if (!open) CloseDrawers(null);
        }

        /// <summary>Highlight the sidebar entry whose drawer is open (cheap; called every LateUpdate).</summary>
        private void SyncNav()
        {
            if (_nav.Count == 0) return;
            _nav["btn-scenarios"].EnableInClassList("selected", _scenarios.IsOpen);
            _nav["btn-events"].EnableInClassList("selected", UiUtil.IsShown(_drawerEvents));
            _nav["btn-fields"].EnableInClassList("selected", UiUtil.IsShown(_drawerFields));
            _nav["btn-params"].EnableInClassList("selected", _params.IsOpen);
            _nav["btn-diagnostics"].EnableInClassList("selected", _diagnostics.IsOpen);
            _nav["btn-badges"].EnableInClassList("selected", UiUtil.IsShown(_drawerSources));
            _nav["btn-settings"].EnableInClassList("selected", UiUtil.IsShown(_drawerSettings));
            _nav["btn-panels-drawer"].EnableInClassList("selected", UiUtil.IsShown(_drawerPanels));
            _panels.PanelsButton.EnableInClassList("selected", UiUtil.IsShown(_drawerPanels));
        }

        /// <summary>Show or hide the selected-region panel on the current screen (ScreenPanels applies classes and the
        /// toolbar button text).</summary>
        private void SetDetails(bool open)
        {
            if (_panels != null) _panels.Set(ScreenLayout.Details, open);
        }

        private void SetLabelMode(WorldLabelMode mode)
        {
            _labelMode = mode;
            if (_panels != null && mode != WorldLabelMode.Off && !_panels.IsVisible(ScreenLayout.Labels)) _panels.Set(ScreenLayout.Labels, true);
            else if (_labels != null) _labels.Mode = _panels == null || _panels.IsVisible(ScreenLayout.Labels) ? mode : WorldLabelMode.Off;
            SyncSettings();
        }

        private void SyncSettings()
        {
            if (_settings.Count == 0 || _panels == null) return;
            var lm = _panels.IsVisible(ScreenLayout.Labels) ? _labelMode : WorldLabelMode.Off;
            _settings["set-labels-off"].EnableInClassList("selected", lm == WorldLabelMode.Off);
            _settings["set-labels-compact"].EnableInClassList("selected", lm == WorldLabelMode.Compact);
            _settings["set-labels-detailed"].EnableInClassList("selected", lm == WorldLabelMode.Detailed);
            _settings["set-details"].EnableInClassList("selected", DetailsOpen);
            _settings["set-autodetails"].EnableInClassList("selected", _autoDetails);
            _settings["set-pipeline"].EnableInClassList("selected", _panels.IsVisible(ScreenLayout.Pipeline));
            _settings["set-charts-tall"].EnableInClassList("selected", _root.ClassListContains("charts-tall"));
            _settings["set-presentation"].EnableInClassList("selected", _root.ClassListContains("presentation"));
            _settings["set-fullscreen"].EnableInClassList("selected", IsFullscreen);
        }

        /// <summary>
        /// Responsive reflow from the resolved logical width (height is always 900 on the 1600 x 900 reference):
        /// wide (>= 1500): both side columns; compact (&lt; 1500): the region panel becomes an overlay on the stage and starts
        /// collapsed; narrow (&lt; 1300): narrower left column and table.
        /// </summary>
        private void ApplyBreakpoint()
        {
            if (_root == null) return;
            float w = _root.resolvedStyle.width;
            if (float.IsNaN(w) || w <= 0) return;
            // short layout: windows wider than about 2:1 (e.g. a wide, short Editor Game view) keep the logical width at
            // 1600 with a logical height below 800 (PanelSettings Shrink), so the tallest panels get a little less height
            _root.EnableInClassList("bp-short", LayoutRules.IsShort(_root.resolvedStyle.height));
            var b = LayoutRules.Breakpoint(w);
            string bp = b == LayoutBreakpoint.Narrow ? "narrow" : b == LayoutBreakpoint.Compact ? "compact" : "wide";
            if (bp == _breakpoint) return;
            _breakpoint = bp;
            _root.EnableInClassList("bp-compact", bp != "wide");
            _root.EnableInClassList("bp-narrow", bp == "narrow");
            if (!_detailsUserSet && _panels != null) _panels.Set(ScreenMode.Analysis, ScreenLayout.Details, bp == "wide");
            RefreshDisplayInfo();
        }

        private void RefreshDisplayInfo()
        {
            if (_displayInfo == null || _root == null) return;
            var w = _root.resolvedStyle.width;
            var h = _root.resolvedStyle.height;
            UiUtil.SetText(_displayInfo, string.Format(CultureInfo.InvariantCulture,
                "Screen {0} × {1} px · dashboard {2:0} × {3:0} logical px (1600 × 900 reference, shrink-to-fit) · layout: {4}{5}",
                Screen.width, Screen.height, w, h, string.IsNullOrEmpty(_breakpoint) ? "wide" : _breakpoint,
                Application.isEditor ? " · running in the Unity Editor" : ""));
        }

        private static bool IsFullscreen => !Application.isEditor && Screen.fullScreenMode != FullScreenMode.Windowed && Screen.fullScreenMode != FullScreenMode.MaximizedWindow;

        /// <summary>
        /// Standalone player: switch between a borderless fullscreen window at the display's native resolution and the
        /// previous window size. The replay clock, scenario, selection and camera are untouched (only the window changes).
        /// In the Unity Editor the Game view cannot be made fullscreen from a script; a toast explains the Editor equivalent.
        /// </summary>
        private void ToggleFullscreen()
        {
            if (Application.isEditor)
            {
                Toast("Fullscreen applies to the standalone app (NERAM > 6. Build Windows player). In the Editor: hover the Game view and press Shift+Space, or enable 'Play Maximized'.", 6f);
                return;
            }
            if (!IsFullscreen)
            {
                _windowedW = Screen.width;
                _windowedH = Screen.height;
                var d = Display.main;
                int w = d != null && d.systemWidth > 0 ? d.systemWidth : Screen.currentResolution.width;
                int h = d != null && d.systemHeight > 0 ? d.systemHeight : Screen.currentResolution.height;
                Screen.SetResolution(w, h, FullScreenMode.FullScreenWindow);
            }
            else
            {
                // back to the normal maximised desktop window the app starts in (taskbar stays visible)
                Screen.fullScreenMode = FullScreenMode.MaximizedWindow;
            }
        }

        private void SyncFullscreenButton()
        {
            if (_btnFullscreen == null) return;
            bool fs = IsFullscreen;
            UiUtil.SetText(_btnFullscreen, fs ? "EXIT FULLSCREEN" : "FULLSCREEN");
            _btnFullscreen.EnableInClassList("selected", fs);
        }

        private void ToggleDiagnostics()
        {
            CloseDrawers(_diagnostics);
            _diagnostics.ShowFrame(clock.Frame);
            _diagnostics.Toggle();
        }

        private void ToggleBadges()
        {
            SourceBadge.Expanded = !SourceBadge.Expanded;
            _badgesToggle.text = SourceBadge.Expanded ? "Badge detail: full meaning" : "Badge detail: compact";
            _badgesToggle.EnableInClassList("selected", SourceBadge.Expanded);
        }

        /// <summary>Presentation: hides the region panel, pipeline note and secondary rows; keeps the patient, the principal
        /// values (temperature, twin, controller, CH1-CH4), the three charts, transport and disclaimer. The sidebar still works.</summary>
        private void TogglePresentation()
        {
            bool on = !_root.ClassListContains("presentation");
            _root.EnableInClassList("presentation", on);
            _btnPresentation.EnableInClassList("selected", on);
            SyncSettings();
        }

        // ------------------------------------------------------------------ visualisation modes

        private int DefaultExplodeChannel()
        {
            int ch = NeramRegion.ChannelOf(_selected);
            return ch > 0 ? ch : 3;
        }

        private void SetMode(VisualMode mode, int channel = 0)
        {
            if (visualModes == null) { Toast("Visualisation modes unavailable: re-run NERAM > 1. Run full setup."); return; }
            visualModes.SetMode(mode, channel);
            if (mode == VisualMode.Exploded && assembly != null && cameraRig != null)
            {
                var m = assembly.Modules[visualModes.ExplodedChannel - 1];
                if (m != null) cameraRig.Focus(m.transform.position, visualModes.ExplodedChannel <= 2 ? 0.85f : 1.0f); // wider than v3-pre: the in-Unity test showed the layers filling the stage
                SetRegion(NeramRegion.ForChannel(visualModes.ExplodedChannel), false);
            }
            OnModeChanged(visualModes.Mode);
        }

        private void OnModeChanged(VisualMode mode)
        {
            if (!_built) return;
            foreach (var kv in _modeButtons) kv.Value.EnableInClassList("selected", kv.Key == mode);
            UiUtil.Show(_expControls, mode == VisualMode.Exploded);
            _expControls.parent?.EnableInClassList("exp-on", mode == VisualMode.Exploded); // compact toolbar so CH1-4 + Assemble do not collide with the camera group
            for (int i = 0; i < 4; i++) _expButtons[i].EnableInClassList("selected", visualModes != null && visualModes.ExplodedChannel == i + 1);
            UiUtil.Show(_modeLegend, mode != VisualMode.External);
            UiUtil.Show(_internalLegend, mode == VisualMode.Internal);
            UiUtil.Show(_thermalLegend, mode == VisualMode.Thermal);
            UiUtil.Show(_explodedLegend, mode == VisualMode.Exploded);
            if (mode == VisualMode.Exploded && visualModes != null && visualModes.ExplodedChannel > 0)
                _explodedTitle.text = "EXPLODED VIEW · " + NeramRegion.Title(NeramRegion.ForChannel(visualModes.ExplodedChannel));
        }

        // ------------------------------------------------------------------ loader events

        private void OnCatalog(List<ScenarioListing> list) => _scenarios.Render(list);

        private void OnLoadStarted(ScenarioListing listing)
        {
            _error.Hide();
            UnbindAll();
            _loadStart = Time.realtimeSinceStartup;
            _loadingFile = Path.GetFileName(listing.FilePath ?? "");
            _loading.Show(listing.Id + "\n" + Path.GetFileName(listing.FilePath ?? ""));
        }

        private void OnSessionLoaded(ReplaySession s)
        {
            _loading.Hide();
            _session = s;
            foreach (var v in _fastViews) v.Bind(s);
            foreach (var v in _textViews) v.Bind(s);
            _labels.Bind(s);
            _scenarios.SetCurrent(s.Header.ScenarioId);
            _scenarios.Render(loader.Scenarios);
            UpdateTopBar(s);
            _pendingFrame = -1;
            _shownFrame = -1;
            _textFrame = -1;
            clock.Attach(s.Table); // raises FrameChanged(0, jump) -> first render in LateUpdate
        }

        private void OnLoadFailed(ScenarioListing listing, ReplayParseResult result, string message)
        {
            _loading.Hide();
            UnbindAll();
            _error.Show(listing, result, message);
            UpdateTopBar(null);
        }

        private void OnLoadCancelled()
        {
            _loading.Hide();
            UpdateTopBar(null);
        }

        private void UnbindAll()
        {
            clock.Detach();
            if (_session == null) return;
            foreach (var v in _fastViews) v.Unbind();
            foreach (var v in _textViews) v.Unbind();
            _labels.Unbind();
            if (assembly != null) assembly.Clear();
            _session = null;
            _pendingFrame = -1;
        }

        private void UpdateTopBar(ReplaySession s)
        {
            _scenarioChips.Clear();
            if (s == null)
            {
                _scenarioTitle.text = "No scenario loaded";
                _scenarioId.text = "";
                UiUtil.Show(_placeholderMark, false);
                return;
            }
            var h = s.Header;
            _scenarioTitle.text = h.Title;
            _scenarioId.text = h.ScenarioId;
            _scenarioChips.Add(UiUtil.Chip(h.Cohort ?? "?", h.IsSynthetic ? "chip-placeholder" : "chip-info"));
            if (h.Placeholder) { var pc = UiUtil.Chip("PLACEHOLDER", "chip-warn"); pc.tooltip = "Placeholder replay: scripted stand-in data, not an output of the NERAM twin or controller"; _scenarioChips.Add(pc); }
            if (s.Faults != null && s.Faults.IsPlaceholder) { var fc = UiUtil.Chip("FAULT TEXT TBD", "chip-warn"); fc.tooltip = "hardware/interfaces/fault_codes.csv not delivered yet: fault display text is a built-in placeholder"; _scenarioChips.Add(fc); }
            int warnings = 0;
            foreach (var i in s.Report.Issues) if (i.Severity == IssueSeverity.Warning) warnings++;
            if (warnings > 0) _scenarioChips.Add(UiUtil.Chip(warnings + " validation warning" + (warnings == 1 ? "" : "s"), "chip-warn"));
            // the placeholder fault-table warning already has its own chip (FAULT TEXT TBD); count only the others here
            int cfgWarn = 0;
            foreach (var w in loader.ConfigWarnings) if (!(s.Faults != null && s.Faults.IsPlaceholder && w.StartsWith("Fault-code display texts are PLACEHOLDERS"))) cfgWarn++;
            if (cfgWarn > 0) _scenarioChips.Add(UiUtil.Chip(cfgWarn + " config warning" + (cfgWarn == 1 ? "" : "s"), "chip-warn"));
            // The header row can clip the last chip at 1600 logical px; the tooltip always lists every chip in full.
            var chipTexts = new List<string>();
            foreach (var c in _scenarioChips.Children()) if (c is Label l) chipTexts.Add(l.text);
            _scenarioChips.tooltip = string.Join(" · ", chipTexts) + " (details: ☰ MENU → Diagnostics)";
            UiUtil.Show(_placeholderMark, h.Placeholder);
        }

        // ------------------------------------------------------------------ frame pipeline

        private void OnFrame(int frame, bool jump)
        {
            _pendingFrame = frame;
            _pendingJump |= jump;
        }

        private void OnClockState()
        {
            // Pausing forces a full refresh so text panels match the frozen frame exactly.
            if (clock.Model != null && !clock.Model.Playing) _pendingJump = true;
            if (_pendingFrame < 0 && _shownFrame >= 0) _pendingFrame = _shownFrame;
        }

        private void LateUpdate()
        {
            if (!_built) return;
            _frameMs = Mathf.Lerp(_frameMs, Time.unscaledDeltaTime * 1000f, 0.05f);
            PruneDuplicateTrees();
            if (_session != null && _pendingFrame >= 0)
            {
                int frame = _pendingFrame;
                bool jump = _pendingJump;
                _pendingFrame = -1;
                _pendingJump = false;
                foreach (var v in _fastViews) v.ShowFrame(frame);
                _labels.ShowFrame(frame);
                if (assembly != null) assembly.ShowFrame(_session, frame, jump);
                _shownFrame = frame;
                bool playing = clock.Model != null && clock.Model.Playing;
                if (jump || !playing || Time.unscaledTime - _lastTextRefresh >= 1f / textRefreshHz) RefreshText(frame);
                UpdatePatientSignal(frame);
            }
            else if (_session != null && _textFrame != _shownFrame && _shownFrame >= 0 && Time.unscaledTime - _lastTextRefresh >= 1f / textRefreshHz)
            {
                RefreshText(_shownFrame); // catch up after throttling
            }
            // replay-time-driven animations (frozen while paused or without a replay)
            double rt = clock.Model != null ? clock.Model.Time : double.NaN;
            if (visualModes != null) visualModes.SetReplayTime(rt);
            foreach (var d in _drips) if (d != null) d.SetReplayTime(rt);
            if (_session != null) _labels.UpdatePositions();
            if (_wearable != null) _wearable.UpdatePosition();
            UpdateMonitorChips();
            UpdateStage();
            if (_hoverTip != null && UiUtil.IsShown(_hoverTip) && inputController != null)
            {
                var p = inputController.PointerPanelPosition;
                _hoverTip.style.left = p.x + 14;
                _hoverTip.style.top = p.y + 12;
            }
            if (loader.IsLoading)
                _loading.Progress(_loadingFile, loader.LinesParsed, Time.realtimeSinceStartup - _loadStart);
            if (_toastUntil > 0 && Time.unscaledTime > _toastUntil) { UiUtil.Show(_toast, false); _toastUntil = 0; }
            SyncNav();
            SyncFullscreenButton();
        }

        private void UpdatePatientSignal(int frame)
        {
            double obs = _session.Table.Get(_session.F.TObs, frame);
            if (_session.Table.GetBool(_session.F.ObsMissing, frame)) obs = double.NaN;
            if (visualModes != null) visualModes.SetPatientSignal(obs);
            _thermalBar.SetValue(obs);
            UiUtil.SetText(_thermalValue, double.IsNaN(obs) ? "no observation at this frame (grey)" : Fmt.Value(obs, _session.F.TObs) + " · " + _session.Tag("obs", frame));
        }

        /// <summary>If the UIDocument also cloned its UXML after our explicit clone, remove the second, unused tree.</summary>
        private void PruneDuplicateTrees()
        {
            var top = document != null ? document.rootVisualElement : null;
            if (top == null || _tree == null) return;
            if (_tree.panel == null)
            {
                // UIDocument rebuilt its UI (e.g. UXML live reload): our tree is detached. Stop instead of deleting the new tree.
                Debug.LogError("[NERAM] Dashboard tree was detached (UIDocument rebuilt its UI). Exit and re-enter Play mode.");
                _built = false;
                return;
            }
            if (top.childCount <= 1) return;
            for (int i = top.childCount - 1; i >= 0; i--)
            {
                var c = top[i];
                // remove only true duplicates of the dashboard (a second clone that also contains an element named "root")
                if (c != _tree && !IsAncestor(c, _tree) && c.Q<VisualElement>("root") != null) top.RemoveAt(i);
            }
        }

        private static bool IsAncestor(VisualElement a, VisualElement b)
        {
            for (var p = b; p != null; p = p.parent) if (p == a) return true;
            return false;
        }

        /// <summary>Tell the camera rig where the free stage area (between the dashboard panels) is on screen.</summary>
        private void UpdateStage()
        {
            if (cameraRig == null || _stage == null || _stage.panel == null) return;
            if (_panels != null && _panels.Mode == ScreenMode.Monitor) return; // the 3D view is covered: keep its composition
            var rb = _stage.panel.visualTree.worldBound;
            var wb = _stage.worldBound;
            if (rb.width <= 0 || rb.height <= 0 || float.IsNaN(wb.width)) { cameraRig.ClearStage(); return; }
            float sx = Screen.width / rb.width, sy = Screen.height / rb.height;
            cameraRig.SetStage(new Rect(wb.xMin * sx, Screen.height - wb.yMax * sy, wb.width * sx, wb.height * sy));
        }

        private void RefreshText(int frame)
        {
            foreach (var v in _textViews) v.ShowFrame(frame);
            _lastTextRefresh = Time.unscaledTime;
            _textFrame = frame;
        }

        // ------------------------------------------------------------------ selection + camera

        private void OnPicked(NeramRegion reg)
        {
            if (reg != null && reg.region == RegionId.Monitor) // a theatre screen -> its MONITOR page
            {
                var prop = PropOf(reg);
                _panels.SetPage(prop != null ? prop.Page : MonitorPage.Values);
                return;
            }
            SetRegion(reg != null ? reg.region : RegionId.None, false);
        }

        private void OnHover(NeramRegion reg)
        {
            if (!_built) return;
            bool on = reg != null;
            UiUtil.Show(_hoverTip, on);
            if (!on) return;
            var prop = reg.region == RegionId.Monitor ? PropOf(reg) : null;
            _hoverTip.text = prop != null
                ? prop.Name + "  ·  click to open MONITOR · " + ScreenLayout.PageTitle(prop.Page)
                : NeramRegion.Title(reg.region) + (reg.region == _selected ? "" : "  ·  click to select");
        }

        private void OnFreeRoam(bool on)
        {
            if (!_built) return;
            _btnRoam.EnableInClassList("selected", on);
            _btnInspect.EnableInClassList("selected", !on);
            UiUtil.Show(_freeRoamHint, on);
            UiUtil.Show(_hoverTip, false);
            _presetLabel.text = on ? "free roam" : "manual";
        }

        private void SetRegion(RegionId region, bool focus)
        {
            if (_regions.TryGetValue(_selected, out var old) && old != null) old.SetSelected(false);
            _selected = region;
            if (_regions.TryGetValue(region, out var now) && now != null) now.SetSelected(true);
            int ch = NeramRegion.ChannelOf(region);
            _labels.SetSelected(region == RegionId.Controller ? 0 : ch > 0 ? ch : -1);
            _overview.SetSelectedChannel(ch);
            if (ch == 0 && _inspector.Selected >= 0) _inspector.Select(-1, 0);
            _detail.Select(region);
            _detail.ShowFrame(Math.Max(0, _shownFrame));
            // a click on the patient is an explicit request: the region panel opens (also in THEATRE), never on the monitor
            if (region != RegionId.None && _autoDetails && !DetailsOpen && _panels.Mode != ScreenMode.Monitor) SetDetails(true);
            if (focus) FocusSelected();
        }

        private void FocusSelected()
        {
            if (cameraRig == null || !_regions.TryGetValue(_selected, out var reg) || reg == null) return;
            cameraRig.Focus(reg.Center, Mathf.Clamp(reg.Radius * 3.2f, 0.4f, 2.2f));
        }

        private void NextCameraPreset()
        {
            if (cameraRig == null || cameraRig.Presets.Count == 0) return;
            _presetIndex = (_presetIndex + 1) % cameraRig.Presets.Count;
            var p = cameraRig.Presets[_presetIndex];
            cameraRig.GoTo(p);
            _presetLabel.text = p.label;
            Toast("Camera: " + p.label, 1.6f);
        }

        private void Toast(string text, float seconds = 3f)
        {
            if (_toast == null) return;
            _toast.text = text;
            UiUtil.Show(_toast, true);
            _toastUntil = Time.unscaledTime + seconds;
        }

        // ------------------------------------------------------------------ keyboard (polled)

        private void Update()
        {
            if (!_built || _root == null) return;
            if (cameraRig != null && cameraRig.FreeRoam) return; // WASD/Space/Ctrl/Shift belong to Free Roam
            if (inputController != null && inputController.RoamExitFrame == Time.frameCount) return;
            bool shift = NeramInput.ShiftHeld;
            if (NeramInput.Pressed(KeyCode.Space)) clock.TogglePlay();
            if (NeramInput.Pressed(KeyCode.LeftArrow)) { if (shift) _transport.Jump(EventCategory.All, false); else clock.StepBack(); }
            if (NeramInput.Pressed(KeyCode.RightArrow)) { if (shift) _transport.Jump(EventCategory.All, true); else clock.StepForward(); }
            if (NeramInput.Pressed(KeyCode.Home)) clock.Restart();
            if (NeramInput.Pressed(KeyCode.Alpha1) || NeramInput.Pressed(KeyCode.Keypad1)) clock.SetSpeed(1);
            if (NeramInput.Pressed(KeyCode.Alpha2) || NeramInput.Pressed(KeyCode.Keypad2)) clock.SetSpeed(2);
            if (NeramInput.Pressed(KeyCode.Alpha3) || NeramInput.Pressed(KeyCode.Keypad3)) clock.SetSpeed(4);
            if (NeramInput.Pressed(KeyCode.Alpha4) || NeramInput.Pressed(KeyCode.Keypad4)) clock.SetSpeed(10);
            if (NeramInput.Pressed(KeyCode.Alpha5) || NeramInput.Pressed(KeyCode.Keypad5)) clock.SetSpeed(60);
            if (NeramInput.Pressed(KeyCode.T)) _transport.Jump(EventCategory.Transition, !shift);
            if (NeramInput.Pressed(KeyCode.F)) _transport.Jump(EventCategory.Fault, !shift);
            if (NeramInput.Pressed(KeyCode.S)) _transport.Jump(EventCategory.Safety, !shift);
            bool monitor = _panels.Mode == ScreenMode.Monitor;
            if (NeramInput.Pressed(KeyCode.C) && !monitor) NextCameraPreset();
            if (NeramInput.Pressed(KeyCode.R) && cameraRig != null && !monitor) cameraRig.SetFreeRoam(true);
            if (NeramInput.Pressed(KeyCode.N)) _panels.ToggleMonitor();
            if (NeramInput.Pressed(KeyCode.P)) TogglePresentation();
            if (NeramInput.Pressed(KeyCode.B)) ToggleBadges();
            if (NeramInput.Pressed(KeyCode.D)) ToggleDiagnostics();
            if (NeramInput.Pressed(KeyCode.M)) ToggleSidebar();
            if (NeramInput.Pressed(KeyCode.F11)) ToggleFullscreen();
            if (NeramInput.Pressed(KeyCode.Escape)) Escape();
        }

        /// <summary>Esc closes one layer at a time: drawer, sidebar, monitor, inspector, view mode, selection, presentation.</summary>
        private void Escape()
        {
            if (AnyDrawerOpen) { CloseDrawers(null); return; }
            if (SidebarOpen) { SetSidebar(false); return; }
            if (_panels.Mode == ScreenMode.Monitor) { _panels.CloseMonitor(); return; }
            if (_inspector.Selected >= 0) { _inspector.Select(-1, 0); return; }
            if (visualModes != null && visualModes.Mode != VisualMode.External) { SetMode(VisualMode.External); return; }
            if (_selected != RegionId.None) { SetRegion(RegionId.None, false); return; }
            if (_root.ClassListContains("presentation")) TogglePresentation();
        }

        // ------------------------------------------------------------------ capture

        /// <summary>
        /// Saves a PNG of the full screen (3D + UI, including disclaimer footer and source badges) to
        /// persistentDataPath/captures. Only validated SYNTHETIC/DEVELOPMENT replays can be on screen, so captures can
        /// never show final-holdout data.
        /// </summary>
        private void Capture()
        {
            var dir = Path.Combine(Application.persistentDataPath, "captures");
            Directory.CreateDirectory(dir);
            string id = _session != null ? _session.Header.ScenarioId : "no_replay";
            string t = _session != null && _shownFrame >= 0 ? ((int)_session.Table.T[_shownFrame]).ToString(CultureInfo.InvariantCulture) + "s" : "0s";
            var path = Path.Combine(dir, "NERAM_" + id + "_" + t + "_" + DateTime.UtcNow.ToString("yyyyMMdd_HHmmss", CultureInfo.InvariantCulture) + ".png");
            ScreenCapture.CaptureScreenshot(path);
            Toast("Capture saved: " + path, 4f);
            Debug.Log("[NERAM] Capture saved: " + path);
        }
    }
}
