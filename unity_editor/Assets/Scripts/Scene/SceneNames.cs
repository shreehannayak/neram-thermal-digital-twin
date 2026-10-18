namespace Neram.Unity
{
    /// <summary>
    /// Object names shared with the CAD specification (plan section 2W). Placeholders use the same names with the
    /// suffix "_PLACEHOLDER" on the top-level object only; their children use the exact CAD part names, so the binder
    /// code is identical for placeholder and CAD geometry.
    /// </summary>
    public static class SceneNames
    {
        public const string Assembly = "NERAM_Assembly";
        public const string PlaceholderSuffix = "_PLACEHOLDER";
        public const string Anchors = "NERAM_Anchors";
        public const string ThermalAnchor = "ThermalStateAnchor";
        public const string CameraPresets = "CameraPresets";

        public const string ReferenceCube = "Reference_Cube_1m";
        public const string Table = "OR_Table";
        public const string Mannequin = "Patient_Mannequin";
        public const string Controller = "Bedside_Controller";
        public const string CableHub = "Cable_Hub";

        public static readonly string[] Modules = { "Left_Hand_Module", "Right_Hand_Module", "Left_Foot_Module", "Right_Foot_Module" };

        public static string Cable(int ch) => "Cable_CH" + ch;
        public static string Connector(int ch) => "Connector_CH" + ch;
        public static string Part(int ch, string part) => "CH" + ch + "_" + part;

        /// <summary>Module part suffixes from the CAD hierarchy (CHn_ prefix). Straps are CHn_Strap_1..n.</summary>
        public static readonly string[] ModuleParts = { "Liner", "Sensor_A", "Sensor_B", "Heater", "Cutoff", "Insulation", "Shell", "Strain_Relief" };
        public const string StrapPrefix = "Strap_";

        public static readonly string[] ControllerParts =
        {
            "BC_Enclosure", "BC_Front_Panel", "BC_Display", "BC_LED_CH1", "BC_LED_CH2", "BC_LED_CH3", "BC_LED_CH4",
            "BC_Button_Start", "BC_Button_Stop", "BC_Button_Reset", "BC_Port_CH1", "BC_Port_CH2", "BC_Port_CH3", "BC_Port_CH4",
            "BC_Mains_Inlet", "BC_Rail_Clamp",
        };

        public static readonly string[] Materials =
        {
            "MAT_Liner", "MAT_Sensor", "MAT_Heater", "MAT_Insulation", "MAT_Shell", "MAT_Strap", "MAT_Cable", "MAT_Connector",
            "MAT_Enclosure", "MAT_Indicator",
        };
    }
}
