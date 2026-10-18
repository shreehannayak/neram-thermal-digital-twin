#pragma warning disable
using System;
using System.Collections.Generic;
namespace UnityEngine.UIElements
{
    public enum PickingMode { Position, Ignore }
    public enum TrickleDown { NoTrickleDown, TrickleDown }
    public enum LengthUnit { Pixel, Percent }
    public enum Visibility { Visible, Hidden }
    public enum DisplayStyle { Flex, None }
    public enum Align { Auto, FlexStart, Center, FlexEnd, Stretch }
    public enum Justify { FlexStart, Center, FlexEnd, SpaceBetween, SpaceAround }
    public enum FlexDirection { Column, ColumnReverse, Row, RowReverse }
    public enum Position { Relative, Absolute }
    public enum Wrap { NoWrap, Wrap, WrapReverse }
    public enum WhiteSpace { Normal, NoWrap }
    public enum Overflow { Visible, Hidden }
    public enum LineJoin { Miter, Bevel, Round }
    public enum LineCap { Butt, Round }
    public enum StyleKeyword { Undefined, Null, Auto, None, Initial }
    public enum ScrollViewMode { Vertical, Horizontal, VerticalAndHorizontal }
    public enum ScrollerVisibility { Auto, AlwaysVisible, Hidden }
    public enum PanelScaleMode { ConstantPixelSize, ConstantPhysicalSize, ScaleWithScreenSize }
    public enum PanelScreenMatchMode { MatchWidthOrHeight = 0, Shrink = 1, Expand = 2 }
    public enum ArcDirection { Clockwise, CounterClockwise }

    public struct Length
    {
        public Length(float v) { } public Length(float v, LengthUnit u) { }
        public static Length Percent(float v) => default;
    }
    public struct StyleLength
    {
        public StyleLength(float v) { } public StyleLength(Length v) { } public StyleLength(StyleKeyword k) { }
        public static implicit operator StyleLength(float v) => default;
        public static implicit operator StyleLength(Length v) => default;
        public static implicit operator StyleLength(StyleKeyword k) => default;
        public Length value => default;
    }
    public struct StyleFloat { public StyleFloat(float v) { } public static implicit operator StyleFloat(float v) => default; public static implicit operator StyleFloat(StyleKeyword k) => default; public float value => 0; }
    public struct StyleInt { public static implicit operator StyleInt(int v) => default; }
    public struct StyleColor { public StyleColor(Color c) { } public static implicit operator StyleColor(Color c) => default; public static implicit operator StyleColor(StyleKeyword k) => default; public Color value => default; }
    public struct StyleEnum<T> where T : struct, IConvertible { public StyleEnum(T v) { } public static implicit operator StyleEnum<T>(T v) => default; public static implicit operator StyleEnum<T>(StyleKeyword k) => default; public T value => default; }
    public struct Translate { public Translate(Length x, Length y) { } }
    public struct StyleTranslate { public static implicit operator StyleTranslate(Translate t) => default; }
    public struct StyleFont { public static implicit operator StyleFont(Font f) => default; }

    public interface IStyle
    {
        StyleLength left { get; set; } StyleLength top { get; set; } StyleLength right { get; set; } StyleLength bottom { get; set; }
        StyleLength width { get; set; } StyleLength height { get; set; } StyleLength minWidth { get; set; } StyleLength minHeight { get; set; }
        StyleLength maxWidth { get; set; } StyleLength maxHeight { get; set; }
        StyleLength marginTop { get; set; } StyleLength marginBottom { get; set; } StyleLength marginLeft { get; set; } StyleLength marginRight { get; set; }
        StyleLength paddingTop { get; set; } StyleLength paddingBottom { get; set; } StyleLength paddingLeft { get; set; } StyleLength paddingRight { get; set; }
        StyleLength fontSize { get; set; }
        StyleFloat flexGrow { get; set; } StyleFloat flexShrink { get; set; } StyleFloat opacity { get; set; }
        StyleFloat borderTopWidth { get; set; } StyleFloat borderBottomWidth { get; set; } StyleFloat borderLeftWidth { get; set; } StyleFloat borderRightWidth { get; set; }
        StyleColor color { get; set; } StyleColor backgroundColor { get; set; }
        StyleColor borderTopColor { get; set; } StyleColor borderBottomColor { get; set; } StyleColor borderLeftColor { get; set; } StyleColor borderRightColor { get; set; }
        StyleLength borderTopLeftRadius { get; set; } StyleLength borderTopRightRadius { get; set; } StyleLength borderBottomLeftRadius { get; set; } StyleLength borderBottomRightRadius { get; set; }
        StyleEnum<Visibility> visibility { get; set; } StyleEnum<DisplayStyle> display { get; set; }
        StyleEnum<Align> alignSelf { get; set; } StyleEnum<Align> alignItems { get; set; } StyleEnum<Justify> justifyContent { get; set; }
        StyleEnum<FlexDirection> flexDirection { get; set; } StyleEnum<Position> position { get; set; } StyleEnum<Wrap> flexWrap { get; set; }
        StyleEnum<WhiteSpace> whiteSpace { get; set; } StyleEnum<Overflow> overflow { get; set; }
        StyleEnum<TextAnchor> unityTextAlign { get; set; } StyleTranslate translate { get; set; }
    }
    public interface IResolvedStyle { float width { get; } float height { get; } Color color { get; } float fontSize { get; } }
    public interface ICustomStyle { bool TryGetValue(CustomStyleProperty<Color> p, out Color v); bool TryGetValue(CustomStyleProperty<float> p, out float v); bool TryGetValue(CustomStyleProperty<int> p, out int v); }
    public struct CustomStyleProperty<T> { public CustomStyleProperty(string name) { } public string name => null; }

    public interface IPanel { VisualElement visualTree { get; } VisualElement Pick(Vector2 point); }
    public interface IVisualElementScheduledItem { IVisualElementScheduledItem StartingIn(long ms); IVisualElementScheduledItem Every(long ms); void Pause(); void Resume(); }
    public interface IVisualElementScheduler { IVisualElementScheduledItem Execute(Action a); }
    public interface IEventHandler { }

    public delegate void EventCallback<in TEventType>(TEventType evt);
    public abstract class EventBase { public void StopPropagation() { } public void PreventDefault() { } public IEventHandler target => null; public IEventHandler currentTarget => null; }
    public abstract class EventBase<T> : EventBase where T : EventBase<T>, new() { }
    public abstract class PointerEventBase<T> : EventBase<T> where T : PointerEventBase<T>, new()
    {
        public int pointerId => 0; public int button => 0; public Vector3 position => default; public Vector3 localPosition => default;
        public Vector3 deltaPosition => default; public int clickCount => 0; public bool shiftKey => false; public bool ctrlKey => false; public bool altKey => false;
    }
    public sealed class PointerDownEvent : PointerEventBase<PointerDownEvent> { }
    public sealed class PointerMoveEvent : PointerEventBase<PointerMoveEvent> { }
    public sealed class PointerUpEvent : PointerEventBase<PointerUpEvent> { }
    public sealed class PointerLeaveEvent : PointerEventBase<PointerLeaveEvent> { }
    public sealed class PointerEnterEvent : PointerEventBase<PointerEnterEvent> { }
    public sealed class ClickEvent : PointerEventBase<ClickEvent> { }
    public abstract class MouseEventBase<T> : EventBase<T> where T : MouseEventBase<T>, new() { public Vector2 mousePosition => default; public Vector2 localMousePosition => default; public Vector3 delta => default; }
    public sealed class WheelEvent : MouseEventBase<WheelEvent> { }
    public sealed class MouseLeaveEvent : MouseEventBase<MouseLeaveEvent> { }
    public sealed class KeyDownEvent : EventBase<KeyDownEvent> { public KeyCode keyCode => KeyCode.None; public char character => '\0'; public bool shiftKey => false; public bool ctrlKey => false; public bool altKey => false; }
    public sealed class GeometryChangedEvent : EventBase<GeometryChangedEvent> { public Rect newRect => default; public Rect oldRect => default; }
    public sealed class CustomStyleResolvedEvent : EventBase<CustomStyleResolvedEvent> { public ICustomStyle customStyle => null; }
    public sealed class AttachToPanelEvent : EventBase<AttachToPanelEvent> { }
    public sealed class DetachFromPanelEvent : EventBase<DetachFromPanelEvent> { }

    public class Painter2D
    {
        public float lineWidth { get; set; } public Color strokeColor { get; set; } public Color fillColor { get; set; }
        public LineJoin lineJoin { get; set; } public LineCap lineCap { get; set; }
        public void BeginPath() { } public void ClosePath() { } public void MoveTo(Vector2 p) { } public void LineTo(Vector2 p) { }
        public void Arc(Vector2 c, float r, Angle a0, Angle a1, ArcDirection d = ArcDirection.Clockwise) { }
        public void Stroke() { } public void Fill(FillRule r = FillRule.NonZero) { }
    }
    public enum FillRule { NonZero, OddEven }
    public struct Angle { public static Angle Degrees(float v) => default; public static Angle Radians(float v) => default; public static implicit operator Angle(float v) => default; }
    public class MeshGenerationContext { public Painter2D painter2D => null; public VisualElement visualElement => null; }

    public class VisualElement : IEventHandler
    {
        public string name { get; set; }
        public string tooltip { get; set; }
        public IStyle style => null;
        public IResolvedStyle resolvedStyle => null;
        public ICustomStyle customStyle => null;
        public PickingMode pickingMode { get; set; }
        public bool focusable { get; set; }
        public bool visible { get; set; }
        public bool enabledSelf => true;
        public Rect contentRect => default;
        public Rect layout => default;
        public Rect worldBound => default;
        public IPanel panel => null;
        public VisualElement parent => null;
        public int childCount => 0;
        public IVisualElementScheduler schedule => null;
        public Action<MeshGenerationContext> generateVisualContent { get; set; }
        public object userData { get; set; }
        public VisualElement this[int i] => null;
        public IEnumerable<VisualElement> Children() => new VisualElement[0];
        public void Add(VisualElement c) { }
        public void Insert(int i, VisualElement c) { }
        public int IndexOf(VisualElement c) => -1;
        public void Remove(VisualElement c) { }
        public void RemoveAt(int i) { }
        public void RemoveFromHierarchy() { }
        public void Clear() { }
        public void BringToFront() { }
        public void AddToClassList(string c) { }
        public void RemoveFromClassList(string c) { }
        public void EnableInClassList(string c, bool e) { }
        public bool ClassListContains(string c) => false;
        public void ToggleInClassList(string c) { }
        public void ClearClassList() { }
        public void MarkDirtyRepaint() { }
        public void Focus() { }
        public void Blur() { }
        public void SetEnabled(bool e) { }
        public void CapturePointer(int id) { }
        public void ReleasePointer(int id) { }
        public bool HasPointerCapture(int id) => false;
        public void RegisterCallback<TEventType>(EventCallback<TEventType> cb, TrickleDown td = TrickleDown.NoTrickleDown) where TEventType : EventBase<TEventType>, new() { }
        public void UnregisterCallback<TEventType>(EventCallback<TEventType> cb, TrickleDown td = TrickleDown.NoTrickleDown) where TEventType : EventBase<TEventType>, new() { }
        public T Q<T>(string name = null, string className = null) where T : VisualElement => null;
        public VisualElement Q(string name = null, string className = null) => null;
        public Vector2 WorldToLocal(Vector2 p) => p;
        public Vector2 LocalToWorld(Vector2 p) => p;
    }
    public class TextElement : VisualElement { public string text { get; set; } public bool enableRichText { get; set; } }
    public class Label : TextElement { public Label() { } public Label(string t) { } }
    public class Button : TextElement { public Button() { } public Button(Action a) { } public event Action clicked; }
    public class ScrollView : VisualElement
    {
        public ScrollView() { } public ScrollView(ScrollViewMode m) { }
        public VisualElement contentContainer => null; public Vector2 scrollOffset { get; set; }
        public ScrollerVisibility horizontalScrollerVisibility { get; set; } public ScrollerVisibility verticalScrollerVisibility { get; set; }
        public void ScrollTo(VisualElement e) { }
    }
    public static class RuntimePanelUtils
    {
        public static Vector2 CameraTransformWorldToPanel(IPanel panel, Vector3 world, Camera cam) => default;
        public static Vector2 ScreenToPanel(IPanel panel, Vector2 screen) => default;
    }
    public class StyleSheet : ScriptableObject { }
    public class ThemeStyleSheet : StyleSheet { }
    public class VisualTreeAsset : ScriptableObject { public void CloneTree(VisualElement target) { } }
    public class PanelSettings : ScriptableObject
    {
        public PanelScaleMode scaleMode { get; set; } public Vector2Int referenceResolution { get; set; }
        public PanelScreenMatchMode screenMatchMode { get; set; } public float match { get; set; } public ThemeStyleSheet themeStyleSheet { get; set; }
        public float sortingOrder { get; set; }
    }
    public class UIDocument : MonoBehaviour { public PanelSettings panelSettings { get; set; } public VisualTreeAsset visualTreeAsset { get; set; } public VisualElement rootVisualElement => null; }
}
namespace UnityEngine { public enum TextAnchor { UpperLeft, UpperCenter, UpperRight, MiddleLeft, MiddleCenter, MiddleRight, LowerLeft, LowerCenter, LowerRight } }
namespace UnityEngine.UIElements
{
    public struct UQueryBuilder<T> where T : VisualElement { public void ForEach(System.Action<T> funcCall) { } }
    public static class UQueryExtensions { public static UQueryBuilder<T> Query<T>(this VisualElement e, string name = null, string className = null) where T : VisualElement => default; }
}

namespace UnityEngine.UIElements
{
    /// <summary>Real UI Toolkit type (mouse cursor style). Present so that an unqualified `Cursor` in a file that imports
    /// both UnityEngine and UnityEngine.UIElements fails the stub compile exactly as it fails in Unity (CS0104).</summary>
    public struct Cursor { public Texture2D texture { get; set; } public Vector2 hotspot { get; set; } }
}
