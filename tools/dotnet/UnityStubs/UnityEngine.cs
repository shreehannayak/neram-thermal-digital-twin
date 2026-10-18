#pragma warning disable
using System;
using System.Collections.Generic;
namespace UnityEngine
{
    public class Object
    {
        public string name { get; set; }
        public HideFlags hideFlags { get; set; }
        public static void Destroy(Object o) { }
        public static void DestroyImmediate(Object o) { }
        public static T Instantiate<T>(T original, Transform parent) where T : Object => original;
        public static T Instantiate<T>(T original) where T : Object => original;
        public static T FindAnyObjectByType<T>() where T : Object => null;
        public static Object FindAnyObjectByType(Type t) => null;
        public static T[] FindObjectsByType<T>(FindObjectsInactive i, FindObjectsSortMode s) where T : Object => new T[0];
        public static bool operator ==(Object a, Object b) => ReferenceEquals(a, b);
        public static bool operator !=(Object a, Object b) => !ReferenceEquals(a, b);
        public static implicit operator bool(Object o) => !ReferenceEquals(o, null);
        public override bool Equals(object o) => ReferenceEquals(this, o);
        public override int GetHashCode() => 0;
    }
    public enum HideFlags { None = 0, DontSave = 52 }
    public enum FindObjectsInactive { Exclude, Include }
    public enum FindObjectsSortMode { None, InstanceID }
    public class Component : Object
    {
        public GameObject gameObject => null;
        public Transform transform => null;
        public string tag { get; set; }
        public T GetComponent<T>() => default;
        public T GetComponentInParent<T>() => default;
        public T GetComponentInChildren<T>() => default;
        public T GetComponentInChildren<T>(bool includeInactive) => default;
        public T[] GetComponentsInChildren<T>() => new T[0];
        public T[] GetComponentsInChildren<T>(bool includeInactive) => new T[0];
    }
    public class Behaviour : Component { public bool enabled { get; set; } public bool isActiveAndEnabled => true; }
    public class MonoBehaviour : Behaviour { }
    public class ScriptableObject : Object { public static T CreateInstance<T>() where T : ScriptableObject => default; }
    public sealed class GameObject : Object
    {
        public GameObject() { }
        public GameObject(string name) { }
        public Transform transform => null;
        public string tag { get; set; }
        public bool activeSelf => true;
        public bool activeInHierarchy => true;
        public bool isStatic { get; set; }
        public UnityEngine.SceneManagement.Scene scene => default;
        public void SetActive(bool v) { }
        public T AddComponent<T>() where T : Component => default;
        public Component AddComponent(Type t) => null;
        public T GetComponentInChildren<T>() => default;
        public T GetComponent<T>() => default;
        public T GetComponentInParent<T>() => default;
        public T[] GetComponentsInChildren<T>() => new T[0];
        public T[] GetComponentsInChildren<T>(bool includeInactive) => new T[0];
        public static GameObject Find(string n) => null;
        public static GameObject CreatePrimitive(PrimitiveType t) => null;
    }
    public enum PrimitiveType { Sphere, Capsule, Cylinder, Cube, Plane, Quad }
    public class Transform : Component, System.Collections.IEnumerable
    {
        public Vector3 position { get; set; }
        public Vector3 localPosition { get; set; }
        public Quaternion rotation { get; set; }
        public Quaternion localRotation { get; set; }
        public Vector3 localScale { get; set; }
        public Vector3 right => default;
        public Vector3 up => default;
        public Vector3 forward => default;
        public Transform parent => null;
        public int childCount => 0;
        public void SetParent(Transform p, bool worldPositionStays) { }
        public void SetParent(Transform p) { }
        public void SetPositionAndRotation(Vector3 p, Quaternion q) { }
        public Transform Find(string n) => null;
        public Transform GetChild(int i) => null;
        public Vector3 InverseTransformPoint(Vector3 v) => v;
        public Vector3 InverseTransformDirection(Vector3 v) => v;
        public Vector3 TransformPoint(Vector3 v) => v;
        public System.Collections.IEnumerator GetEnumerator() { yield break; }
    }
    public struct Vector2
    {
        public float x, y;
        public Vector2(float x, float y) { this.x = x; this.y = y; }
        public float sqrMagnitude => x * x + y * y;
        public float magnitude => (float)Math.Sqrt(sqrMagnitude);
        public static Vector2 zero => default;
        public static Vector2 operator -(Vector2 a, Vector2 b) => new Vector2(a.x - b.x, a.y - b.y);
        public static Vector2 operator +(Vector2 a, Vector2 b) => new Vector2(a.x + b.x, a.y + b.y);
        public static Vector2 operator *(Vector2 a, float d) => new Vector2(a.x * d, a.y * d);
        public static Vector2 operator *(float d, Vector2 a) => new Vector2(a.x * d, a.y * d);
        public static Vector2 operator /(Vector2 a, float d) => new Vector2(a.x / d, a.y / d);
        public static implicit operator Vector2(Vector3 v) => new Vector2(v.x, v.y);
        public static implicit operator Vector3(Vector2 v) => new Vector3(v.x, v.y, 0);
        public static Vector2 SmoothDamp(Vector2 current, Vector2 target, ref Vector2 currentVelocity, float smoothTime, float maxSpeed, float deltaTime) => target;
    }
    public struct Vector2Int { public int x, y; public Vector2Int(int x, int y) { this.x = x; this.y = y; } }
    public struct Vector3
    {
        public void Normalize() { }
        public float x, y, z;
        public Vector3(float x, float y, float z) { this.x = x; this.y = y; this.z = z; }
        public Vector3(float x, float y) { this.x = x; this.y = y; z = 0; }
        public static Vector3 zero => default;
        public static Vector3 one => new Vector3(1, 1, 1);
        public static Vector3 up => new Vector3(0, 1, 0);
        public static Vector3 down => new Vector3(0, -1, 0);
        public static Vector3 forward => new Vector3(0, 0, 1);
        public static Vector3 right => new Vector3(1, 0, 0);
        public Vector3 normalized => this;
        public float magnitude => 0;
        public float sqrMagnitude => 0;
        public static Vector3 Cross(Vector3 a, Vector3 b) => default;
        public static float Dot(Vector3 a, Vector3 b) => 0;
        public static float Distance(Vector3 a, Vector3 b) => 0;
        public static Vector3 Lerp(Vector3 a, Vector3 b, float t) => a;
        public static Vector3 SmoothDamp(Vector3 c, Vector3 t, ref Vector3 v, float st, float ms, float dt) => c;
        public static Vector3 operator +(Vector3 a, Vector3 b) => a;
        public static Vector3 operator -(Vector3 a, Vector3 b) => a;
        public static Vector3 operator -(Vector3 a) => a;
        public static Vector3 operator *(Vector3 a, float d) => a;
        public static Vector3 operator *(float d, Vector3 a) => a;
        public static Vector3 operator /(Vector3 a, float d) => a;
        public static bool operator ==(Vector3 a, Vector3 b) => a.x == b.x && a.y == b.y && a.z == b.z;
        public static bool operator !=(Vector3 a, Vector3 b) => !(a == b);
        public override bool Equals(object o) => false;
        public override int GetHashCode() => 0;
    }
    public struct Vector4 { public float x, y, z, w; }
    public struct Quaternion
    {
        public float x, y, z, w;
        public Quaternion(float x, float y, float z, float w) { this.x = x; this.y = y; this.z = z; this.w = w; }
        public static Quaternion identity => default;
        public Vector3 eulerAngles => default;
        public static Quaternion Euler(float x, float y, float z) => default;
        public static Quaternion Euler(Vector3 e) => default;
        public static Quaternion LookRotation(Vector3 f) => default;
        public static Vector3 operator *(Quaternion q, Vector3 v) => v;
        public static Quaternion operator *(Quaternion a, Quaternion b) => a;
    }
    public struct Color
    {
        public float r, g, b, a;
        public Color(float r, float g, float b) { this.r = r; this.g = g; this.b = b; a = 1; }
        public Color(float r, float g, float b, float a) { this.r = r; this.g = g; this.b = b; this.a = a; }
        public static Color black => default; public static Color white => default; public static Color red => default; public static Color clear => default;
        public static Color operator *(Color c, float f) => c;
        public static Color operator *(float f, Color c) => c;
        public static Color Lerp(Color a, Color b, float t) => a;
        public static implicit operator Color(Color32 c) => default;
        public float maxColorComponent => 0f;
    }
    public struct Color32
    {
        public byte r, g, b, a;
        public Color32(byte r, byte g, byte b, byte a) { this.r = r; this.g = g; this.b = b; this.a = a; }
        public static implicit operator Color32(Color c) => default;
    }
    public struct Rect
    {
        public float x, y, width, height;
        public Rect(float x, float y, float w, float h) { this.x = x; this.y = y; width = w; height = h; }
        public float xMin => x; public float yMin => y; public float xMax => x + width; public float yMax => y + height;
        public Vector2 center => default; public Vector2 position => default; public Vector2 size => default;
        public bool Contains(Vector2 p) => false;
    }
    public struct Bounds
    {
        public Bounds(Vector3 c, Vector3 s) { center = c; size = s; }
        public Vector3 center { get; set; }
        public Vector3 size { get; set; }
        public Vector3 extents => default;
        public void Encapsulate(Bounds b) { }
    }
    public struct Ray { }
    public struct RaycastHit { public Collider collider => null; public Vector3 point => default; }
    public static class Physics { public static bool Raycast(Ray r, out RaycastHit h, float maxDistance) { h = default; return false; } }
    public static class Mathf
    {
        public const float PI = 3.14159265f;
        public const float Infinity = float.PositiveInfinity;
        public static float Clamp(float v, float a, float b) => v;
        public static int Clamp(int v, int a, int b) => v;
        public static float Clamp01(float v) => v;
        public static float Lerp(float a, float b, float t) => a;
        public static float InverseLerp(float a, float b, float v) => 0;
        public static float Max(float a, float b) => a;
        public static float Max(params float[] v) => 0;
        public static int Max(int a, int b) => a;
        public static float Min(float a, float b) => a;
        public static int Min(int a, int b) => a;
        public static float Abs(float a) => a;
        public static float Sign(float a) => a;
        public static float Sin(float a) => a;
        public static float Cos(float a) => a;
        public static float Sqrt(float a) => a;
        public static float Floor(float a) => a;
        public static float Ceil(float a) => a;
        public static float Round(float a) => a;
        public static int RoundToInt(float a) => 0;
        public static int FloorToInt(float a) => 0;
        public static int CeilToInt(float a) => 0;
        public static float Pow(float a, float b) => a;
        public static float Log10(float a) => a;
        public static float MoveTowards(float c, float t, float d) => c;
        public static float SmoothStep(float a, float b, float t) => a;
        public static float SmoothDamp(float c, float t, ref float v, float st, float ms, float dt) => c;
        public static float SmoothDampAngle(float c, float t, ref float v, float st, float ms, float dt) => c;
        public static bool Approximately(float a, float b) => a == b;
        public static float Repeat(float t, float l) => t;
        public static float PingPong(float t, float l) => t;
    }
    public static class Time { public static float deltaTime; public static float unscaledDeltaTime; public static float unscaledTime; public static float time; public static float realtimeSinceStartup; public static int frameCount; }
    public static class Application { public static bool isBatchMode; public static string dataPath; public static string streamingAssetsPath; public static string persistentDataPath; public static bool isPlaying; public static bool isEditor; public static string productName; public static string version; public static string unityVersion; }
    public static class Debug
    {
        public static void Log(object m) { } public static void LogWarning(object m) { } public static void LogError(object m) { } public static void LogException(Exception e) { }
    }
    public enum FullScreenMode { ExclusiveFullScreen, FullScreenWindow, MaximizedWindow, Windowed }
    public struct Resolution { public int width; public int height; }
    public static class Screen
    {
        public static int width; public static int height; public static float dpi;
        public static bool fullScreen { get; set; }
        public static FullScreenMode fullScreenMode { get; set; }
        public static Resolution currentResolution => default;
        public static void SetResolution(int width, int height, FullScreenMode mode) { }
    }
    public class Display { public static Display main => null; public int systemWidth => 0; public int systemHeight => 0; }
    public static class ScreenCapture { public static void CaptureScreenshot(string path) { } public static void CaptureScreenshot(string path, int superSize) { } }
    public enum KeyCode { None, F11, Space, LeftArrow, RightArrow, UpArrow, DownArrow, Home, End, Escape, LeftShift, RightShift, LeftControl, RightControl, Alpha1, Alpha2, Alpha3, Alpha4, Alpha5, Keypad1, Keypad2, Keypad3, Keypad4, Keypad5, A, B, C, D, E, F, G, H, I, J, K, L, M, N, O, P, Q, R, S, T, U, V, W, X, Y, Z }
    public class Camera : Behaviour
    {
        public static Camera main => null;
        public CameraClearFlags clearFlags { get; set; }
        public Color backgroundColor { get; set; }
        public float nearClipPlane { get; set; }
        public float farClipPlane { get; set; }
        public float fieldOfView { get; set; }
        public bool allowHDR { get; set; }
        public Vector3 WorldToViewportPoint(Vector3 p) => p;
        public Vector3 WorldToScreenPoint(Vector3 p) => p;
        public Ray ScreenPointToRay(Vector3 p) => default;
        public Matrix4x4 projectionMatrix { get; set; }
        public void ResetProjectionMatrix() { }
    }
    public struct Matrix4x4
    {
        public float m00, m01, m02, m03, m10, m11, m12, m13, m20, m21, m22, m23, m30, m31, m32, m33;
    }
    public class ReflectionProbe : Behaviour
    {
        public UnityEngine.Rendering.ReflectionProbeMode mode { get; set; }
        public UnityEngine.Rendering.ReflectionProbeRefreshMode refreshMode { get; set; }
        public UnityEngine.Rendering.ReflectionProbeTimeSlicingMode timeSlicingMode { get; set; }
        public Vector3 size { get; set; }
        public bool boxProjection { get; set; }
    }
    public class Texture : Object { }
    public class Texture2D : Texture { }
    public enum TextureWrapMode { Repeat, Clamp, Mirror, MirrorOnce }
    public enum FilterMode { Point, Bilinear, Trilinear }
    public class TextAsset : Object { public string text => null; public byte[] bytes => null; }
    public static class JsonUtility { public static T FromJson<T>(string json) => default; public static string ToJson(object o) => null; }
    public enum CursorLockMode { None, Locked, Confined }
    public static class Cursor { public static CursorLockMode lockState { get; set; } public static bool visible { get; set; } }
    public static class Input { public static bool GetKey(KeyCode k) => false; public static bool GetKeyDown(KeyCode k) => false; public static Vector3 mousePosition => default; public static float GetAxisRaw(string a) => 0f; public static Vector2 mouseScrollDelta => default; public static bool GetMouseButtonDown(int b) => false; public static bool GetMouseButtonUp(int b) => false; public static bool GetMouseButton(int b) => false; }
    public static class Resources { public static T Load<T>(string path) where T : Object => null; }
    public enum CameraClearFlags { Skybox = 1, SolidColor = 2, Depth = 3, Nothing = 4 }
    public class AudioListener : Behaviour { }
    public class Light : Behaviour
    {
        public LightType type { get; set; } public float intensity { get; set; } public Color color { get; set; }
        public LightShadows shadows { get; set; } public float range { get; set; } public float spotAngle { get; set; } public float innerSpotAngle { get; set; }
    }
    public enum LightType { Spot, Directional, Point }
    public enum LightShadows { None, Hard, Soft }
    public class Renderer : Component
    {
        public Material sharedMaterial { get; set; }
        public Material[] sharedMaterials { get; set; }
        public Material material { get; set; }
        public Bounds bounds => default;
        public bool enabled { get; set; }
        public UnityEngine.Rendering.ShadowCastingMode shadowCastingMode { get; set; }
        public void GetPropertyBlock(MaterialPropertyBlock b) { }
        public void SetPropertyBlock(MaterialPropertyBlock b) { }
    }
    public class MeshRenderer : Renderer { }
    public class MeshFilter : Component { public Mesh sharedMesh { get; set; } public Mesh mesh { get; set; } }
    public class Collider : Component { }
    public class MeshCollider : Collider { public Mesh sharedMesh { get; set; } }
    public class BoxCollider : Collider { }
    public sealed class Mesh : Object
    {
        public void Clear() { }
        public void SetVertices(List<Vector3> v) { }
        public void SetNormals(List<Vector3> v) { }
        public void SetTriangles(List<int> t, int sub) { }
        public void RecalculateBounds() { }
        public UnityEngine.Rendering.IndexFormat indexFormat { get; set; }
        public Vector3[] vertices { get; set; }
        public Vector3[] normals { get; set; }
        public Vector2[] uv { get; set; }
        public int[] triangles { get; set; }
        public void RecalculateNormals() { }
    }
    public class Shader : Object { public static Shader Find(string n) => null; public static int PropertyToID(string n) => 0; }
    public class Material : Object
    {
        public Material(Shader s) { }
        public Material(Material m) { }
        public Shader shader { get; set; }
        public int renderQueue { get; set; }
        public MaterialGlobalIlluminationFlags globalIlluminationFlags { get; set; }
        public bool HasProperty(string n) => false;
        public bool HasProperty(int id) => false;
        public Color GetColor(int id) => default;
        public Color GetColor(string n) => default;
        public void SetColor(string n, Color c) { }
        public void SetColor(int id, Color c) { }
        public void SetFloat(string n, float v) { }
        public void EnableKeyword(string k) { }
        public void DisableKeyword(string k) { }
        public void SetOverrideTag(string t, string v) { }
        public void SetTexture(string n, Texture t) { }
        public void SetShaderPassEnabled(string passName, bool enabled) { }
        public void SetTextureScale(string n, Vector2 s) { }
    }
    [Flags] public enum MaterialGlobalIlluminationFlags { None = 0, RealtimeEmissive = 1, BakedEmissive = 2, EmissiveIsBlack = 4 }
    public sealed class MaterialPropertyBlock { public void SetColor(int id, Color c) { } public void SetFloat(int id, float v) { } public void Clear() { } }
    public class Font : Object { }
    public static class RenderSettings
    {
        public static Material skybox { get; set; }
        public static UnityEngine.Rendering.AmbientMode ambientMode { get; set; }
        public static Color ambientSkyColor { get; set; } public static Color ambientEquatorColor { get; set; } public static Color ambientGroundColor { get; set; } public static Color ambientLight { get; set; }
    }
    public static class QualitySettings
    {
        public static string[] names => new string[0];
        public static int GetQualityLevel() => 0;
        public static void SetQualityLevel(int i, bool apply) { }
        public static UnityEngine.Rendering.RenderPipelineAsset renderPipeline { get; set; }
    }
    // ---- attributes
    public sealed class TooltipAttribute : Attribute { public TooltipAttribute(string t) { } }
    public sealed class RangeAttribute : Attribute { public RangeAttribute(float a, float b) { } }
    public sealed class ColorUsageAttribute : Attribute { public ColorUsageAttribute(bool alpha, bool hdr) { } }
    public sealed class TextAreaAttribute : Attribute { public TextAreaAttribute() { } public TextAreaAttribute(int a, int b) { } }
    public sealed class SerializeField : Attribute { }
    public sealed class HideInInspector : Attribute { }
    public sealed class HeaderAttribute : Attribute { public HeaderAttribute(string h) { } }
    public sealed class DisallowMultipleComponent : Attribute { }
    public sealed class ExecuteAlways : Attribute { }
    public sealed class RequireComponent : Attribute { public RequireComponent(Type a) { } public RequireComponent(Type a, Type b) { } }
    public sealed class DefaultExecutionOrder : Attribute { public DefaultExecutionOrder(int o) { } }
    public sealed class AddComponentMenu : Attribute { public AddComponentMenu(string m) { } }
}
namespace UnityEngine.SceneManagement
{
    public struct Scene { public string path => null; public bool isDirty => false; public string name => null; }
    public static class SceneManager { public static Scene GetActiveScene() => default; }
}

namespace UnityEngine.InputSystem
{
    namespace Controls { public class KeyControl { public bool wasPressedThisFrame => false; public bool isPressed => false; } }
    namespace Controls { public class ButtonControl { public bool wasPressedThisFrame => false; public bool wasReleasedThisFrame => false; public bool isPressed => false; } }
    public class Vector2Control { public Vector2 ReadValue() => default; }
    public class InputSettings { public enum ScrollDeltaBehavior { UniformAcrossAllPlatforms, KeepPlatformSpecificInputRange } public ScrollDeltaBehavior scrollDeltaBehavior { get; set; } }
    public static class InputSystem { public static InputSettings settings => null; }
    public class Mouse
    {
        public static Mouse current => null;
        public Vector2Control position => null; public Vector2Control delta => null; public Vector2Control scroll => null;
        public Controls.ButtonControl leftButton => null; public Controls.ButtonControl rightButton => null; public Controls.ButtonControl middleButton => null;
    }
    public class Keyboard
    {
        public static Keyboard current => null;
        public Controls.KeyControl wKey => null; public Controls.KeyControl aKey => null; public Controls.KeyControl rKey => null;
        public Controls.KeyControl leftCtrlKey => null; public Controls.KeyControl rightCtrlKey => null;
        public Controls.KeyControl leftShiftKey => null; public Controls.KeyControl rightShiftKey => null;
        public Controls.KeyControl shiftKey => null; public Controls.KeyControl spaceKey => null; public Controls.KeyControl leftArrowKey => null;
        public Controls.KeyControl rightArrowKey => null; public Controls.KeyControl homeKey => null; public Controls.KeyControl escapeKey => null;
        public Controls.KeyControl digit1Key => null; public Controls.KeyControl digit2Key => null; public Controls.KeyControl digit3Key => null;
        public Controls.KeyControl digit4Key => null; public Controls.KeyControl digit5Key => null;
        public Controls.KeyControl numpad1Key => null; public Controls.KeyControl numpad2Key => null; public Controls.KeyControl numpad3Key => null;
        public Controls.KeyControl numpad4Key => null; public Controls.KeyControl numpad5Key => null;
        public Controls.KeyControl tKey => null; public Controls.KeyControl fKey => null; public Controls.KeyControl sKey => null;
        public Controls.KeyControl cKey => null; public Controls.KeyControl pKey => null; public Controls.KeyControl bKey => null; public Controls.KeyControl dKey => null; public Controls.KeyControl mKey => null; public Controls.KeyControl f11Key => null;
    }
}
