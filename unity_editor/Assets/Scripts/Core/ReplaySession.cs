using System.Collections.Generic;

namespace Neram.Core
{
    /// <summary>Resolved field handles for fast, allocation-free access from views.</summary>
    public sealed class FrameFields
    {
        public readonly FieldDef T = ReplayFields.Get("meta", "t_s");
        public readonly FieldDef TObs = ReplayFields.Get("obs", "T_obs");
        public readonly FieldDef ObsMissing = ReplayFields.Get("obs", "obs_missing");
        public readonly FieldDef TEst = ReplayFields.Get("twin", "T_est");
        public readonly FieldDef TEstSd = ReplayFields.Get("twin", "T_est_sd");
        public readonly FieldDef TwinValid = ReplayFields.Get("twin", "Twin_Valid");
        public readonly FieldDef PLevelShift = ReplayFields.Get("twin", "P_level_shift");
        public readonly FieldDef POutlier = ReplayFields.Get("twin", "P_outlier");
        public readonly FieldDef[] PredMean = new FieldDef[3];
        public readonly FieldDef[] L80 = new FieldDef[3];
        public readonly FieldDef[] U80 = new FieldDef[3];
        public readonly FieldDef[] L95 = new FieldDef[3];
        public readonly FieldDef[] U95 = new FieldDef[3];
        public readonly FieldDef[] PBelow = new FieldDef[3];
        public readonly FieldDef State = ReplayFields.Get("ctrl", "Controller_State");
        public readonly FieldDef Substate = ReplayFields.Get("ctrl", "Degraded_Substate");
        public readonly FieldDef[] Heat = new FieldDef[4];
        public readonly FieldDef Demand = ReplayFields.Get("ctrl", "Demand_Global");
        public readonly FieldDef Reason = ReplayFields.Get("ctrl", "Trigger_Reason");
        public readonly FieldDef Alert = ReplayFields.Get("ctrl", "Alert");
        public readonly FieldDef SafetyShutdown = ReplayFields.Get("ctrl", "Safety_Shutdown");
        public readonly FieldDef FaultLatched = ReplayFields.Get("ctrl", "Fault_Latched");
        public readonly FieldDef FaultCode = ReplayFields.Get("ctrl", "fault_code");
        public readonly FieldDef[] ChannelFault = new FieldDef[4];
        public readonly FieldDef ClinicianMode = ReplayFields.Get("ctrl", "Clinician_Mode");
        public readonly FieldDef DataStaleTwin = ReplayFields.Get("ctrl", "Data_Stale_Twin");
        public readonly FieldDef DataStaleHw = ReplayFields.Get("ctrl", "Data_Stale_HW");
        public readonly FieldDef[] TempA = new FieldDef[4];
        public readonly FieldDef[] TempB = new FieldDef[4];
        public readonly FieldDef[] Connected = new FieldDef[4];
        public readonly FieldDef[] Current = new FieldDef[4];
        public readonly FieldDef[] Cutoff = new FieldDef[4];
        public readonly FieldDef TPlant = ReplayFields.Get("plant", "T_plant");
        public readonly FieldDef DTHeat = ReplayFields.Get("plant", "dT_heat");
        public readonly FieldDef PlantMode = ReplayFields.Get("plant", "plant_mode");
        public readonly Dictionary<string, FieldDef> Src = new Dictionary<string, FieldDef>();

        public FrameFields()
        {
            for (int h = 0; h < 3; h++)
            {
                var hz = ReplayFields.Horizons[h];
                PredMean[h] = ReplayFields.Get("twin", "T_pred_" + hz);
                L80[h] = ReplayFields.Get("twin", "L80_" + hz);
                U80[h] = ReplayFields.Get("twin", "U80_" + hz);
                L95[h] = ReplayFields.Get("twin", "L95_" + hz);
                U95[h] = ReplayFields.Get("twin", "U95_" + hz);
                PBelow[h] = ReplayFields.Get("twin", "P_below_hypo_" + hz);
            }
            for (int i = 0; i < 4; i++)
            {
                var c = (i + 1).ToString();
                Heat[i] = ReplayFields.Get("ctrl", "Heat_" + c);
                ChannelFault[i] = ReplayFields.Get("ctrl", "Channel_Fault_" + c);
                TempA[i] = ReplayFields.Get("hw", "Module_Temp_" + c + "_A");
                TempB[i] = ReplayFields.Get("hw", "Module_Temp_" + c + "_B");
                Connected[i] = ReplayFields.Get("hw", "Module_Connected_" + c);
                Current[i] = ReplayFields.Get("hw", "Heater_Current_" + c);
                Cutoff[i] = ReplayFields.Get("hw", "HW_Cutoff_" + c);
            }
            foreach (var g in new[] { "obs", "twin", "ctrl", "hw", "plant" }) Src[g] = ReplayFields.Get("src", g);
        }
    }

    /// <summary>Everything a loaded, validated replay needs for display. Immutable after construction.</summary>
    public sealed class ReplaySession
    {
        public readonly ReplayHeader Header;
        public readonly ReplayTable Table;
        public readonly EventIndex Events;
        public readonly EnumRegistry Enums;
        public readonly ParamsRegistry Params;
        public readonly FaultCodeTable Faults;
        public readonly DisplayConfig Display;
        public readonly ValidationReport Report;
        public readonly string SourcePath;
        public readonly FrameFields F = new FrameFields();

        /// <summary>Resolved integer values of FROZEN enum names (integers are PROVISIONAL in enums.json).</summary>
        public readonly int StNormal, StPredictive, StActive, StMaintenance, StClinician, StDegraded, StShutdown;
        public readonly int TvNoData, TvInitialising, TvValid, TvDegraded;
        public readonly int SubNone, SubMonitor, SubClinicianFixed;
        public readonly int AlertResetBlocked;

        public ReplaySession(ReplayHeader header, ReplayTable table, ValidationReport report, EnumRegistry enums,
            ParamsRegistry prms, FaultCodeTable faults, DisplayConfig display, string sourcePath)
        {
            Header = header; Table = table; Report = report; Enums = enums; Params = prms; Faults = faults; Display = display; SourcePath = sourcePath;
            StNormal = enums.ValueOf(EnumNames.ControllerState, "NORMAL");
            StPredictive = enums.ValueOf(EnumNames.ControllerState, "PREDICTIVE_WARMING");
            StActive = enums.ValueOf(EnumNames.ControllerState, "ACTIVE_WARMING");
            StMaintenance = enums.ValueOf(EnumNames.ControllerState, "TARGET_MAINTENANCE");
            StClinician = enums.ValueOf(EnumNames.ControllerState, "CLINICIAN_WARMING");
            StDegraded = enums.ValueOf(EnumNames.ControllerState, "TWIN_DEGRADED");
            StShutdown = enums.ValueOf(EnumNames.ControllerState, "SAFETY_SHUTDOWN");
            TvNoData = enums.ValueOf(EnumNames.TwinValid, "NO_DATA");
            TvInitialising = enums.ValueOf(EnumNames.TwinValid, "INITIALISING");
            TvValid = enums.ValueOf(EnumNames.TwinValid, "VALID");
            TvDegraded = enums.ValueOf(EnumNames.TwinValid, "DEGRADED");
            SubNone = enums.ValueOf(EnumNames.DegradedSubstate, "NONE");
            SubMonitor = enums.ValueOf(EnumNames.DegradedSubstate, "MONITOR");
            SubClinicianFixed = enums.ValueOf(EnumNames.DegradedSubstate, "CLINICIAN_FIXED");
            AlertResetBlocked = enums.ValueOf(EnumNames.AlertCode, "RESET_BLOCKED");
            if (header.ParamsUsed != null) prms.OverlayHeaderSnapshot(header.ParamsUsed, header.ScenarioId);
            Events = EventIndex.Build(table, enums, faults, display);
        }

        public ParamEntry THypo => Params.GetOrNull("t_hypo_degC");
        public ParamEntry TTarget => Params.GetOrNull("t_target_degC");

        public string Tag(string group, int frame) => Table.GetString(F.Src[group], frame);

        public bool AnyHeat(int frame)
        {
            for (int i = 0; i < 4; i++) if (Table.Get(F.Heat[i], frame) > 0) return true;
            return false;
        }
    }
}
