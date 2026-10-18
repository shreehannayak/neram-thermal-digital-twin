using System.Collections.Generic;
using System.Text;

namespace Neram.Core
{
    public enum IssueSeverity { Info, Warning, Error }

    public sealed class ValidationIssue
    {
        public IssueSeverity Severity;
        /// <summary>Stable code from unity/schema/VALIDATION_RULES.md, e.g. "E040".</summary>
        public string Code;
        /// <summary>1-based line number in the replay file (0 = file level).</summary>
        public int Line;
        public string Field;
        public string Message;

        public override string ToString()
        {
            var where = Line > 0 ? "line " + Line : "file";
            return Field != null ? $"{Code} [{where}, {Field}] {Message}" : $"{Code} [{where}] {Message}";
        }
    }

    /// <summary>Collected validation results. Any error means the replay is rejected as a whole.</summary>
    public sealed class ValidationReport
    {
        public const int MaxErrors = 200;
        public const int MaxStoredPerCode = 25;

        public readonly List<ValidationIssue> Issues = new List<ValidationIssue>();
        /// <summary>Total occurrences per code (including ones not stored because of MaxStoredPerCode).</summary>
        public readonly Dictionary<string, int> CountByCode = new Dictionary<string, int>();
        public int ErrorCount { get; private set; }
        public int WarningCount { get; private set; }
        public bool Truncated { get; private set; }

        public bool IsValid => ErrorCount == 0;
        public bool StopRequested => ErrorCount >= MaxErrors;

        public void Add(IssueSeverity sev, string code, int line, string field, string message)
        {
            CountByCode.TryGetValue(code, out var n);
            CountByCode[code] = n + 1;
            if (sev == IssueSeverity.Error) ErrorCount++;
            else if (sev == IssueSeverity.Warning) WarningCount++;
            if (n < MaxStoredPerCode)
                Issues.Add(new ValidationIssue { Severity = sev, Code = code, Line = line, Field = field, Message = message });
            if (sev == IssueSeverity.Error && ErrorCount == MaxErrors && !Truncated)
            {
                Truncated = true;
                Issues.Add(new ValidationIssue { Severity = IssueSeverity.Error, Code = "E099", Line = line, Message = "more than " + MaxErrors + " errors; validation stopped" });
                CountByCode["E099"] = 1;
            }
        }

        public void Error(string code, int line, string field, string message) => Add(IssueSeverity.Error, code, line, field, message);
        public void Warn(string code, int line, string field, string message) => Add(IssueSeverity.Warning, code, line, field, message);
        public void Info(string code, int line, string field, string message) => Add(IssueSeverity.Info, code, line, field, message);

        public bool Has(string code) => CountByCode.ContainsKey(code);

        public IEnumerable<string> Codes => CountByCode.Keys;

        public string Summary()
        {
            var sb = new StringBuilder();
            sb.Append(IsValid ? "VALID" : "INVALID").Append(": ").Append(ErrorCount).Append(" error(s), ")
              .Append(WarningCount).Append(" warning(s)");
            foreach (var kv in CountByCode) sb.Append("; ").Append(kv.Key).Append(" x").Append(kv.Value);
            return sb.ToString();
        }
    }
}
