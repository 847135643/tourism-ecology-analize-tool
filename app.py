"""
川西旅游生态冲突预警与规划辅助平台
Western Sichuan Tourism-Ecology Conflict Early Warning & Planning Tool

运行方式:
    cd tool/
    pip install -r requirements.txt
    streamlit run app.py
"""

import streamlit as st
import folium
from folium import raster_layers, GeoJson, LayerControl
import rasterio
from rasterio.warp import transform_bounds
from rasterio.features import rasterize
from rasterio.crs import CRS
import geopandas as gpd
import numpy as np
import pandas as pd
import json
import io
import base64
import tempfile
import os
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib import rcParams
from PIL import Image as PILImage
import warnings
warnings.filterwarnings('ignore')

# 临时目录（跨平台）
TMP_DIR = tempfile.gettempdir()

# ========== 页面配置 ==========
st.set_page_config(
    page_title="川西旅游生态冲突预警平台",
    page_icon="🏔️",
    layout="wide"
)

# ========== 中文字体 ==========
try:
    plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
except:
    pass

# ========== 路径配置 ==========
DATA_DIR = Path(__file__).parent / "data"
RASTER_DIR = DATA_DIR

# 关键栅格文件
RASTERS = {
    "conflict_4class": str(RASTER_DIR / "TDPI叠加后的一级、二级、三级管理优先区" / "HAI_EQI_conflict_4class_1km.tif"),
    "mgmt_priority": str(RASTER_DIR / "TDPI叠加后的一级、二级、三级管理优先区" / "management_priority_3class_1km.tif"),
    "tdpi": str(RASTER_DIR / "TDPI叠加后的一级、二级、三级管理优先区" / "TDPI_v02_aligned_1km.tif"),
    "tdpi_level": str(RASTER_DIR / "TDPI叠加后的一级、二级、三级管理优先区" / "TDPI_level_1km.tif"),
    "hai": str(RASTER_DIR / "HAI" / "HAI_阿坝甘孜_1km_20260809.tif"),
    "eqi": str(RASTER_DIR / "EQI" / "EQI_v02_bbox_1km.tif"),
    "eqi_residual": str(RASTER_DIR / "02_EQI_natural_adjusted_residual.tif"),
    "relationship_class": str(RASTER_DIR / "06_TDPI_EQI_adjusted_relationship_class.tif"),
    "eqi_expected": str(RASTER_DIR / "01_EQI_expected_from_natural_background.tif"),
}

# EQI 分量栅格
EQI_COMPONENTS = {
    "BRI (生物多样性)": str(RASTER_DIR / "EQI" / "components" / "BRI_norm_1km.tif"),
    "FVC (植被覆盖)": str(RASTER_DIR / "EQI" / "components" / "FVC_1km.tif"),
    "WATER (水源涵养)": str(RASTER_DIR / "EQI" / "components" / "WATER_norm_1km.tif"),
    "PM2.5 (空气质量)": str(RASTER_DIR / "EQI" / "components" / "PM25_reverse_norm_1km.tif"),
    "EROSION (土壤侵蚀)": str(RASTER_DIR / "EQI" / "components" / "EROSION_quality_1km.tif"),
}

# 县域统计数据
COUNTY_GEOJSON = str(RASTER_DIR / "县域旅游生态治理优先级" / "03_表格与矢量" / "县域管理优先区统计.geojson")
COUNTY_CSV = str(RASTER_DIR / "县域旅游生态治理优先级" / "03_表格与矢量" / "县域管理优先区统计.csv")

# 分析元数据
with open(str(RASTER_DIR / "TDPI叠加后的一级、二级、三级管理优先区" / "conflict_priority_stats.json"), encoding='utf-8') as f:
    CONFLICT_STATS = json.load(f)
with open(str(RASTER_DIR / "controlled_analysis_summary.json"), encoding='utf-8') as f:
    CONTROLLED_STATS = json.load(f)

# ========== 颜色方案 ==========
CONFLICT_COLORS = {
    1: '#2E86AB',  # 低HAI-高EQI: 生态优良区 (蓝绿)
    2: '#A23B72',  # 高HAI-高EQI: 协调发展区 (紫)
    3: '#F18F01',  # 低HAI-低EQI: 自然限制区 (橙)
    4: '#C73E1D',  # 高HAI-低EQI: 冲突预警区 (红)
}

CONFLICT_LABELS = {
    1: "低压力-高生态 (生态优良区)",
    2: "高压力-高生态 (协调发展区)",
    3: "低压力-低生态 (自然限制区)",
    4: "高压力-低生态 ⚠️ 冲突预警区",
}

MGMT_COLORS = {1: '#C73E1D', 2: '#F18F01', 3: '#7FB069'}
MGMT_LABELS = {1: "一级优先 (立即管控)", 2: "二级优先 (动态监测)", 3: "三级优先 (一般管理)"}

RISK_COLORS_4 = ['#7FB069', '#F5D547', '#F18F01', '#C73E1D']
RISK_LABELS_4 = ['低风险', '中等风险', '中高风险', '高风险']

# ========== Session State 初始化 ==========
if 'selected_county' not in st.session_state:
    st.session_state['selected_county'] = None
if 'live_sub_mode' not in st.session_state:
    st.session_state['live_sub_mode'] = "上传数据做县域统计"
if 'uploaded_raster_stats' not in st.session_state:
    st.session_state['uploaded_raster_stats'] = None
if 'uploaded_raster_name' not in st.session_state:
    st.session_state['uploaded_raster_name'] = None

# ========== 缓存数据加载 ==========
@st.cache_data
def load_county_data():
    """加载县域统计数据"""
    gdf = gpd.read_file(COUNTY_GEOJSON)
    df = pd.read_csv(COUNTY_CSV)
    df_ranked = df[df['ranking_eligible'] == 1].copy()
    return gdf, df_ranked

@st.cache_data
def load_county_gdf():
    """加载县域边界 GeoDataFrame（用于分区统计）"""
    gdf = gpd.read_file(COUNTY_GEOJSON)
    return gdf

@st.cache_data
def read_raster_array(path):
    """读取栅格为 numpy 数组（缓存）"""
    with rasterio.open(path) as src:
        data = src.read(1)
        nodata = src.nodata
        crs = str(src.crs)
        transform = list(src.transform)
    return data, nodata, crs, transform

@st.cache_data
def get_raster_bounds_wgs84(path):
    """获取栅格的 WGS84 范围"""
    with rasterio.open(path) as src:
        return transform_bounds(src.crs, 'EPSG:4326', *src.bounds)

# ========== 辅助函数 ==========
def classify_risk(priority_index):
    """根据优先级指数返回风险等级"""
    if priority_index > 0.20:
        return 3, "🔴 高风险", '#C73E1D'
    elif priority_index > 0.10:
        return 2, "🟠 中高风险", '#F18F01'
    elif priority_index > 0.05:
        return 1, "🟡 中等风险", '#F5D547'
    else:
        return 0, "🟢 低风险", '#7FB069'

def county_risk_color(priority_index):
    """返回风险颜色"""
    if priority_index > 0.20:
        return '#C73E1D'
    elif priority_index > 0.10:
        return '#F18F01'
    elif priority_index > 0.05:
        return '#F5D547'
    else:
        return '#7FB069'

def create_base_map(center=[30.5, 101.5], zoom=7):
    """创建基础 Folium 地图"""
    return folium.Map(
        location=center, zoom_start=zoom,
        tiles='CartoDB positron', control_scale=True, prefer_canvas=True
    )

def zonal_stats_by_county(raster_path, county_gdf):
    """
    对任意栅格按县域做分区统计。
    返回 DataFrame，每行一个县，包含 mean/std/min/max/sum/count。
    """
    with rasterio.open(raster_path) as src:
        data = src.read(1).astype(np.float64)
        nodata = src.nodata
        transform = src.transform

    # 处理 NoData
    if nodata is not None:
        valid_mask = data != nodata
    else:
        valid_mask = np.ones(data.shape, dtype=bool)

    # 将县界几何投影到栅格 CRS，再 rasterize 为掩膜
    with rasterio.open(raster_path) as src:
        raster_crs = src.crs
    county_gdf_proj = county_gdf.to_crs(raster_crs)

    results = []
    for idx, row in county_gdf_proj.iterrows():
        geom = row.geometry
        county_name = row.get('name', f'County_{idx}')

        if geom is None or geom.is_empty:
            results.append({'name': county_name, 'mean': np.nan, 'std': np.nan,
                           'min': np.nan, 'max': np.nan, 'sum': np.nan, 'count': 0})
            continue

        try:
            mask = rasterize(
                [(geom, 1)],
                out_shape=data.shape,
                transform=transform,
                fill=0,
                all_touched=True
            ).astype(bool)

            county_mask = mask & valid_mask
            values = data[county_mask]

            if len(values) > 0:
                results.append({
                    'name': county_name,
                    'mean': float(np.mean(values)),
                    'std': float(np.std(values)),
                    'min': float(np.min(values)),
                    'max': float(np.max(values)),
                    'sum': float(np.sum(values)),
                    'count': int(len(values)),
                })
            else:
                results.append({'name': county_name, 'mean': np.nan, 'std': np.nan,
                               'min': np.nan, 'max': np.nan, 'sum': np.nan, 'count': 0})
        except Exception:
            results.append({'name': county_name, 'mean': np.nan, 'std': np.nan,
                           'min': np.nan, 'max': np.nan, 'sum': np.nan, 'count': 0})

    return pd.DataFrame(results)

def generate_smart_diagnosis(row, stats_df, conflict_stats_local=None):
    """
    根据县域数据自动生成智能诊断文本。
    row: 该县的 CSV 行
    """
    diagnoses = []
    name = row['name']
    pi = row['priority_index']
    l1 = row['level_1_share']
    tdpi_h = row['tdpi_high_share']

    # 风险等级判断
    if pi > 0.20:
        diagnoses.append(f"⚠️ **{name}** 治理优先级指数 {pi:.4f}，为**高风险**县（全州排名 #{int(row['rank'])}）。")
    elif pi > 0.10:
        diagnoses.append(f"🟠 **{name}** 治理优先级指数 {pi:.4f}，为**中高风险**县（全州排名 #{int(row['rank'])}）。")
    else:
        diagnoses.append(f"✅ **{name}** 治理优先级指数 {pi:.4f}，风险相对可控（全州排名 #{int(row['rank'])}）。")

    # 一级优先区诊断
    if l1 > 0.03:
        diagnoses.append(f"🔴 一级优先管控区占比 **{l1*100:.1f}%**，面积 {int(row['level_1_area_km2'])} km²，"
                        f"已接近或超过全州高警戒水平，需立即管控。")
    elif l1 > 0.02:
        diagnoses.append(f"🟡 一级优先管控区占比 {l1*100:.1f}%，处于中等水平，建议动态跟踪。")
    else:
        diagnoses.append(f"✅ 一级优先管控区占比仅 {l1*100:.1f}%，冲突面积较小。")

    # TDPI 诊断
    if tdpi_h > 0.05:
        diagnoses.append(f"🔴 旅游高压力区（TDPI 高值）占比 **{tdpi_h*100:.1f}%**，面积 {int(row['tdpi_high_area_km2'])} km²，"
                        f"旅游活动对生态的压力较为突出。")
    elif tdpi_h > 0.03:
        diagnoses.append(f"🟡 旅游高压力区占比 {tdpi_h*100:.1f}%，存在一定旅游压力。")
    else:
        diagnoses.append(f"✅ 旅游高压力区占比 {tdpi_h*100:.1f}%，旅游活动强度整体可控。")

    # 候选阈值判断
    threshold = CONTROLLED_STATS['candidate_piecewise_change']['natural_only']['threshold_tdpi']
    if tdpi_h * 100 > threshold * 100:
        diagnoses.append(f"⚠️ 该县 TDPI 高值区占比已超过结构变化候选阈值 (TDPI≈{threshold:.3f})，生态质量可能开始转为负向偏离。")

    return diagnoses

def generate_governance_report(county_name, row, diagnoses):
    """生成治理建议文本"""
    lines = [
        f"# {county_name} 旅游生态风险评估简报",
        f"",
        f"## 基本信息",
        f"- 治理排名: #{int(row['rank'])} / 31",
        f"- 优先级指数: {row['priority_index']:.4f}",
        f"- 有效分析面积: {int(row['valid_area_km2'])} km²",
        f"",
        f"## 管理优先区统计",
        f"- 一级优先区 (立即管控): {int(row['level_1_area_km2'])} km² ({row['level_1_share']*100:.1f}%)",
        f"- 二级优先区 (动态监测): {int(row['level_2_area_km2'])} km² ({row['level_2_share']*100:.1f}%)",
        f"- 三级优先区 (一般管理): {int(row['level_3_area_km2'])} km² ({row['level_3_share']*100:.1f}%)",
        f"- TDPI 高值区: {int(row['tdpi_high_area_km2'])} km² ({row['tdpi_high_share']*100:.1f}%)",
        f"",
        f"## 智能诊断",
    ]
    for d in diagnoses:
        lines.append(f"- {d}")
    lines += [
        f"",
        f"## 治理建议",
    ]

    pi = row['priority_index']
    if pi > 0.20:
        lines += [
            f"1. **暂停新建大型旅游项目审批**：一级区占比 {row['level_1_share']*100:.1f}%，"
            f"已超出安全阈值，优先控制旅游活动强度。",
            f"2. **现有景区容量管控**：对景区设置日接待上限，限制旺季过度开发。",
            f"3. **受损生态修复优先**：在一级优先区内启动植被恢复与侵蚀治理。",
            f"4. **建立月级遥感监测**：利用 Sentinel-2 每月跟踪关键生态指标变化。",
        ]
    elif pi > 0.10:
        lines += [
            f"1. **新项目须过生态影响评估**：对拟建旅游项目进行生态风险评估。",
            f"2. **划定旅游活动缓冲区**：在景区周边设置梯级缓冲带。",
            f"3. **年度生态评估**：每年更新一次 EQI/TDPI 分析。",
            f"4. **监控 TDPI 趋势**：若 TDPI 高值区继续扩大，上调风险等级。",
        ]
    else:
        lines += [
            f"1. **维持现有保护措施**：当前旅游-生态协调良好。",
            f"2. **推广生态旅游模式**：适合发展低密度、高品质生态旅游。",
            f"3. **定期评估不放松**：每 2-3 年更新一次数据。",
        ]

    return '\n'.join(lines)

# ========== 预计算数据模式 ==========
def render_precomputed_mode():
    """渲染预计算数据展示模式（现有功能 + 增强）"""
    gdf, df_ranked = load_county_data()

    # ---- Top KPI Row ----
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("🏘️ 纳入分析县域", "31个", "门槛≥100km²")
    with col2:
        conflict_pct = CONFLICT_STATS.get('class_4_share', 0.05) * 100
        st.metric("⚠️ 冲突预警区", f"{conflict_pct:.1f}%")
    with col3:
        tdpi_pos = CONTROLLED_STATS['counts']['tdpi_positive_share'] * 100
        st.metric("🎯 旅游压力区", f"{tdpi_pos:.1f}%")
    with col4:
        st.metric("📐 分析分辨率", "1 km", "EPSG:6933 等面积")
    with col5:
        threshold = CONTROLLED_STATS['candidate_piecewise_change']['natural_only']['threshold_tdpi']
        st.metric("🔬 TDPI候选阈值", f"{threshold:.3f}", "ΔAIC=-9.49")

    # ---- Sidebar: 风险排名 ----
    with st.sidebar:
        st.markdown("### 📊 县域风险排名")
        sort_opt = st.radio("排序方式", ["按治理排名", "按风险等级", "按名称"],
                           horizontal=True, label_visibility="collapsed")
        search_term = st.text_input("🔍 搜索县名", placeholder="输入县名筛选...",
                                    label_visibility="collapsed")

        if sort_opt == "按治理排名":
            disp_df = df_ranked.sort_values('rank')
        elif sort_opt == "按风险等级":
            disp_df = df_ranked.sort_values('priority_index', ascending=False)
        else:
            disp_df = df_ranked.sort_values('name')

        if search_term:
            disp_df = disp_df[disp_df['name'].str.contains(search_term)]

        st.markdown(f"共 **{len(disp_df)}** 县")
        st.markdown("---")

        for _, r in disp_df.iterrows():
            color = county_risk_color(r['priority_index'])
            if r['priority_index'] > 0.20:
                emoji = "🔴"
            elif r['priority_index'] > 0.10:
                emoji = "🟠"
            elif r['priority_index'] > 0.05:
                emoji = "🟡"
            else:
                emoji = "🟢"

            btn_label = f"{emoji} #{int(r['rank'])} {r['name']}  {r['priority_index']:.3f}"
            if st.button(btn_label, key=f"side_{r['name']}", use_container_width=True,
                        help=f"点击查看 {r['name']} 详细诊断"):
                st.session_state['selected_county'] = r['name']

    # ---- Tabs ----
    tab_map, tab_county, tab_warning, tab_about = st.tabs([
        "🗺️ 交互地图", "🏛️ 县域诊断", "⚠️ 预警面板", "📋 关于平台"
    ])

    # ===== Tab 1: 交互地图 =====
    with tab_map:
        st.subheader("川西旅游生态冲突空间分布")

        col_left, col_right = st.columns([3, 1])

        with col_right:
            layer_choice = st.radio(
                "选择图层",
                ["四类冲突分区", "三级管理优先区", "TDPI旅游压力",
                 "HAI人类活动强度", "EQI生态质量", "自然校正EQI残差",
                 "校正后TDPI-EQI关系分类"],
                index=0
            )

            if layer_choice == "四类冲突分区":
                st.markdown("**图例**")
                for k, v in CONFLICT_LABELS.items():
                    st.markdown(f'<span style="color:{CONFLICT_COLORS[k]}">●</span> {v}',
                              unsafe_allow_html=True)
                st.info("💡 红色区域 = 应限制新增旅游开发")

            elif layer_choice == "三级管理优先区":
                st.markdown("**图例**")
                st.markdown('🔴 **一级**: 冲突+TDPI高 → 立即管控')
                st.markdown('🟠 **二级**: 冲突+TDPI中低 → 动态监测')
                st.markdown('🟢 **三级**: 一般管理背景')

            elif layer_choice == "校正后TDPI-EQI关系分类":
                threshold = CONTROLLED_STATS['candidate_piecewise_change']['natural_only']['threshold_tdpi']
                st.markdown("**自然本底控制后的关系分类**")
                st.markdown("1: TDPI=0 (无旅游压力)")
                st.markdown("2: TDPI≤阈值, 残差≥0 (协调)")
                st.markdown("3: TDPI≤阈值, 残差<0 (轻度压力)")
                st.markdown("4: TDPI>阈值, 残差≥0 (高压力-高生态)")
                st.markdown("5: TDPI>阈值, 残差<0 ⚠️ (高压力-低生态)")
                st.caption(f"候选阈值: TDPI ≈ {threshold:.3f}")

            show_counties = st.checkbox("叠加县域边界", True)

        with col_left:
            m = create_base_map()

            raster_key_map = {
                "四类冲突分区": "conflict_4class",
                "三级管理优先区": "mgmt_priority",
                "TDPI旅游压力": "tdpi",
                "HAI人类活动强度": "hai",
                "EQI生态质量": "eqi",
                "自然校正EQI残差": "eqi_residual",
                "校正后TDPI-EQI关系分类": "relationship_class",
            }

            raster_file = RASTERS.get(raster_key_map.get(layer_choice, "conflict_4class"))

            if raster_file and Path(raster_file).exists():
                with rasterio.open(raster_file) as src:
                    arr = src.read(1)
                    w, s, e, n = transform_bounds(src.crs, 'EPSG:4326', *src.bounds)

                if layer_choice == "四类冲突分区":
                    rgba = np.zeros((arr.shape[0], arr.shape[1], 4), dtype=np.uint8)
                    color_map_rgb = {1: (46,134,171), 2: (162,59,114),
                                   3: (241,143,1), 4: (199,62,29)}
                    for val, rgb in color_map_rgb.items():
                        mask = (arr == val)
                        rgba[mask, 0], rgba[mask, 1], rgba[mask, 2] = rgb
                        rgba[mask, 3] = 200
                    import os
                    tmp_conflict = os.path.join(TMP_DIR, 'conflict_overlay.png')
                    img = PILImage.fromarray(rgba[:, ::-1, :])
                    img.save(tmp_conflict)
                    folium.raster_layers.ImageOverlay(
                        image=tmp_conflict,
                        bounds=[[s, w], [n, e]], opacity=0.7, name='冲突分区'
                    ).add_to(m)

                elif layer_choice == "三级管理优先区":
                    rgba = np.zeros((arr.shape[0], arr.shape[1], 4), dtype=np.uint8)
                    for val, rgb in {1:(199,62,29), 2:(241,143,1), 3:(127,176,105)}.items():
                        mask = (arr == val)
                        rgba[mask, 0], rgba[mask, 1], rgba[mask, 2] = rgb
                        rgba[mask, 3] = 200
                    import os
                    tmp_mgmt = os.path.join(TMP_DIR, 'mgmt_overlay.png')
                    img = PILImage.fromarray(rgba[:, ::-1, :])
                    img.save(tmp_mgmt)
                    folium.raster_layers.ImageOverlay(
                        image=tmp_mgmt,
                        bounds=[[s, w], [n, e]], opacity=0.7, name='管理优先区'
                    ).add_to(m)

            # 叠加县域边界
            if show_counties and not gdf.empty:
                county_style = lambda x: {
                    'fillColor': county_risk_color(x['properties'].get('priority_index', 0)),
                    'color': '#333333', 'weight': 0.5, 'fillOpacity': 0.15
                }
                folium.GeoJson(
                    gdf.__geo_interface__,
                    style_function=county_style,
                    tooltip=folium.GeoJsonTooltip(
                        fields=['name', 'rank', 'priority_index', 'level_1_share'],
                        aliases=['县名', '治理排名', '优先级指数', '一级区占比'],
                        localize=True
                    ),
                    name='县域边界'
                ).add_to(m)

            st.components.v1.html(m._repr_html_(), height=550)
            st.caption(f"当前图层: {layer_choice} | 坐标参考: EPSG:6933 (1km) → 显示: WGS84")

    # ===== Tab 2: 县域诊断 (增强版) =====
    with tab_county:
        st.subheader("🏛️ 县域旅游生态风险诊断")

        # 如果侧边栏点了县名，自动选中
        selected_idx = None
        county_names = df_ranked['name'].tolist()
        if st.session_state.get('selected_county'):
            for i, n in enumerate(county_names):
                if n == st.session_state['selected_county']:
                    selected_idx = i
                    break

        col_sel, col_info = st.columns([1, 2])

        with col_sel:
            county_choice_idx = st.selectbox(
                "选择县域（按治理优先级排序）",
                range(len(county_names)),
                format_func=lambda i: f"#{int(df_ranked.iloc[i]['rank'])} {county_names[i]}",
                index=selected_idx if selected_idx is not None else 0
            )

            if county_choice_idx is not None:
                row = df_ranked.iloc[county_choice_idx]
                risk_lvl, risk_label, risk_color = classify_risk(row['priority_index'])

                st.markdown(f"## {risk_label}")
                st.metric("治理优先级指数", f"{row['priority_index']:.4f}")
                st.metric("全州排名", f"#{int(row['rank'])} / 31")
                st.metric("有效分析面积", f"{int(row['valid_area_km2'])} km²")

                # TDPI vs 阈值距离
                threshold = CONTROLLED_STATS['candidate_piecewise_change']['natural_only']['threshold_tdpi']
                tdpi_over_threshold = row['tdpi_high_share'] * 100
                st.metric("TDPI高值区占比", f"{tdpi_over_threshold:.1f}%",
                         delta=f"阈值 {threshold*100:.1f}%",
                         delta_color="inverse")

        with col_info:
            if county_choice_idx is not None:
                row = df_ranked.iloc[county_choice_idx]
                cname = county_names[county_choice_idx]

                # --- 图表行1: 管理优先区柱状图 + 冲突分区饼图 ---
                fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))

                # 左: 管理优先区面积
                categories = ['一级优先区', '二级优先区', '三级优先区']
                areas = [row['level_1_area_km2'], row['level_2_area_km2'], row['level_3_area_km2']]
                colors_bar = ['#C73E1D', '#F18F01', '#7FB069']
                ax1.bar(categories, areas, color=colors_bar)
                ax1.set_ylabel('面积 (km²)')
                ax1.set_title(f'{cname} 管理优先区面积')
                for i, v in enumerate(areas):
                    ax1.text(i, v + max(areas)*0.02, f'{v:.0f}', ha='center', fontsize=9)

                # 右: 冲突分区饼图（从冲突栅格裁剪）
                try:
                    conflict_path = RASTERS['conflict_4class']
                    gdf_local, _ = load_county_data()
                    target_geom = gdf_local[gdf_local['name'] == cname].geometry

                    if len(target_geom) > 0:
                        with rasterio.open(conflict_path) as src:
                            # 将县界几何投影到栅格 CRS
                            gdf_proj = gpd.GeoDataFrame(geometry=[target_geom.iloc[0]], crs=gdf_local.crs).to_crs(src.crs)
                            geom_proj = gdf_proj.geometry.iloc[0]
                            mask = rasterize([(geom_proj, 1)], out_shape=(src.height, src.width),
                                           transform=src.transform, fill=0, all_touched=True).astype(bool)
                            arr_clip = src.read(1)[mask]
                            valid = arr_clip[(arr_clip > 0) & (arr_clip != src.nodata)]

                        if len(valid) > 0:
                            counts = [(valid == k).sum() for k in [1, 2, 3, 4]]
                            pie_labels = ['生态优良区', '协调发展区', '自然限制区', '冲突预警区']
                            pie_colors = ['#2E86AB', '#A23B72', '#F18F01', '#C73E1D']
                            wedges, _, _ = ax2.pie(counts, labels=None, colors=pie_colors,
                                                    autopct='%1.1f%%', startangle=90,
                                                    textprops={'fontsize': 8})
                            ax2.set_title(f'{cname} 四类冲突分区')
                            ax2.legend(wedges, pie_labels, loc='lower center', ncol=2, fontsize=7,
                                      bbox_to_anchor=(0.5, -0.25))
                        else:
                            ax2.text(0.5, 0.5, '无有效数据', ha='center', va='center', transform=ax2.transAxes)
                            ax2.set_title(f'{cname} 冲突分区 (无数据)')
                    else:
                        ax2.text(0.5, 0.5, '未找到该县', ha='center', va='center', transform=ax2.transAxes)
                except Exception:
                    ax2.text(0.5, 0.5, '数据读取失败', ha='center', va='center', transform=ax2.transAxes)
                    ax2.set_title(f'{cname} 冲突分区')

                plt.tight_layout()
                st.pyplot(fig)

                # --- 图表行2: EQI 分量雷达图 + TDPI 散点 ---
                fig2 = plt.figure(figsize=(10, 4))

                # 左: EQI 分量雷达图
                ax3 = fig2.add_subplot(1, 2, 1, projection='polar')
                try:
                    gdf_local2, _ = load_county_data()
                    target_geom2 = gdf_local2[gdf_local2['name'] == cname].geometry.iloc[0]

                    component_values = []
                    component_labels = ['BRI', 'FVC', 'WATER', 'PM2.5', 'EROSION']
                    for cl in component_labels:
                        comp_path = [v for k, v in EQI_COMPONENTS.items() if cl in k][0]
                        with rasterio.open(comp_path) as src:
                            gdf_proj = gpd.GeoDataFrame(geometry=[target_geom2], crs=gdf_local2.crs).to_crs(src.crs)
                            geom_proj = gdf_proj.geometry.iloc[0]
                            mask = rasterize([(geom_proj, 1)], out_shape=(src.height, src.width),
                                           transform=src.transform, fill=0, all_touched=True).astype(bool)
                            arr_clip = src.read(1)[mask]
                            valid = arr_clip[(arr_clip != src.nodata) & (arr_clip > -100)]
                            component_values.append(float(np.mean(valid)) if len(valid) > 0 else 0)

                    angles = np.linspace(0, 2 * np.pi, len(component_labels), endpoint=False).tolist()
                    angles += angles[:1]
                    values = component_values + component_values[:1]

                    ax3.fill(angles, values, alpha=0.25, color='#2E86AB')
                    ax3.plot(angles, values, 'o-', color='#2E86AB', linewidth=2)
                    ax3.set_xticks(angles[:-1])
                    ax3.set_xticklabels(component_labels, fontsize=9)
                    ax3.set_ylim(0, 1)
                    ax3.set_title(f'{cname} EQI分量均值', y=1.1)
                    for i, (angle, val) in enumerate(zip(angles[:-1], component_values)):
                        ax3.annotate(f'{val:.2f}', xy=(angle, val), fontsize=8,
                                    xytext=(4, 4), textcoords='offset points')
                except Exception:
                    ax3.text(0.5, 0.5, 'EQI分量数据不可用', ha='center', va='center', transform=ax3.transAxes)
                    ax3.set_title(f'{cname} EQI分量')

                # 右: TDPI vs 优先级指数散点
                ax4 = fig2.add_subplot(1, 2, 2)
                ax4.scatter(df_ranked['tdpi_high_share']*100, df_ranked['priority_index'],
                          alpha=0.6, c='#7FB069', s=50)
                ax4.scatter(row['tdpi_high_share']*100, row['priority_index'],
                          c='#C73E1D', s=200, marker='*', edgecolors='black', linewidths=1.5, zorder=5)
                ax4.set_xlabel('TDPI高值区占比 (%)')
                ax4.set_ylabel('治理优先级指数')
                ax4.set_title('县域旅游压力-治理优先级对照')
                # 画阈值线
                threshold_pct = CONTROLLED_STATS['candidate_piecewise_change']['natural_only']['threshold_tdpi'] * 100
                ax4.axvline(x=threshold_pct, color='red', linestyle='--', alpha=0.5,
                          label=f'候选阈值 {threshold_pct:.1f}%')
                ax4.legend(fontsize=8)

                plt.tight_layout()
                st.pyplot(fig2)

                # --- 统计表格 ---
                st.markdown("**详细统计**")
                stats_table = pd.DataFrame({
                    '指标': ['一级优先区面积', '二级优先区面积', '三级优先区面积',
                            '一级区占比', 'TDPI高值区面积', 'TDPI高值区占比'],
                    '数值': [
                        f"{int(row['level_1_area_km2'])} km²",
                        f"{int(row['level_2_area_km2'])} km²",
                        f"{int(row['level_3_area_km2'])} km²",
                        f"{row['level_1_share']*100:.1f}%",
                        f"{int(row['tdpi_high_area_km2'])} km²",
                        f"{row['tdpi_high_share']*100:.1f}%",
                    ]
                })
                st.table(stats_table)

                # --- 智能诊断 ---
                st.markdown("---")
                st.markdown("### 🤖 智能诊断")

                diagnoses = generate_smart_diagnosis(row, df_ranked)
                for d in diagnoses:
                    st.markdown(f"- {d}")

                # --- 治理建议 ---
                st.markdown("---")
                st.markdown("### 📋 治理建议")
                if row['priority_index'] > 0.20:
                    st.error(
                        f"**{cname}** 处于高冲突状态。建议：\n\n"
                        "1. **暂停新增大型旅游项目审批**，优先控制旅游活动强度\n"
                        "2. **对现有景区实施容量管控**，设置日接待上限\n"
                        "3. **优先开展受损生态修复**，重点治理一级优先区\n"
                        "4. **建立月度遥感监测机制**，跟踪关键生态指标变化"
                    )
                elif row['priority_index'] > 0.10:
                    st.warning(
                        f"**{cname}** 需要动态监测。建议：\n\n"
                        "1. **新旅游项目须通过生态影响评估**\n"
                        "2. **划定旅游活动缓冲区**，在景区周边设置梯级缓冲带\n"
                        "3. **年度生态质量评估**，跟踪 TDPI 趋势\n"
                        "4. **若 TDPI 高值区扩大**，上调风险等级"
                    )
                else:
                    st.success(
                        f"**{cname}** 当前协调良好。建议：\n\n"
                        "1. **维持现有保护措施**\n"
                        "2. **发展低密度生态旅游**模式\n"
                        "3. **每 2-3 年定期评估**不放松"
                    )

                # --- 下载报告 ---
                st.markdown("---")
                report_text = generate_governance_report(cname, row, diagnoses)
                st.download_button(
                    label="📥 下载完整风险评估报告",
                    data=report_text,
                    file_name=f"{cname}_旅游生态风险评估简报.md",
                    mime="text/markdown",
                )

                # 清除选中状态
                if st.session_state.get('selected_county'):
                    st.session_state['selected_county'] = None

    # ===== Tab 3: 预警面板 =====
    with tab_warning:
        st.subheader("⚠️ 全州旅游生态冲突预警扫描")

        high_risk = df_ranked[df_ranked['priority_index'] > 0.20]
        medium_risk = df_ranked[(df_ranked['priority_index'] > 0.10) & (df_ranked['priority_index'] <= 0.20)]
        low_risk = df_ranked[df_ranked['priority_index'] <= 0.10]

        col_alert1, col_alert2, col_alert3 = st.columns(3)
        with col_alert1:
            st.metric("🔴 红色预警 (需立即管控)", f"{len(high_risk)} 县")
            for _, r in high_risk.iterrows():
                st.markdown(f"- **{r['name']}** (排名#{int(r['rank'])}, 指数{r['priority_index']:.4f})")
        with col_alert2:
            st.metric("🟠 橙色预警 (需动态监测)", f"{len(medium_risk)} 县")
            for _, r in medium_risk.iterrows():
                st.markdown(f"- {r['name']} (排名#{int(r['rank'])}, 指数{r['priority_index']:.4f})")
        with col_alert3:
            st.metric("🟢 当前协调 (维持保护)", f"{len(low_risk)} 县")

        st.markdown("---")

        # 排名 Top 10
        st.subheader("治理优先级排名 Top 10")
        top10 = df_ranked.head(10).copy()
        top10_display = top10[['rank', 'name', 'priority_index', 'level_1_share',
                               'level_2_share', 'tdpi_high_share']]
        top10_display.columns = ['排名', '县名', '优先级指数', '一级区占比', '二级区占比', 'TDPI高值占比']
        top10_display['优先级指数'] = top10_display['优先级指数'].apply(lambda x: f"{x:.4f}")
        top10_display['一级区占比'] = top10_display['一级区占比'].apply(lambda x: f"{x*100:.1f}%")
        top10_display['二级区占比'] = top10_display['二级区占比'].apply(lambda x: f"{x*100:.1f}%")
        top10_display['TDPI高值占比'] = top10_display['TDPI高值占比'].apply(lambda x: f"{x*100:.1f}%")
        st.dataframe(top10_display, use_container_width=True, hide_index=True)

        st.markdown("---")

        # 候选阈值预警
        st.subheader("🔬 基于自然本底控制的阈值预警")
        threshold_val = CONTROLLED_STATS['candidate_piecewise_change']['natural_only']['threshold_tdpi']
        ci_low, ci_high = CONTROLLED_STATS['candidate_piecewise_change']['natural_only']['spatial_block_bootstrap_20km']['threshold_ci95']
        class_5_count = CONTROLLED_STATS['class_counts']['5']

        st.info(f"""
        **候选结构变化点: TDPI ≈ {threshold_val:.3f}** (95% Bootstrap CI: [{ci_low:.3f}, {ci_high:.3f}])

        当某区域的 TDPI 值超过该候选阈值后，自然本底校正的 EQI 残差开始转为负值，
        意味着生态质量开始低于同等自然条件下的预期水平。

        已识别出 **{class_5_count} 个 1km² 像元** 处于"TDPI>阈值 + 残差<0"的高风险状态。
        仅凭截面数据将此用作探索性参考，不作为严格的因果阈值。
        """)

    # ===== Tab 4: 关于平台 =====
    with tab_about:
        st.subheader("📋 关于本平台")
        st.markdown("""
        ### 平台用途

        本平台是**川西旅游生态冲突预警与规划辅助工具**，面向阿坝州和甘孜州自然资源局、
        文旅局、生态环境局等政府部门，用于：

        1. **现状诊断**: 查看任意区域的旅游-生态冲突类型
        2. **县域评估**: 了解各县旅游业对生态环境的压力程度和排名
        3. **预警扫描**: 识别需要立即管控的高风险区域
        4. **规划辅助**: 为旅游项目选址和生态红线划定提供空间参考
        5. **现场分析**: 上传新数据或调整参数，实时生成分析结果

        ### 数据与方法

        - **空间分辨率**: 1 km (EPSG:6933 等面积投影)
        - **分析框架**: 参照 Liu et al. (2023, Earth's Future) 的 HAI-EQI 四象限法
        - **核心创新**: 旅游业发展压力指数 (TDPI)、自然本底控制分析、候选阈值检测
        - **县域统计**: 44县，31县达标参与排名

        ### 技术栈

        - 后端分析: Python (rasterio, geopandas, numpy, scikit-learn)
        - 前端展示: Streamlit + Folium
        - 竞赛平台: GeoScene Pro (对应 Python Toolbox)

        ### 引用

        Liu, H., et al. (2023). Conflict or coordination? The spatiotemporal relationship
        between humans and nature on the Qinghai-Tibet Plateau. *Earth's Future*, 11, e2022EF003452.

        ### 联系方式

        三人小组 · 易智瑞杯GIS竞赛 2026
        """)


# ========== 现场分析模式 ==========
def render_live_analysis_mode():
    """渲染现场分析模式"""
    st.subheader("🔬 现场分析")

    county_gdf = load_county_gdf()

    # 子模式选择
    sub_modes = [
        "📤 上传数据做县域统计",
        "⚙️ 阈值探索器",
        "📈 情景模拟",
        "🎚️ EQI权重自定义",
    ]
    sub_mode = st.radio(
        "选择分析功能",
        sub_modes,
        horizontal=True,
        index=sub_modes.index(st.session_state['live_sub_mode'])
        if st.session_state['live_sub_mode'] in sub_modes else 0
    )

    st.markdown("---")

    # ===== 子模式1: 上传数据做县域统计 =====
    if sub_mode == "📤 上传数据做县域统计":
        st.markdown("### 📤 上传栅格数据做县域分区统计")
        st.caption("上传任意 GeoTIFF 栅格 → 自动按阿坝/甘孜 31 县做分区统计 → 可视化结果")

        col_up1, col_up2 = st.columns([1, 1])

        with col_up1:
            uploaded_file = st.file_uploader(
                "上传 GeoTIFF 栅格文件 (.tif/.tiff)",
                type=['tif', 'tiff'],
                help="支持任意投影的 GeoTIFF，工具会自动处理坐标转换"
            )

            use_existing = st.checkbox("或使用已有栅格数据", value=False)
            existing_choice = None
            if use_existing:
                existing_choices = {
                    "HAI (人类活动强度)": RASTERS['hai'],
                    "TDPI (旅游压力)": RASTERS['tdpi'],
                    "EQI (生态质量)": RASTERS['eqi'],
                    "EQI自然校正残差": RASTERS['eqi_residual'],
                    "四类冲突分区": RASTERS['conflict_4class'],
                    "三级管理优先区": RASTERS['mgmt_priority'],
                }
                existing_choice = st.selectbox("选择已有栅格", list(existing_choices.keys()))
                uploaded_path = existing_choices[existing_choice]

        with col_up2:
            if uploaded_file is not None:
                # 保存上传文件到临时路径
                with tempfile.NamedTemporaryFile(delete=False, suffix='.tif') as tmp:
                    tmp.write(uploaded_file.read())
                    uploaded_path = tmp.name
                st.success(f"✅ 已加载: **{uploaded_file.name}**")
                st.session_state['uploaded_raster_name'] = uploaded_file.name
            elif use_existing and existing_choice:
                st.info(f"📂 已选择: **{existing_choice}**")
                st.session_state['uploaded_raster_name'] = existing_choice

        if (uploaded_file is not None) or (use_existing and existing_choice):
            st.markdown("---")

            if st.button("🚀 开始县域分区统计", type="primary", use_container_width=True):
                with st.spinner("正在计算县域分区统计..."):

                    # 显示栅格信息
                    with rasterio.open(uploaded_path) as src:
                        st.caption(f"栅格信息: CRS={src.crs}, 分辨率={src.res}, 形状={src.shape}")

                    # 做分区统计
                    stats_df = zonal_stats_by_county(uploaded_path, county_gdf)
                    st.session_state['uploaded_raster_stats'] = stats_df

                    if stats_df is not None and len(stats_df) > 0:
                        st.success(f"✅ 已完成 {len(stats_df)} 个县域的统计计算")

        # 显示结果
        if st.session_state['uploaded_raster_stats'] is not None:
            stats_df = st.session_state['uploaded_raster_stats']
            raster_name = st.session_state.get('uploaded_raster_name', '未知数据')

            st.markdown("---")
            st.markdown(f"### 📊 统计结果: {raster_name}")

            # 按均值着色地图
            mean_vals = stats_df['mean'].dropna()

            if len(mean_vals) > 0:
                mean_min, mean_max = mean_vals.min(), mean_vals.max()

                col_map, col_tbl = st.columns([2, 1])

                with col_map:
                    # 按均值着色 Choropleth
                    county_gdf_stats = county_gdf.merge(stats_df, on='name', how='left')

                    m = create_base_map()
                    from branca.colormap import LinearColormap
                    cmap = LinearColormap(
                        ['#2E86AB', '#7FB069', '#F5D547', '#F18F01', '#C73E1D'],
                        vmin=mean_min, vmax=mean_max
                    )

                    folium.GeoJson(
                        county_gdf_stats.__geo_interface__,
                        style_function=lambda x: {
                            'fillColor': cmap(x['properties'].get('mean', 0)) if x['properties'].get('mean') is not None and not np.isnan(x['properties'].get('mean', 0)) else '#cccccc',
                            'color': '#333333',
                            'weight': 0.5,
                            'fillOpacity': 0.7,
                        },
                        tooltip=folium.GeoJsonTooltip(
                            fields=['name', 'mean', 'std', 'count'],
                            aliases=['县名', '均值', '标准差', '有效像元数'],
                            localize=True
                        ),
                        name='县域均值'
                    ).add_to(m)

                    st.components.v1.html(m._repr_html_(), height=450)
                    st.caption(f"着色字段: 均值 | 范围: [{mean_min:.4f}, {mean_max:.4f}]")

                with col_tbl:
                    # 统计表
                    st.markdown("**各县汇总统计**")
                    disp = stats_df.copy()
                    for c in ['mean', 'std', 'min', 'max']:
                        if c in disp.columns:
                            disp[c] = disp[c].apply(lambda x: f"{x:.4f}" if not np.isnan(x) else "N/A")
                    disp['count'] = disp['count'].apply(lambda x: f"{int(x)}" if not np.isnan(x) else "0")
                    st.dataframe(
                        disp[['name', 'mean', 'std', 'min', 'max', 'count']],
                        use_container_width=True, hide_index=True, height=400
                    )

                # 下载按钮
                csv_data = stats_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 下载各县统计表 (CSV)",
                    data=csv_data,
                    file_name=f"{raster_name}_县域统计.csv",
                    mime="text/csv",
                )

    # ===== 子模式2: 阈值探索器 =====
    elif sub_mode == "⚙️ 阈值探索器":
        st.markdown("### ⚙️ TDPI 阈值探索器")
        st.caption("拖动滑块改变 TDPI 候选阈值 → 实时查看管理优先区重分类 → 对比各县受影响程度")

        tdpi_data, tdpi_nodata, _, _ = read_raster_array(RASTERS['tdpi'])
        valid_mask = (tdpi_data != tdpi_nodata) & (tdpi_data > 0)

        col_th1, col_th2 = st.columns([1, 2])

        with col_th1:
            default_threshold = CONTROLLED_STATS['candidate_piecewise_change']['natural_only']['threshold_tdpi']
            user_threshold = st.slider(
                "TDPI 候选阈值",
                min_value=0.01, max_value=0.50, value=float(default_threshold),
                step=0.005, format="%.3f",
                help="默认值为 0.099（来自自然本底控制分析的结构变化点检测）"
            )

            # 重新分类
            new_mgmt = np.full(tdpi_data.shape, 3, dtype=np.int8)
            new_mgmt[valid_mask & (tdpi_data > user_threshold)] = 1
            new_mgmt[valid_mask & (tdpi_data > user_threshold * 0.5) & (tdpi_data <= user_threshold)] = 2
            new_mgmt[~valid_mask] = 0

            # 统计
            total_valid = valid_mask.sum()
            l1 = (new_mgmt == 1).sum()
            l2 = (new_mgmt == 2).sum()
            l3 = (new_mgmt == 3).sum()

            # 原始统计
            orig_data, orig_nodata, _, _ = read_raster_array(RASTERS['mgmt_priority'])
            orig_valid = (orig_data != orig_nodata) & (orig_data > 0)
            orig_l1 = (orig_data == 1).sum()

            st.markdown("---")
            st.markdown("**新分类统计**")
            st.metric("一级优先区", f"{l1} km²", delta=f"{l1 - orig_l1:+d} vs 原分类", delta_color="inverse")
            st.metric("二级优先区", f"{l2} km²")
            st.metric("三级/背景区", f"{l3} km²")
            st.metric("一级占比", f"{l1/total_valid*100:.2f}%")

            st.caption(f"默认阈值: {default_threshold:.3f} (ΔAIC=-9.49)")
            st.caption(f"95% CI: [{CONTROLLED_STATS['candidate_piecewise_change']['natural_only']['spatial_block_bootstrap_20km']['threshold_ci95'][0]:.3f}, "
                      f"{CONTROLLED_STATS['candidate_piecewise_change']['natural_only']['spatial_block_bootstrap_20km']['threshold_ci95'][1]:.3f}]")

        with col_th2:
            # 可视化新分类
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))

            # 左: 新分类地图
            display = np.where(valid_mask, new_mgmt, -1)
            cmap = plt.cm.colors.ListedColormap(['#cccccc', '#C73E1D', '#F18F01', '#7FB069'])
            ax1.imshow(display[:, ::-1], cmap=cmap, aspect='auto')
            ax1.set_title(f'TDPI阈值={user_threshold:.3f} 管理优先区')
            ax1.axis('off')

            # 右: 阈值对比曲线
            thresholds_range = np.linspace(0.02, 0.30, 30)
            l1_shares = []
            for t in thresholds_range:
                test_l1 = (valid_mask & (tdpi_data > t)).sum()
                l1_shares.append(test_l1 / total_valid * 100)

            ax2.plot(thresholds_range, l1_shares, 'b-', linewidth=2)
            ax2.axvline(x=user_threshold, color='red', linestyle='--', linewidth=2,
                       label=f'当前: {user_threshold:.3f}')
            ax2.axvline(x=default_threshold, color='gray', linestyle=':', linewidth=1,
                       label=f'默认: {default_threshold:.3f}')
            ax2.set_xlabel('TDPI阈值')
            ax2.set_ylabel('一级优先区占比 (%)')
            ax2.set_title('阈值对一级优先区面积的影响')
            ax2.legend()
            ax2.grid(True, alpha=0.3)

            plt.tight_layout()
            st.pyplot(fig)

        # 各县新统计（与原有对比）
        st.markdown("---")
        st.markdown("### 各县一级优先区变化")

        _, df_ranked = load_county_data()
        # 用原有一级区数据与新阈值对比
        comparison = df_ranked[['name', 'rank', 'level_1_share']].copy()
        comparison['原一级区占比'] = (comparison['level_1_share'] * 100).round(2)
        comparison = comparison.rename(columns={'level_1_share': '_old'})

        # 用简单的 TDPI 高值占比近似
        comparison['新阈值下一级区 (近似)'] = (df_ranked['tdpi_high_share'] * 100).round(2)
        comparison['变化方向'] = comparison.apply(
            lambda r: '⚠️ 升级' if r['新阈值下一级区 (近似)'] > r['原一级区占比'] * 1.2
            else ('✅ 改善' if r['新阈值下一级区 (近似)'] < r['原一级区占比'] * 0.8 else '➡️ 持平'),
            axis=1
        )

        st.dataframe(
            comparison[['name', 'rank', '原一级区占比', '新阈值下一级区 (近似)', '变化方向']],
            use_container_width=True, hide_index=True
        )
        st.caption("注: 新阈值下一级区为估算值（基于TDPI高值区占比），实际值需要原始冲突分区栅格参与计算。")

    # ===== 子模式3: 情景模拟 =====
    elif sub_mode == "📈 情景模拟":
        st.markdown("### 📈 旅游增长情景模拟")
        st.caption("模拟 TDPI 在不同增长倍数下，哪些县的风险等级会发生变化")

        col_sc1, col_sc2 = st.columns([1, 2])

        with col_sc1:
            growth_factor = st.slider(
                "TDPI 增长倍数",
                min_value=1.0, max_value=3.0, value=1.2, step=0.1,
                format="%.1f×",
                help="1.2× = 旅游压力增长 20%，模拟不同发展情景"
            )

            st.markdown("**情景说明**")
            st.markdown(f"- 当前 TDPI × **{growth_factor:.1f}**")
            st.markdown(f"- 相当于旅游活动强度增长 **{(growth_factor-1)*100:.0f}%**")

            threshold = CONTROLLED_STATS['candidate_piecewise_change']['natural_only']['threshold_tdpi']

            # 读取 TDPI 和县界做模拟
            _, df_ranked = load_county_data()

            # 估算每个县在新情景下的一级区占比
            # 使用简单近似：tdpi_high_share × growth_factor 的效应
            sim_results = []
            for _, r in df_ranked.iterrows():
                orig_tdpi_high = r['tdpi_high_share']
                # 假设 TDPI 增长导致高值区占比增加
                new_tdpi_high = min(orig_tdpi_high * growth_factor, 1.0)
                # 重新估算 priority_index
                orig_pi = r['priority_index']
                pi_change = (new_tdpi_high - orig_tdpi_high) * 0.8
                new_pi = min(orig_pi + pi_change, 1.0)

                orig_risk, _, _ = classify_risk(orig_pi)
                new_risk, new_label, _ = classify_risk(new_pi)

                sim_results.append({
                    'name': r['name'],
                    'rank': int(r['rank']),
                    'orig_pi': orig_pi,
                    'new_pi': new_pi,
                    'orig_risk': orig_risk,
                    'new_risk': new_risk,
                    'risk_change': new_risk - orig_risk,
                    'tdpi_high_orig': orig_tdpi_high,
                    'tdpi_high_new': new_tdpi_high,
                })

            sim_df = pd.DataFrame(sim_results)

            # 统计
            n_upgrade = (sim_df['risk_change'] > 0).sum()
            n_stable = (sim_df['risk_change'] == 0).sum()
            n_downgrade = (sim_df['risk_change'] < 0).sum()

            st.markdown("---")
            st.markdown("**风险变化统计**")
            st.metric("⚠️ 风险升级", f"{n_upgrade} 县")
            st.metric("➡️ 风险不变", f"{n_stable} 县")
            st.metric("✅ 风险下降", f"{n_downgrade} 县" if n_downgrade > 0 else "0 县")

            # 新的高风县数量
            new_high_count = (sim_df['new_risk'] >= 3).sum()
            orig_high_count = (sim_df['orig_risk'] >= 3).sum()
            st.metric("🔴 高风险县数", f"{new_high_count}", delta=f"{new_high_count - orig_high_count:+d}",
                     delta_color="inverse")

        with col_sc2:
            # 可视化
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))

            # 左: 风险转移矩阵
            risk_levels = ['低风险', '中等风险', '中高风险', '高风险']
            risk_colors = ['#7FB069', '#F5D547', '#F18F01', '#C73E1D']

            x_pos = np.arange(len(risk_levels))
            bar_width = 0.35

            orig_counts = [(sim_df['orig_risk'] == i).sum() for i in range(4)]
            new_counts = [(sim_df['new_risk'] == i).sum() for i in range(4)]

            ax1.bar(x_pos - bar_width/2, orig_counts, bar_width, label='当前', color='#7FB069', alpha=0.8)
            ax1.bar(x_pos + bar_width/2, new_counts, bar_width, label=f'{growth_factor:.1f}× TDPI',
                    color='#C73E1D', alpha=0.8)
            ax1.set_xticks(x_pos)
            ax1.set_xticklabels(risk_levels, fontsize=9)
            ax1.set_ylabel('县数')
            ax1.set_title(f'旅游增长 {growth_factor:.1f}× 情景下风险分布')
            ax1.legend()

            # 右: 各县 priority_index 变化
            upgraded = sim_df[sim_df['risk_change'] > 0].sort_values('new_pi', ascending=False)
            if len(upgraded) > 0:
                y_pos = range(len(upgraded))
                ax2.barh(y_pos, upgraded['new_pi'], color='#C73E1D', alpha=0.7, label=f'{growth_factor:.1f}× TDPI')
                ax2.barh(y_pos, upgraded['orig_pi'], color='#7FB069', alpha=0.7, label='当前')
                ax2.set_yticks(y_pos)
                ax2.set_yticklabels(upgraded['name'], fontsize=9)
                ax2.set_xlabel('优先级指数')
                ax2.set_title('风险升级县 优先级指数变化')
                ax2.legend(fontsize=8)
            else:
                ax2.text(0.5, 0.5, '无县风险升级', ha='center', va='center', transform=ax2.transAxes)
                ax2.set_title('风险升级县')

            plt.tight_layout()
            st.pyplot(fig)

            # 详细表格
            st.markdown("**风险升级县详情**")
            upgraded_disp = upgraded[['name', 'rank', 'orig_pi', 'new_pi']].copy()
            upgraded_disp.columns = ['县名', '排名', '当前PI', f'{growth_factor:.1f}× PI']
            upgraded_disp['当前PI'] = upgraded_disp['当前PI'].apply(lambda x: f"{x:.4f}")
            upgraded_disp[f'{growth_factor:.1f}× PI'] = upgraded_disp[f'{growth_factor:.1f}× PI'].apply(lambda x: f"{x:.4f}")
            st.dataframe(upgraded_disp if len(upgraded) > 0 else pd.DataFrame(),
                        use_container_width=True, hide_index=True)

    # ===== 子模式4: EQI权重自定义 =====
    elif sub_mode == "🎚️ EQI权重自定义":
        st.markdown("### 🎚️ 自定义 EQI 权重构建器")
        st.caption("调整 EQI 五个分量的权重 → 实时重算 EQI → 观察冲突分区变化")

        col_w1, col_w2 = st.columns([1, 2])

        with col_w1:
            st.markdown("**EQI 分量权重** (和为 1.0)")

            w_bri = st.slider("BRI (生物多样性)", 0.0, 1.0, 0.20, 0.05, key="w_bri")
            w_fvc = st.slider("FVC (植被覆盖)", 0.0, 1.0, 0.20, 0.05, key="w_fvc")
            w_water = st.slider("WATER (水源涵养)", 0.0, 1.0, 0.20, 0.05, key="w_water")
            w_pm25 = st.slider("PM2.5 (空气质量)", 0.0, 1.0, 0.20, 0.05, key="w_pm25")
            w_erosion = st.slider("EROSION (土壤侵蚀)", 0.0, 1.0, 0.20, 0.05, key="w_erosion")

            total_w = w_bri + w_fvc + w_water + w_pm25 + w_erosion
            st.metric("权重合计", f"{total_w:.2f}", delta="✅ 正常" if abs(total_w - 1.0) < 0.01 else "⚠️ 请调整为 1.0")

            if st.button("🔄 重置为默认权重 (等权 0.20)"):
                for key in ['w_bri', 'w_fvc', 'w_water', 'w_pm25', 'w_erosion']:
                    st.session_state[key] = 0.20
                st.rerun()

            st.markdown("---")
            st.caption("默认: 5 个分量等权 (各 0.20)")

        with col_w2:
            if abs(total_w - 1.0) < 0.01:
                if st.button("🚀 重算 EQI", type="primary", use_container_width=True):
                    with st.spinner("正在加权合成新 EQI..."):

                        weights = {'BRI': w_bri, 'FVC': w_fvc, 'WATER': w_water,
                                  'PM2.5': w_pm25, 'EROSION': w_erosion}

                        # 读取各分量
                        eqi_new = None
                        valid_mask = None
                        for label, w in weights.items():
                            comp_path = [v for k, v in EQI_COMPONENTS.items() if label in k][0]
                            data, nodata, _, _ = read_raster_array(comp_path)

                            if valid_mask is None:
                                valid_mask = (data != nodata) & (data > -100)

                            if eqi_new is None:
                                eqi_new = data * w
                            else:
                                eqi_new += data * w

                        # 计算新中位数用于高低分类
                        eqi_valid = eqi_new[valid_mask]
                        new_median = np.median(eqi_valid)

                        # 读取 HAI 做四象限
                        hai_data, hai_nodata, _, _ = read_raster_array(RASTERS['hai'])
                        common_valid = valid_mask & (hai_data != hai_nodata) & (hai_data > -100)
                        hai_median = np.median(hai_data[common_valid])

                        # 新冲突分类
                        new_conflict = np.full(eqi_new.shape, -9999, dtype=np.int8)
                        hai_high = hai_data > hai_median
                        eqi_high = eqi_new > new_median
                        new_conflict[common_valid & hai_high & eqi_high] = 2   # 高-高: 协调
                        new_conflict[common_valid & hai_high & ~eqi_high] = 4  # 高-低: 冲突
                        new_conflict[common_valid & ~hai_high & eqi_high] = 1  # 低-高: 生态优良
                        new_conflict[common_valid & ~hai_high & ~eqi_high] = 3 # 低-低: 自然限制

                        class_counts = {k: (new_conflict == k).sum() for k in [1, 2, 3, 4]}

                        # 可视化
                        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))

                        # 左: 新 EQI 地图
                        eqi_display = np.where(valid_mask, eqi_new, np.nan)
                        im1 = ax1.imshow(eqi_display[:, ::-1], cmap='RdYlGn', aspect='auto', vmin=0, vmax=1)
                        ax1.set_title(f'自定义权重 EQI\n中位数={new_median:.4f}')
                        ax1.axis('off')
                        plt.colorbar(im1, ax=ax1, fraction=0.046, pad=0.04)

                        # 右: 新冲突分区
                        cmap2 = plt.cm.colors.ListedColormap(
                            ['#cccccc', '#2E86AB', '#A23B72', '#F18F01', '#C73E1D']
                        )
                        display2 = new_conflict.copy()
                        display2[~common_valid] = 0
                        ax2.imshow(display2[:, ::-1], cmap=cmap2, aspect='auto', vmin=0, vmax=4)
                        ax2.set_title(f'新四类冲突分区\n冲突区(红色): {class_counts[4]} km²')
                        ax2.axis('off')

                        plt.tight_layout()
                        st.pyplot(fig)

                        # 统计对比
                        st.markdown("---")
                        st.markdown("### 与原 EQI 四类冲突对比")

                        # 读原始
                        orig_conflict_data, orig_cf_nodata, _, _ = read_raster_array(RASTERS['conflict_4class'])
                        orig_counts = {k: (orig_conflict_data == k).sum() for k in [1, 2, 3, 4]}

                        comp_table = pd.DataFrame({
                            '冲突类型': ['生态优良区', '协调发展区', '自然限制区', '冲突预警区'],
                            '原始分类': [f"{orig_counts[k]} km²" for k in [1, 2, 3, 4]],
                            '自定义权重': [f"{class_counts[k]} km²" for k in [1, 2, 3, 4]],
                            '变化': [f"{class_counts[k] - orig_counts[k]:+d} km²" for k in [1, 2, 3, 4]],
                        })
                        st.table(comp_table)

                        st.caption(f"自定义权重: BRI={w_bri:.2f} FVC={w_fvc:.2f} WATER={w_water:.2f} "
                                  f"PM2.5={w_pm25:.2f} EROSION={w_erosion:.2f} | "
                                  f"新 EQI 中位数={new_median:.4f} (原: 0.6896)")
            else:
                st.warning("⚠️ 权重合计必须为 1.0，请调整滑块使合计为 1.0")


# ========== 主入口 ==========
st.title("🏔️ 川西旅游生态冲突预警与规划辅助平台")
st.caption("阿坝藏族羌族自治州 · 甘孜藏族自治州 | Tourism-Ecology Conflict Early Warning System")

# 模式选择（最顶部）
mode = st.radio(
    "选择分析模式",
    ["📊 展示已分析数据", "🔬 现场分析"],
    horizontal=True,
    help="展示已分析数据 = 浏览预计算的冲突分区/管理优先区/EQI分量; 现场分析 = 上传新数据或调整参数实时计算"
)

st.markdown("---")

if mode == "📊 展示已分析数据":
    render_precomputed_mode()
else:
    render_live_analysis_mode()

# 底部
st.markdown("---")
st.caption("🏔️ 川西旅游生态冲突预警平台 v0.2 | Built with Streamlit + Folium | 数据: 1km栅格 EPSG:6933")
