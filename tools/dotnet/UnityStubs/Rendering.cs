#pragma warning disable
using System;
namespace UnityEngine.Rendering
{
    public enum ShadowCastingMode { Off, On, TwoSided, ShadowsOnly }
    public enum AmbientMode { Skybox = 0, Trilight = 1, Flat = 3, Custom = 4 }
    public enum CullMode { Off = 0, Front = 1, Back = 2 }
    public enum BlendMode { Zero = 0, One = 1, DstColor = 2, SrcColor = 3, OneMinusDstColor = 4, SrcAlpha = 5, OneMinusSrcColor = 6, DstAlpha = 7, OneMinusDstAlpha = 8, SrcAlphaSaturate = 9, OneMinusSrcAlpha = 10 }
    public enum RenderQueue { Background = 1000, Geometry = 2000, AlphaTest = 2450, Transparent = 3000, Overlay = 4000 }
    public abstract class RenderPipelineAsset : ScriptableObject { }
    public static class GraphicsSettings { public static RenderPipelineAsset defaultRenderPipeline { get; set; } public static RenderPipelineAsset currentRenderPipeline => null; }
    public class VolumeParameter<T> { public T value { get; set; } public void Override(T v) { } }
    public class ClampedFloatParameter : VolumeParameter<float> { }
    public class MinFloatParameter : VolumeParameter<float> { }
    public class VolumeComponent : ScriptableObject { }
    public class VolumeProfile : ScriptableObject
    {
        public T Add<T>(bool overrides = false) where T : VolumeComponent => default;
        public bool TryGet<T>(out T component) where T : VolumeComponent { component = default; return false; }
    }
    public enum IndexFormat { UInt16 = 0, UInt32 = 1 }
    public enum ReflectionProbeMode { Baked = 0, Realtime = 1, Custom = 2 }
    public enum ReflectionProbeRefreshMode { OnAwake = 0, EveryFrame = 1, ViaScripting = 2 }
    public enum ReflectionProbeTimeSlicingMode { AllFacesAtOnce = 0, IndividualFaces = 1, NoTimeSlicing = 2 }
    public class Volume : MonoBehaviour { public bool isGlobal { get; set; } public VolumeProfile sharedProfile { get; set; } public float priority { get; set; } }
}
namespace UnityEngine.Rendering.Universal
{
    public abstract class ScriptableRendererData : ScriptableObject { }
    public class PostProcessData : ScriptableObject { }
    public class UniversalRendererData : ScriptableRendererData { public PostProcessData postProcessData; }
    public class UniversalRenderPipelineAsset : RenderPipelineAsset
    {
        public static UniversalRenderPipelineAsset Create(ScriptableRendererData rendererData = null) => null;
        public bool supportsHDR { get; set; } public int msaaSampleCount { get; set; }
    }
    public enum AntialiasingMode { None, FastApproximateAntialiasing, SubpixelMorphologicalAntiAliasing, TemporalAntiAliasing }
    public enum AntialiasingQuality { Low, Medium, High }
    public class UniversalAdditionalCameraData : MonoBehaviour { public bool renderPostProcessing { get; set; } public AntialiasingMode antialiasing { get; set; } public AntialiasingQuality antialiasingQuality { get; set; } }
    public sealed class Vignette : VolumeComponent { public ClampedFloatParameter intensity; public ClampedFloatParameter smoothness; }
    public sealed class Bloom : VolumeComponent { public MinFloatParameter threshold; public MinFloatParameter intensity; public ClampedFloatParameter scatter; }
    public enum TonemappingMode { None, Neutral, ACES }
    public sealed class TonemappingModeParameter : VolumeParameter<TonemappingMode> { }
    public sealed class Tonemapping : VolumeComponent { public TonemappingModeParameter mode; }
}
