using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UIElements;

namespace Neram.Unity
{
    /// <summary>Implemented by every view: bind once per loaded replay, then render a frame. Views never mutate replay data.</summary>
    public interface IReplayView
    {
        void Bind(Neram.Core.ReplaySession session);
        void ShowFrame(int frame);
        void Unbind();
    }

    /// <summary>Small helpers shared by the UI controllers (element lookup, labels, chips, rows).</summary>
    public static class UiUtil
    {
        /// <summary>Required element lookup: a missing element is a setup error, reported loudly instead of failing silently.</summary>
        public static T Req<T>(VisualElement root, string name) where T : VisualElement
        {
            var e = root.Q<T>(name);
            if (e == null) throw new InvalidOperationException("NERAM UI: element '" + name + "' (" + typeof(T).Name + ") not found in NeramMain.uxml");
            return e;
        }

        public static Label Label(string text, params string[] classes)
        {
            var l = new Label(text);
            foreach (var c in classes) l.AddToClassList(c);
            return l;
        }

        public static VisualElement Box(params string[] classes)
        {
            var e = new VisualElement();
            foreach (var c in classes) e.AddToClassList(c);
            return e;
        }

        public static Label Chip(string text, string variant = null)
        {
            var l = new Label(text);
            l.AddToClassList("chip");
            if (!string.IsNullOrEmpty(variant)) l.AddToClassList(variant);
            return l;
        }

        public static Button Button(string text, Action onClick, params string[] classes)
        {
            var b = new Button(onClick) { text = text };
            b.AddToClassList("btn");
            foreach (var c in classes) b.AddToClassList(c);
            return b;
        }

        public static void Show(VisualElement e, bool visible)
        {
            if (e == null) return;
            e.EnableInClassList("hidden", !visible);
        }

        public static bool IsShown(VisualElement e) => e != null && !e.ClassListContains("hidden");

        /// <summary>Set text only when it changed (avoids needless layout work every frame).</summary>
        public static void SetText(TextElement l, string text)
        {
            if (l != null && l.text != text) l.text = text;
        }

        public static VisualElement KeyValue(string key, string value, out Label valueLabel)
        {
            var row = Box("kv-row");
            row.Add(Label(key, "kv-k"));
            valueLabel = Label(value, "kv-v");
            row.Add(valueLabel);
            return row;
        }

        public static VisualElement KeyValue(string key, string value) => KeyValue(key, value, out _);

        /// <summary>Exclusive "selected" class within a button group.</summary>
        public static void Select(IEnumerable<Button> group, Button selected)
        {
            foreach (var b in group) b.EnableInClassList("selected", b == selected);
        }

        public static string StatusChipClass(string status) => "chip-status-" + (status ?? "TBD");

        public static Color StateColor(string stateName)
        {
            switch (stateName)
            {
                case "NORMAL": return new Color32(100, 116, 139, 255);
                case "PREDICTIVE_WARMING": return new Color32(167, 139, 250, 255);
                case "ACTIVE_WARMING": return new Color32(245, 158, 11, 255);
                case "TARGET_MAINTENANCE": return new Color32(16, 185, 129, 255);
                case "CLINICIAN_WARMING": return new Color32(56, 189, 248, 255);
                case "TWIN_DEGRADED": return new Color32(234, 179, 8, 255);
                case "SAFETY_SHUTDOWN": return new Color32(239, 68, 68, 255);
                default: return new Color32(107, 118, 132, 255);
            }
        }
    }
}
