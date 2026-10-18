using System;
using System.Collections.Generic;

namespace Neram.Core
{
    /// <summary>
    /// Validated replay data in columnar form: one double[] per field, NaN for null.
    /// Booleans are stored as 0/1, integer enums/codes as their integer value, string enums as
    /// their index in StringEnums. The JSON is discarded after parsing, so memory is
    /// (fields x frames x 8 bytes) regardless of file size, and every lookup is O(1) without allocation.
    /// A ReplayTable is immutable once built and only exists for files that passed validation.
    /// </summary>
    public sealed class ReplayTable
    {
        private readonly double[][] _cols;
        public readonly int FrameCount;
        /// <summary>Logical time of each frame (seconds since settled start), strictly increasing.</summary>
        public readonly double[] T;
        /// <summary>Index of the first frame of each twin-update bucket (floor(t_s / ts_twin_s)).</summary>
        public readonly int[] MinuteStartFrames;
        /// <summary>For each frame, the index into MinuteStartFrames of its bucket.</summary>
        public readonly int[] FrameMinute;
        public readonly double TwinPeriodS;

        internal ReplayTable(double[][] cols, int frameCount, double twinPeriodS)
        {
            _cols = cols;
            FrameCount = frameCount;
            T = cols[ReplayFields.Get("meta", "t_s").Id];
            TwinPeriodS = twinPeriodS;
            var starts = new List<int>();
            FrameMinute = new int[frameCount];
            long prev = long.MinValue;
            for (int i = 0; i < frameCount; i++)
            {
                long bucket = (long)Math.Floor(T[i] / twinPeriodS);
                if (bucket != prev) { starts.Add(i); prev = bucket; }
                FrameMinute[i] = starts.Count - 1;
            }
            MinuteStartFrames = starts.ToArray();
        }

        public double StartTime => T[0];
        public double EndTime => T[FrameCount - 1];
        public double Duration => EndTime - StartTime;

        public double Get(FieldDef f, int frame) => _cols[f.Id][frame];
        public double Get(int fieldId, int frame) => _cols[fieldId][frame];
        public bool IsNull(FieldDef f, int frame) => double.IsNaN(_cols[f.Id][frame]);
        public bool GetBool(FieldDef f, int frame) => _cols[f.Id][frame] > 0.5;
        public int GetInt(FieldDef f, int frame)
        {
            var v = _cols[f.Id][frame];
            return double.IsNaN(v) ? -1 : (int)v;
        }

        /// <summary>String value of a StringEnum field (plant_mode, src.*), or null.</summary>
        public string GetString(FieldDef f, int frame)
        {
            var v = _cols[f.Id][frame];
            if (double.IsNaN(v)) return null;
            var values = StringEnums.ValuesFor(f.EnumName);
            int idx = (int)v;
            return values != null && idx >= 0 && idx < values.Length ? values[idx] : null;
        }

        /// <summary>Read-only access to a whole column (used by charts; do not modify).</summary>
        public double[] Column(FieldDef f) => _cols[f.Id];

        /// <summary>Largest frame index with T[i] &lt;= t (0 when t is before the first frame).</summary>
        public int FrameAtTime(double t)
        {
            if (t <= T[0]) return 0;
            if (t >= T[FrameCount - 1]) return FrameCount - 1;
            int lo = 0, hi = FrameCount - 1;
            while (lo < hi)
            {
                int mid = (lo + hi + 1) >> 1;
                if (T[mid] <= t) lo = mid; else hi = mid - 1;
            }
            return lo;
        }
    }

    /// <summary>Growable column buffers used while parsing.</summary>
    internal sealed class ColumnBuilder
    {
        private double[][] _cols;
        private int _count;
        private int _capacity;

        public ColumnBuilder(int fieldCount, int initialCapacity = 1024)
        {
            _capacity = Math.Max(16, initialCapacity);
            _cols = new double[fieldCount][];
            for (int i = 0; i < fieldCount; i++) _cols[i] = NewNaN(_capacity);
        }

        public int Count => _count;

        public int AddRow()
        {
            if (_count == _capacity)
            {
                int newCap = _capacity * 2;
                for (int i = 0; i < _cols.Length; i++)
                {
                    var n = NewNaN(newCap);
                    Array.Copy(_cols[i], n, _count);
                    _cols[i] = n;
                }
                _capacity = newCap;
            }
            return _count++;
        }

        public void Set(int fieldId, int row, double value) => _cols[fieldId][row] = value;
        public double Get(int fieldId, int row) => _cols[fieldId][row];

        public ReplayTable Build(double twinPeriodS)
        {
            var trimmed = new double[_cols.Length][];
            for (int i = 0; i < _cols.Length; i++)
            {
                trimmed[i] = new double[_count];
                Array.Copy(_cols[i], trimmed[i], _count);
            }
            return new ReplayTable(trimmed, _count, twinPeriodS);
        }

        private static double[] NewNaN(int n)
        {
            var a = new double[n];
            for (int i = 0; i < n; i++) a[i] = double.NaN;
            return a;
        }
    }
}
