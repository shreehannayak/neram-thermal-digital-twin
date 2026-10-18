using System;
using System.Linq;
using Neram.Core;
using UnityEngine.UIElements;

namespace Neram.Unity
{
    /// <summary>
    /// Modal shown when a replay fails validation. Nothing from the rejected file is displayed anywhere; the views stay
    /// unbound. Lists the first issues with code, line, field and message (codes: unity/schema/VALIDATION_RULES.md).
    /// </summary>
    public sealed class DataErrorScreen
    {
        private readonly VisualElement _scrim;
        private readonly Action _openScenarios;

        public DataErrorScreen(VisualElement root, Action openScenarios)
        {
            _scrim = UiUtil.Req<VisualElement>(root, "data-error");
            _openScenarios = openScenarios;
        }

        public bool IsOpen => UiUtil.IsShown(_scrim);
        public void Hide() => UiUtil.Show(_scrim, false);

        public void Show(ScenarioListing listing, ReplayParseResult result, string message)
        {
            _scrim.Clear();
            var modal = UiUtil.Box("modal");
            modal.Add(UiUtil.Label("Replay rejected — nothing from this file is displayed", "modal-title"));
            modal.Add(UiUtil.Label(message ?? "", "card-text"));
            modal.Add(UiUtil.KeyValue("file", listing?.FilePath ?? "-"));
            if (result != null)
            {
                modal.Add(UiUtil.KeyValue("summary", result.Report.Summary()));
                modal.Add(UiUtil.KeyValue("lines read", result.LineCount.ToString()));
                var list = new ScrollView();
                list.style.maxHeight = 460;
                list.style.marginTop = 8;
                foreach (var i in result.Report.Issues.Where(x => x.Severity == IssueSeverity.Error).Take(80))
                {
                    var row = UiUtil.Box("issue-row");
                    row.Add(UiUtil.Label(i.Code, "issue-code"));
                    row.Add(UiUtil.Label(i.Line > 0 ? "line " + i.Line + (i.Field != null ? "  " + i.Field : "") : (i.Field ?? "file"), "issue-where"));
                    row.Add(UiUtil.Label(i.Message, "issue-msg"));
                    list.Add(row);
                }
                modal.Add(list);
            }
            modal.Add(UiUtil.Label("Check the file with: python integration/validate_replay.py <file>. Rules: unity/schema/VALIDATION_RULES.md.", "card-text"));
            var buttons = UiUtil.Box("row");
            buttons.style.marginTop = 12;
            buttons.Add(UiUtil.Button("Choose another scenario", () => { Hide(); _openScenarios(); }, "btn-primary"));
            buttons.Add(UiUtil.Button("Close", Hide));
            modal.Add(buttons);
            _scrim.Add(modal);
            UiUtil.Show(_scrim, true);
        }
    }

    /// <summary>Loading progress modal (lines parsed, cancel).</summary>
    public sealed class LoadingOverlay
    {
        private readonly VisualElement _scrim;
        private readonly Label _text;
        private readonly VisualElement _fill;

        public LoadingOverlay(VisualElement root, Action cancel)
        {
            _scrim = UiUtil.Req<VisualElement>(root, "loading");
            var box = UiUtil.Box("modal", "modal-neutral");
            box.style.width = 520;
            box.Add(UiUtil.Label("Loading and validating replay", "card-title"));
            _text = UiUtil.Label("", "card-text", "mono");
            box.Add(_text);
            var track = UiUtil.Box("progress-track");
            _fill = UiUtil.Box("progress-fill");
            track.Add(_fill);
            box.Add(track);
            var b = UiUtil.Button("Cancel", cancel);
            b.style.marginTop = 10;
            b.style.alignSelf = Align.FlexStart;
            box.Add(b);
            _scrim.Add(box);
        }

        public void Show(string what)
        {
            _text.text = what;
            UiUtil.Show(_scrim, true);
        }

        /// <summary>Indeterminate progress (line count is known, total is not for gzip streams).</summary>
        public void Progress(string file, int lines, float seconds)
        {
            _text.text = file + "\n" + lines + " lines validated  ·  " + seconds.ToString("0.0") + " s";
            _fill.style.width = new StyleLength(new Length((seconds * 37f) % 100f, LengthUnit.Percent));
        }

        public void Hide() => UiUtil.Show(_scrim, false);
    }
}
