using System;
using Neram.Core;
using UnityEngine;

namespace Neram.Unity
{
    /// <summary>
    /// Unity wrapper around the deterministic ReplayClockModel. One clock drives every view through FrameChanged, so the
    /// graph, 3D scene, banner, telemetry, timeline and event log always show the same frame.
    /// Uses unscaled real time, so Time.timeScale (e.g. paused editor) never desynchronises the replay.
    /// </summary>
    public sealed class ReplayClock : MonoBehaviour
    {
        public ReplayClockModel Model { get; private set; }
        public int Frame => Model?.Frame ?? 0;
        public bool HasReplay => Model != null;

        /// <summary>(frame, isJump). isJump is true for seeks/steps so views can snap instead of easing.</summary>
        public event Action<int, bool> FrameChanged;
        public event Action StateChanged;

        private bool _jumpPending;

        public void Attach(ReplayTable table)
        {
            Detach();
            Model = new ReplayClockModel(table);
            Model.FrameChanged += OnModelFrame;
            Model.StateChanged += OnModelState;
            _jumpPending = true;
            OnModelFrame(Model.Frame);
            OnModelState();
        }

        public void Detach()
        {
            if (Model == null) return;
            Model.FrameChanged -= OnModelFrame;
            Model.StateChanged -= OnModelState;
            Model = null;
        }

        private void OnModelFrame(int frame)
        {
            var jump = _jumpPending;
            _jumpPending = false;
            FrameChanged?.Invoke(frame, jump);
        }

        private void OnModelState() => StateChanged?.Invoke();

        private void Update()
        {
            if (Model == null) return;
            Model.Advance(Time.unscaledDeltaTime);
        }

        // ---- controls (all mark the next frame change as a jump) ----
        public void TogglePlay() { if (Model != null) Model.TogglePlay(); }
        public void Play() { if (Model != null) Model.Play(); }
        public void Pause() { if (Model != null) Model.Pause(); }
        public void SetSpeed(double s) { if (Model != null) Model.SetSpeed(s); }
        public void StepForward() { if (Model == null) return; _jumpPending = true; Model.StepForward(); _jumpPending = false; }
        public void StepBack() { if (Model == null) return; _jumpPending = true; Model.StepBack(); _jumpPending = false; }
        public void Restart() { if (Model == null) return; _jumpPending = true; Model.Restart(); _jumpPending = false; }
        public void SeekFrame(int f) { if (Model == null) return; _jumpPending = true; Model.SeekFrame(f); _jumpPending = false; }
        public void SeekFraction(double x) { if (Model == null) return; _jumpPending = true; Model.SeekFraction(x); _jumpPending = false; }
        public void SeekTime(double t) { if (Model == null) return; _jumpPending = true; Model.Seek(t); _jumpPending = false; }
    }
}
