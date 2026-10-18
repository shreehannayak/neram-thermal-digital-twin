using System;

namespace Neram.Core
{
    /// <summary>
    /// Deterministic replay clock. Holds a logical time inside [first t_s, last t_s] and the index of the frame shown
    /// at that time (largest frame with t_s &lt;= time). Every view reads the same Frame, so graph, 3D scene,
    /// controller banner, telemetry and event log can never disagree. Pure C#: unit-tested without Unity.
    /// </summary>
    public sealed class ReplayClockModel
    {
        /// <summary>Playback speeds offered by the UI (x1, x10, x60 logical seconds per real second).</summary>
        public static readonly double[] Speeds = { 1.0, 2.0, 4.0, 10.0, 60.0 };

        private readonly ReplayTable _table;
        public double Time { get; private set; }
        public int Frame { get; private set; }
        public bool Playing { get; private set; }
        public double Speed { get; private set; } = 1.0;
        public bool AtEnd => Frame == _table.FrameCount - 1 && Time >= _table.EndTime;

        /// <summary>Raised whenever Frame changes (argument: new frame). Not raised when only Time moves inside a frame.</summary>
        public event Action<int> FrameChanged;
        /// <summary>Raised on play/pause/speed changes.</summary>
        public event Action StateChanged;

        public ReplayClockModel(ReplayTable table)
        {
            _table = table ?? throw new ArgumentNullException(nameof(table));
            Time = table.StartTime;
            Frame = 0;
        }

        public int FrameCount => _table.FrameCount;
        public double StartTime => _table.StartTime;
        public double EndTime => _table.EndTime;
        public double Elapsed => Time - _table.StartTime;

        /// <summary>Advance by real (unscaled) seconds. Returns true if the frame changed.</summary>
        public bool Advance(double realDeltaSeconds)
        {
            if (!Playing || realDeltaSeconds <= 0) return false;
            double t = Time + realDeltaSeconds * Speed;
            if (t >= _table.EndTime)
            {
                t = _table.EndTime;
                Playing = false;
                SetTime(t);
                StateChanged?.Invoke();
                return true;
            }
            return SetTime(t);
        }

        public void Play()
        {
            if (AtEnd) SeekFrame(0);
            if (Playing) return;
            Playing = true;
            StateChanged?.Invoke();
        }

        public void Pause()
        {
            if (!Playing) return;
            Playing = false;
            StateChanged?.Invoke();
        }

        public void TogglePlay()
        {
            if (Playing) Pause(); else Play();
        }

        public void SetSpeed(double speed)
        {
            if (Array.IndexOf(Speeds, speed) < 0) throw new ArgumentOutOfRangeException(nameof(speed), "speed must be one of x1, x2, x4, x10, x60");
            if (Speed == speed) return;
            Speed = speed;
            StateChanged?.Invoke();
        }

        /// <summary>Seek to a logical time (clamped). Returns true if the frame changed.</summary>
        public bool Seek(double t)
        {
            if (double.IsNaN(t)) return false;
            t = Math.Max(_table.StartTime, Math.Min(_table.EndTime, t));
            return SetTime(t);
        }

        /// <summary>Seek to the start of a frame (clamped). Returns true if the frame changed.</summary>
        public bool SeekFrame(int frame)
        {
            frame = Math.Max(0, Math.Min(_table.FrameCount - 1, frame));
            return SetTime(_table.T[frame]);
        }

        /// <summary>Pause and move one frame forward.</summary>
        public bool StepForward()
        {
            Pause();
            return SeekFrame(Frame + 1);
        }

        /// <summary>Pause and move one frame back.</summary>
        public bool StepBack()
        {
            Pause();
            return SeekFrame(Frame - 1);
        }

        /// <summary>Back to the first frame; keeps the play/pause state.</summary>
        public bool Restart() => SeekFrame(0);

        /// <summary>Seek to a fraction 0..1 of the replay duration (used by the scrubber).</summary>
        public bool SeekFraction(double fraction)
        {
            fraction = Math.Max(0, Math.Min(1, fraction));
            return Seek(_table.StartTime + fraction * _table.Duration);
        }

        public double Fraction => _table.Duration <= 0 ? 0 : (Time - _table.StartTime) / _table.Duration;

        private bool SetTime(double t)
        {
            Time = t;
            int f = _table.FrameAtTime(t);
            if (f == Frame) return false;
            Frame = f;
            FrameChanged?.Invoke(f);
            return true;
        }
    }
}
