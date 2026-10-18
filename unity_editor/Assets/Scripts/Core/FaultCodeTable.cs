using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text;

namespace Neram.Core
{
    public sealed class FaultCodeEntry
    {
        public int Code;
        public string Name;
        public string Scope;
        public string DetectedBy;
        public string Description;
        public string DisplayText;
        /// <summary>Channel 1-4 for channel codes (100*i + k), 0 for system codes.</summary>
        public int Channel;
    }

    /// <summary>
    /// Fault codes from Shreehan's hardware/interfaces/fault_codes.csv
    /// (columns: code,name,scope,detected_by,description,display_text).
    /// Until that file exists, a placeholder built from the plan (section 3W) is used and the UI says so.
    /// </summary>
    public sealed class FaultCodeTable
    {
        private readonly Dictionary<int, FaultCodeEntry> _byCode = new Dictionary<int, FaultCodeEntry>();
        public string Origin { get; private set; }
        public bool IsPlaceholder { get; private set; }

        public IEnumerable<FaultCodeEntry> Entries => _byCode.Values;
        public int Count => _byCode.Count;

        public static readonly string[] Columns = { "code", "name", "scope", "detected_by", "description", "display_text" };

        public static FaultCodeTable FromCsv(string csv, string origin, bool isPlaceholder)
        {
            var t = new FaultCodeTable { Origin = origin, IsPlaceholder = isPlaceholder };
            var rows = Csv.Parse(csv);
            if (rows.Count == 0) throw new FormatException("fault code table is empty");
            var header = rows[0];
            var idx = new int[Columns.Length];
            for (int c = 0; c < Columns.Length; c++)
            {
                idx[c] = header.IndexOf(Columns[c]);
                if (idx[c] < 0) throw new FormatException("fault code table: missing column '" + Columns[c] + "'");
            }
            for (int r = 1; r < rows.Count; r++)
            {
                var row = rows[r];
                if (row.Count == 1 && row[0].Trim().Length == 0) continue;
                if (row.Count < header.Count) throw new FormatException("fault code table: row " + (r + 1) + " has too few columns");
                if (!int.TryParse(row[idx[0]], NumberStyles.Integer, CultureInfo.InvariantCulture, out var code) || code < 0)
                    throw new FormatException("fault code table: row " + (r + 1) + " has an invalid code '" + row[idx[0]] + "'");
                if (t._byCode.ContainsKey(code)) throw new FormatException("fault code table: duplicate code " + code);
                t._byCode[code] = new FaultCodeEntry
                {
                    Code = code,
                    Name = row[idx[1]],
                    Scope = row[idx[2]],
                    DetectedBy = row[idx[3]],
                    Description = row[idx[4]],
                    DisplayText = row[idx[5]],
                    Channel = code >= 100 ? code / 100 : 0,
                };
            }
            return t;
        }

        public bool Contains(int code) => _byCode.ContainsKey(code);

        public FaultCodeEntry Find(int code) => _byCode.TryGetValue(code, out var e) ? e : null;

        /// <summary>Display text for a code; never invents a meaning for an unknown code.</summary>
        public string Describe(int code)
        {
            if (code == 0) return "No fault";
            var e = Find(code);
            if (e != null) return string.IsNullOrEmpty(e.DisplayText) ? e.Name : e.DisplayText;
            return "Unknown fault code " + code.ToString(CultureInfo.InvariantCulture) + " (not in " + Origin + ")";
        }

        public string NameOf(int code)
        {
            if (code == 0) return "NONE";
            var e = Find(code);
            return e != null ? e.Name : "UNKNOWN_" + code.ToString(CultureInfo.InvariantCulture);
        }

        /// <summary>CSV text of the placeholder table derived from the plan (section 3W). Display texts are marked placeholder.</summary>
        public static string PlaceholderCsvFromPlan()
        {
            var sb = new StringBuilder();
            sb.AppendLine(string.Join(",", Columns));
            void Row(int code, string name, string scope, string by, string desc) =>
                sb.AppendLine(code + "," + name + "," + scope + "," + Csv.Quote(by) + "," + Csv.Quote(desc) + "," + Csv.Quote(desc + " [placeholder text]"));
            Row(0, "NONE", "-", "-", "No fault");
            Row(1, "HOST_HEARTBEAT_LOST", "System", "MCU", "Host heartbeat lost");
            Row(2, "MCU_WATCHDOG_RESET", "System", "MCU", "MCU watchdog reset");
            Row(3, "PSU_UNDERVOLTAGE", "System", "MCU", "Supply undervoltage");
            Row(4, "PSU_OVERVOLTAGE", "System", "MCU", "Supply overvoltage");
            Row(5, "MASTER_SWITCH_FAULT", "System", "MCU", "Master switch fault");
            Row(6, "COMM_CRC_ERROR_RATE", "System", "MCU / host", "Communication error rate");
            Row(7, "TWIN_DATA_STALE", "System", "Controller (software)", "Twin data stale");
            Row(8, "HW_DATA_STALE", "System", "Controller (software)", "Hardware data stale");
            var ch = new[]
            {
                (1, "SENSOR_A_OPEN", "MCU", "Sensor A open"), (2, "SENSOR_A_SHORT", "MCU", "Sensor A short"),
                (3, "SENSOR_B_OPEN", "MCU", "Sensor B open"), (4, "SENSOR_B_SHORT", "MCU", "Sensor B short"),
                (5, "SENSOR_DISAGREE", "Controller", "Sensors A/B disagree"), (6, "OVERTEMP_SW", "MCU / controller", "Module over-temperature (software)"),
                (7, "OVERTEMP_HW_CUTOFF", "Hardware -> MCU", "Hardware over-temperature cutoff"), (8, "DISCONNECTED", "MCU (presence pin)", "Module disconnected"),
                (9, "HEATER_OPEN", "MCU / controller", "Heater open circuit"), (10, "OVERCURRENT", "MCU / controller", "Heater over-current"),
                (11, "STUCK_ON", "MCU / controller", "Heater stuck on (current while commanded off)"),
            };
            for (int i = 1; i <= 4; i++)
                foreach (var (k, name, by, desc) in ch)
                    Row(100 * i + k, name, "Channel " + i, by, "CH" + i + ": " + desc);
            return sb.ToString();
        }
    }

    /// <summary>Minimal RFC 4180 CSV reader/writer (quoted fields, doubled quotes, CRLF/LF).</summary>
    public static class Csv
    {
        public static List<List<string>> Parse(string text)
        {
            var rows = new List<List<string>>();
            var row = new List<string>();
            var field = new StringBuilder();
            bool inQuotes = false;
            for (int i = 0; i < text.Length; i++)
            {
                char c = text[i];
                if (inQuotes)
                {
                    if (c == '"')
                    {
                        if (i + 1 < text.Length && text[i + 1] == '"') { field.Append('"'); i++; }
                        else inQuotes = false;
                    }
                    else field.Append(c);
                    continue;
                }
                switch (c)
                {
                    case '"': inQuotes = true; break;
                    case ',': row.Add(field.ToString()); field.Clear(); break;
                    case '\r': break;
                    case '\n':
                        row.Add(field.ToString()); field.Clear();
                        rows.Add(row); row = new List<string>();
                        break;
                    default: field.Append(c); break;
                }
            }
            if (field.Length > 0 || row.Count > 0) { row.Add(field.ToString()); rows.Add(row); }
            return rows;
        }

        public static string Quote(string s)
        {
            if (s == null) return "";
            if (s.IndexOfAny(new[] { ',', '"', '\n', '\r' }) < 0) return s;
            return "\"" + s.Replace("\"", "\"\"") + "\"";
        }
    }
}
