#pragma warning disable
using System;
using UnityEngine;
namespace UnityEditor
{
    public sealed class MenuItem : Attribute { public MenuItem(string p) { } public MenuItem(string p, bool validate) { } public int priority; }
    public static class EditorUtility
    {
        public static void RevealInFinder(string path) { }
        public static bool DisplayDialog(string t, string m, string ok) => true;
        public static bool DisplayDialog(string t, string m, string ok, string cancel) => true;
        public static void SetDirty(UnityEngine.Object o) { }
        public static void DisplayProgressBar(string t, string i, float p) { }
        public static void ClearProgressBar() { }
        public static string OpenFolderPanel(string title, string folder, string defaultName) => null;
    }
    public static class EditorPrefs
    {
        public static string GetString(string key, string defaultValue) => defaultValue;
        public static void SetString(string key, string value) { }
        public static void DeleteKey(string key) { }
    }
    public class SerializedProperty { public UnityEngine.Object objectReferenceValue { get; set; } }
    public class SerializedObject
    {
        public SerializedObject(UnityEngine.Object o) { }
        public SerializedProperty FindProperty(string path) => null;
        public bool ApplyModifiedPropertiesWithoutUndo() => true;
    }
    [Flags] public enum StaticEditorFlags { ContributeGI = 1, OccluderStatic = 2, BatchingStatic = 4, NavigationStatic = 8, OccludeeStatic = 16, OffMeshLinkGeneration = 32, ReflectionProbeStatic = 64 }
    public static class GameObjectUtility { public static void SetStaticEditorFlags(GameObject go, StaticEditorFlags flags) { } }
    public enum TextureImporterType { Default = 0, NormalMap = 1, GUI = 2, Sprite = 8, Cursor = 7, Cookie = 4, Lightmap = 6, SingleChannel = 10 }
    public static class AssetDatabase
    {
        public static T LoadAssetAtPath<T>(string p) where T : UnityEngine.Object => null;
        public static void CreateAsset(UnityEngine.Object o, string p) { }
        public static void AddObjectToAsset(UnityEngine.Object o, UnityEngine.Object asset) { }
        public static string GetAssetPath(UnityEngine.Object o) => null;
        public static void SaveAssets() { }
        public static void Refresh() { }
        public static string[] FindAssets(string filter, string[] folders) => new string[0];
        public static string GUIDToAssetPath(string g) => null;
        public static bool DeleteAsset(string path) => true;
        public static string MoveAsset(string oldPath, string newPath) => "";
    }
    public static class EditorApplication
    {
        public delegate void CallbackFunction();
        public static CallbackFunction delayCall;
        public static void Exit(int code) { }
        public static bool ExecuteMenuItem(string m) => false;
        public static bool isPlaying => false;
        public static bool isPlayingOrWillChangePlaymode => false;
        public static bool isCompiling => false;
        public static bool isUpdating => false;
    }
    public sealed class InitializeOnLoadAttribute : Attribute { }
    public static class SessionState { public static bool GetBool(string key, bool defaultValue) => defaultValue; public static void SetBool(string key, bool value) { } }
    public static class Selection { public static UnityEngine.Object[] objects => new UnityEngine.Object[0]; public static GameObject activeGameObject { get; set; } }
    public static class Undo
    {
        public static void DestroyObjectImmediate(UnityEngine.Object o) { }
        public static void RegisterCreatedObjectUndo(UnityEngine.Object o, string n) { }
        public static void RecordObject(UnityEngine.Object o, string n) { }
    }
    public static class PrefabUtility { public static UnityEngine.Object InstantiatePrefab(UnityEngine.Object o, Transform parent) => null; }
    public class AssetImporter : UnityEngine.Object { public string assetPath => null; public static AssetImporter GetAtPath(string path) => null; public void SaveAndReimport() { } }
    public class TextureImporter : AssetImporter
    {
        public TextureImporterType textureType { get; set; } public bool sRGBTexture { get; set; } public bool mipmapEnabled { get; set; }
        public TextureWrapMode wrapMode { get; set; } public FilterMode filterMode { get; set; } public int anisoLevel { get; set; }
    }
    public enum ModelImporterMaterialImportMode { None, ImportStandard, ImportViaMaterialDescription }
    public enum ModelImporterMaterialLocation { External, InPrefab }
    public class ModelImporter : AssetImporter
    {
        public float globalScale { get; set; } public bool useFileScale { get; set; } public bool bakeAxisConversion { get; set; }
        public bool importAnimation { get; set; } public bool importCameras { get; set; } public bool importLights { get; set; }
        public bool isReadable { get; set; } public bool addCollider { get; set; }
        public ModelImporterMaterialImportMode materialImportMode { get; set; } public ModelImporterMaterialLocation materialLocation { get; set; }
    }
    public class AssetPostprocessor { public string assetPath => null; public AssetImporter assetImporter => null; }
    public class EditorBuildSettingsScene { public EditorBuildSettingsScene(string path, bool enabled) { } public string path => null; public bool enabled => true; }
    public static class EditorBuildSettings { public static EditorBuildSettingsScene[] scenes { get; set; } }
}
namespace UnityEditor.SceneManagement
{
    public enum NewSceneSetup { EmptyScene, DefaultGameObjects }
    public enum NewSceneMode { Single, Additive }
    public enum OpenSceneMode { Single, Additive }
    public static class EditorSceneManager
    {
        public static UnityEngine.SceneManagement.Scene NewScene(NewSceneSetup s, NewSceneMode m) => default;
        public static UnityEngine.SceneManagement.Scene OpenScene(string p, OpenSceneMode m = OpenSceneMode.Single) => default;
        public static bool SaveScene(UnityEngine.SceneManagement.Scene s, string p) => true;
        public static bool MarkSceneDirty(UnityEngine.SceneManagement.Scene s) => true;
        public static bool SaveCurrentModifiedScenesIfUserWantsTo() => true;
        public static UnityEngine.SceneManagement.Scene GetActiveScene() => default;
    }
}

namespace UnityEditor
{
    public enum BuildTarget { StandaloneWindows64 = 19 }
    [System.Flags] public enum BuildOptions { None = 0 }
    public struct BuildPlayerOptions { public string[] scenes; public string locationPathName; public BuildTarget target; public BuildOptions options; }
    public static class BuildPipeline { public static Build.Reporting.BuildReport BuildPlayer(BuildPlayerOptions o) => null; }
    public static class PlayerSettings
    {
        public static string productName { get; set; }
        public static UnityEngine.FullScreenMode fullScreenMode { get; set; }
        public static bool defaultIsNativeResolution { get; set; }
        public static bool resizableWindow { get; set; }
        public static bool runInBackground { get; set; }
        public static bool visibleInBackground { get; set; }
        public static int defaultScreenWidth { get; set; }
        public static int defaultScreenHeight { get; set; }
    }
}
namespace UnityEditor.Build.Reporting
{
    public enum BuildResult { Unknown, Succeeded, Failed, Cancelled }
    public struct BuildSummary { public BuildResult result; public ulong totalSize; public System.TimeSpan totalTime; public int totalErrors; }
    public class BuildReport { public BuildSummary summary => default; }
}
