"""Single source of truth for the URP material palette (exported to NERAM_Generated/MeshData/materials.json and read
by NeramSceneBuilder.cs). Colours are sRGB 0..1. Palette: deep blue/slate, white/soft grey, teal/cyan highlights,
amber for the foot channels and heater layers, red only for the physical STOP button and critical states.

emission_kw = True keeps the _EMISSION keyword enabled with black emission so the runtime can drive highlight/heater
glow per renderer with a MaterialPropertyBlock (replay-driven only)."""

M = {}


def mat(name, color, smooth=0.4, metal=0.0, alpha=1.0, emission=None, kw=False, texture="", tiling=1.0, emission_from_texture=0.0):
    M[name] = dict(name=name, color=[*color, alpha], smoothness=smooth, metallic=metal, emission=list(emission or (0, 0, 0)),
                   emissionKeyword=bool(kw or emission or emission_from_texture), texture=texture, tiling=tiling,
                   transparent=alpha < 1.0, emissionFromTexture=emission_from_texture)


# patient + wearables (all region materials keep the emission keyword for hover/selection highlight)
mat("MAT_Skin", (0.80, 0.68, 0.61), 0.26, kw=True)  # final release: slightly less sheen (silicone-like, not glossy)
mat("MAT_Gown", (0.50, 0.68, 0.78), 0.12, kw=True, texture="fabric_weave", tiling=14)
mat("MAT_Drape", (0.17, 0.40, 0.53), 0.10, kw=True, texture="fabric_weave", tiling=12)
mat("MAT_GloveFabric", (0.92, 0.93, 0.94), 0.18, kw=True, texture="fabric_weave", tiling=22)
mat("MAT_GloveCuff", (0.17, 0.24, 0.31), 0.32, kw=True)
mat("MAT_HeaterPanel", (0.86, 0.63, 0.38), 0.25, kw=True, texture="fabric_weave", tiling=22)
mat("MAT_HeaterLayer", (0.96, 0.62, 0.16), 0.42, kw=True)
mat("MAT_BootFabric", (0.80, 0.82, 0.84), 0.2, kw=True, texture="fabric_weave", tiling=18)
mat("MAT_BootTrim", (0.22, 0.29, 0.36), 0.35, kw=True)
mat("MAT_Midsole", (0.88, 0.89, 0.87), 0.25, kw=True)
mat("MAT_Outsole", (0.14, 0.16, 0.19), 0.22, kw=True)
mat("MAT_LabelPlate", (0.10, 0.13, 0.17), 0.5, kw=True)
mat("MAT_WatchBand", (0.13, 0.16, 0.20), 0.35, kw=True)
mat("MAT_WatchBody", (0.24, 0.29, 0.35), 0.72, 0.4, kw=True)
# CAD material list (docs/unity/CAD_INTEGRATION.md) - must exist even when not used by the generated meshes
mat("MAT_Liner", (0.82, 0.84, 0.87), 0.2, kw=True)
mat("MAT_Sensor", (0.10, 0.72, 0.78), 0.6, kw=True)
mat("MAT_Heater", (0.35, 0.18, 0.10), 0.3, kw=True)
mat("MAT_Insulation", (0.86, 0.86, 0.82), 0.15, kw=True)
mat("MAT_Shell", (0.55, 0.62, 0.70), 0.6, kw=True)
mat("MAT_Strap", (0.16, 0.20, 0.26), 0.3, kw=True)
mat("MAT_Cable", (0.11, 0.12, 0.14), 0.45)
mat("MAT_Connector", (0.66, 0.68, 0.72), 0.7, 0.6, kw=True)
mat("MAT_Enclosure", (0.90, 0.92, 0.94), 0.55, kw=True)
mat("MAT_Indicator", (0.04, 0.05, 0.06), 0.85, kw=True)
mat("MAT_Button_Start", (0.13, 0.62, 0.36), 0.5, kw=True)
mat("MAT_Button_Stop", (0.80, 0.18, 0.18), 0.5, kw=True)
mat("MAT_Button_Reset", (0.86, 0.60, 0.14), 0.5, kw=True)
# theatre
mat("MAT_Floor", (1.0, 1.0, 1.0), 0.55, texture="floor_tiles", tiling=1)
mat("MAT_Wall", (0.87, 0.90, 0.93), 0.22)
mat("MAT_WallSkirt", (0.25, 0.31, 0.38), 0.35)
mat("MAT_WallRail", (0.18, 0.40, 0.46), 0.5)
mat("MAT_Ceiling", (0.96, 0.97, 0.98), 0.2)
mat("MAT_CeilingPanel", (0.95, 0.97, 1.0), 0.2, emission=(0.75, 0.78, 0.82))
mat("MAT_CeilingLight", (0.95, 0.97, 1.0), 0.2, emission=(1.3, 1.32, 1.36))
mat("MAT_MetalWhite", (0.88, 0.90, 0.92), 0.6, 0.3)
mat("MAT_Metal", (0.72, 0.74, 0.77), 0.78, 0.9)
mat("MAT_Brass", (0.78, 0.62, 0.32), 0.7, 0.9)
mat("MAT_Door", (0.70, 0.76, 0.80), 0.4)
mat("MAT_GlassDark", (0.05, 0.08, 0.10), 0.95)
mat("MAT_EquipDark", (0.13, 0.16, 0.20), 0.5)
mat("MAT_ScreenOff", (0.02, 0.03, 0.04), 0.95)
mat("MAT_PanelWhite", (0.93, 0.94, 0.95), 0.45)
mat("MAT_EquipWhite", (0.90, 0.92, 0.93), 0.5)
mat("MAT_Teal", (0.08, 0.60, 0.60), 0.5)
mat("MAT_Worktop", (0.30, 0.35, 0.40), 0.5)
mat("MAT_TableFrame", (0.86, 0.88, 0.90), 0.6, 0.2)
mat("MAT_TablePad", (0.10, 0.15, 0.20), 0.35)
mat("MAT_LightHead", (0.93, 0.94, 0.95), 0.6)
mat("MAT_LightLens", (0.85, 0.88, 0.90), 0.9, emission=(0.6, 0.6, 0.58))
mat("MAT_LightCell", (1.0, 1.0, 1.0), 0.9, emission=(2.4, 2.35, 2.25))
mat("MAT_GlassClear", (0.75, 0.85, 0.90), 0.95, alpha=0.25)
mat("MAT_Bellows", (0.55, 0.65, 0.75), 0.4)
mat("MAT_VapA", (0.35, 0.45, 0.55), 0.5)
mat("MAT_VapB", (0.45, 0.50, 0.55), 0.5)
mat("MAT_Hose", (0.55, 0.72, 0.82), 0.6, alpha=0.85)
mat("MAT_IVBag", (0.88, 0.93, 0.97), 0.9, alpha=0.35)
mat("MAT_SuctionLid", (0.15, 0.42, 0.70), 0.5)
mat("MAT_O2Body", (0.94, 0.95, 0.96), 0.55)
mat("MAT_O2Shoulder", (0.99, 0.99, 0.99), 0.6)
mat("MAT_TableTop_Ref", (1.0, 0.0, 1.0), 0.0, alpha=0.35)
# Internal View: translucent ("ghost") body surfaces, illustrative vessels and pulses
mat("MAT_Skin_Ghost", (0.80, 0.69, 0.62), 0.3, alpha=0.16, kw=True)
mat("MAT_Gown_Ghost", (0.50, 0.68, 0.78), 0.1, alpha=0.12, kw=True)
mat("MAT_Drape_Ghost", (0.17, 0.40, 0.53), 0.1, alpha=0.10, kw=True)
mat("MAT_VesselArtery", (0.70, 0.17, 0.19), 0.55, kw=True)
mat("MAT_VesselVein", (0.20, 0.33, 0.70), 0.55, kw=True)
mat("MAT_Pulse", (1.0, 0.95, 0.95), 0.6, emission=(1.6, 1.4, 1.4))
# Thermal View: neutral surface whose colour is set per renderer from the patient-level signal
mat("MAT_Thermal", (1.0, 1.0, 1.0), 0.2, kw=True)
# IV set
mat("MAT_IVLiquid", (0.78, 0.88, 0.95), 0.9, alpha=0.6)
mat("MAT_IVDrop", (0.85, 0.93, 1.0), 0.95, alpha=0.75)
mat("MAT_Dressing", (0.96, 0.96, 0.96), 0.6, alpha=0.55)
mat("MAT_Cannula", (0.22, 0.62, 0.88), 0.6)

TEXTURE_MATERIALS = {
    # texture name -> emission strength (screens glow; labels do not)
    "label_ch1": 0.0, "label_ch2": 0.0, "label_ch3": 0.0, "label_ch4": 0.0, "label_controller": 0.0,
    "watch_face": 0.9, "screen_monitor": 0.7, "screen_vent": 0.7, "screen_pump": 0.7, "screen_anaesthesia": 0.7,
    "gas_panel": 0.0, "o2_label": 0.0, "gauge": 0.0, "iv_label": 0.0,
}
for tex, e in TEXTURE_MATERIALS.items():
    mat("MAT_TEX_" + tex, (1.0, 1.0, 1.0), 0.45, texture=tex, tiling=1, emission_from_texture=e)


def material_name(ref: str) -> str:
    return "MAT_TEX_" + ref[4:] if ref.startswith("TEX:") else ref


def preview_color(ref: str):
    name = material_name(ref)
    m = M.get(name)
    if m is None:
        return (1.0, 0.0, 1.0)
    c = m["color"][:3]
    if m["texture"] and name.startswith("MAT_TEX_"):
        return (0.55, 0.6, 0.66) if "screen" in name or "watch" in name else (0.82, 0.84, 0.86)
    if name == "MAT_Floor":
        return (0.38, 0.42, 0.48)
    return tuple(c)
