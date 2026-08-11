# 川西旅游生态冲突预警与规划辅助平台

> **参赛组别**：应用开发组（C组）
> **竞赛名称**：易智瑞杯中国大学生GIS软件开发竞赛（2026）
> **开发平台**：GeoScene Pro + Python (Streamlit)

---

## 快速体验

| 方式 | 说明 | 链接 |
|------|------|------|
| 🌐 **在线使用** | 浏览器打开即用，无需安装 | [b1774geotool.streamlit.app](https://b1774geotool.streamlit.app) |
| 💻 **本地运行** | 下载仓库，本地启动 | 见下方 [运行说明](#五运行说明) |
| 🗺️ **GeoScene 工具箱** | 在 GeoScene Pro 中加载 | 见下方 [GeoScene Pro 工具箱](#53-geoscene-pro-工具箱) |

---

## 一、作品摘要

### 1.1 研究背景

川西地区（阿坝藏族羌族自治州、甘孜藏族自治州）地处青藏高原东缘，是我国重要的生态安全屏障和生物多样性热点区。近年来，随着川藏铁路建设推进和全域旅游快速发展，旅游业对该地区生态环境的压力日益凸显。如何在生态保护与旅游发展之间寻求科学平衡，是地方政府面临的紧迫决策难题。

### 1.2 核心问题

- 哪些区域的旅游业已经对生态环境造成了明显压力？
- 哪些县域需要立即管控，哪些可以适度开发？
- 如果继续扩大旅游规模，风险格局将如何变化？

### 1.3 解决方案

本平台构建了 **"三指数—四象限—三级预警"** 分析框架：

| 层级 | 内容 | 方法 |
|------|------|------|
| 三指数 | HAI（人类活动强度）、TDPI（旅游发展压力）、EQI（生态质量） | 多源数据空间化 + 加权合成 |
| 四象限 | HAI × EQI → 四类冲突分区 | 中位数二分法 + 空间交叉 |
| 三级预警 | 管理优先区 → 县域排名 → 政策建议 | 冲突类型 × TDPI 等级叠加 |

**最终交付物**：

1. **GeoScene Pro Python 工具箱**（`.pyt`）—— 3 个工具覆盖县域评估、全州扫描、点位查询，参数已预设默认路径
2. **Streamlit Web 交互平台**（`app.py`）—— 双模式：预计算数据展示 + 现场实时分析，已部署至 Streamlit Community Cloud

---

## 二、技术创新点

| # | 创新点 | 说明 |
|---|--------|------|
| 1 | **TDPI（旅游业发展压力指数）** | 区别于传统 HAI，聚焦旅游活动——景区等级、设施密度、服务聚集度——构建旅游业特异性压力指标，将旅游从一般人类活动中分离 |
| 2 | **自然本底控制分析** | 以海拔、坡度、气温、降水等五因子岭回归剥离自然混淆效应（空间 CV R²=0.515），分离旅游对生态的净影响 |
| 3 | **出现效应 vs 强度效应** | 区分"旅游压力是否存在"与"旅游压力有多强"的非对称影响，发现出现效应显著而强度效应不显著，指向"空间准入优先于流量控制"的管理方向 |
| 4 | **候选结构变化点检测** | 分段线性回归 + AIC 模型比较识别 TDPI ≈ 0.099 处的候选拐点（ΔAIC=-9.49），经 Bootstrap 审慎定性为探索性结构变化 |
| 5 | **九寨沟 PSM-准DID 局地验证** | 100 m 网格下利用 2017 地震准实验窗口，倾向得分匹配 + 准双重差分法验证旅游建设的局地生态效应 |
| 6 | **GeoScene + Web 双平台交付** | GeoScene Pro 工具箱（竞赛规定平台）+ Streamlit Cloud（零安装，浏览器访问），参数预设默认路径，开箱即用 |

---

## 三、技术路线

### 3.1 数据体系

| 指数 | 分量 | 数据来源 | 分辨率 | 年份 |
|------|------|---------|--------|------|
| **HAI** | 人口密度 | WorldPop | 1 km | 2020 |
| | 夜间灯光 | 国家青藏高原数据中心 (Zhang 2021) | 1 km | 2020 |
| | 土地利用强度 | 中科院 RESDC | 1 km | 2020 |
| | 道路密度 | OpenStreetMap | 矢量 | 2024 |
| **TDPI** | 景区等级与规模 | 百度地图 POI + 四川省文旅厅 | 点/面 | 2024 |
| | 旅游设施密度 | OSM tourism 标签 | 点 | 2024 |
| | 旅游服务集聚度 | 酒店/餐饮/交通 POI | 点 | 2024 |
| | 承载条件 | 道路通达性 + 住宿容量 | — | 2024 |
| **EQI** | BRI（生物多样性） | 国家青藏高原数据中心 | 1 km | 2020 |
| | FVC（植被覆盖度） | MODIS MOD13A3 | 1 km | 2020 |
| | WATER（水源涵养） | Wang (2022) | 1 km | 2020 |
| | PM2.5（空气质量） | WUSTL ACAG V5.GL.02 | 0.01° | 2020 |
| | EROSION（土壤侵蚀） | 中科院 RESDC | 1 km | 2020 |
| **自然控制** | 高程/坡度/起伏度 | SRTM DEM | 1 km | — |
| | 气温/降水 | TerraClimate | ~4 km | 2020 |

### 3.2 分析流程

```
原始数据 → 重采样至统一 1 km 网格 (EPSG:6933 等面积投影)
        → 归一化处理 (0–1)
        → 权重合成 (HAI / TDPI / EQI)
        → 自然本底控制回归 (5 自然因子 → EQI，岭惩罚 + 50 km 空间 CV)
        → 四象限冲突分区 (HAI 中位数 × EQI 中位数)
        → TDPI 叠加 → 三级管理优先区
        → 县域分区统计 → 31 县治理优先级排名
        → 出现效应与强度效应分别检验 (空间块 Bootstrap)
        → 候选结构变化点检测 (分段线性回归 + ΔAIC)
        → 31 km 局部滑动窗口秩相关
        → 九寨沟 PSM-准DID 局地因果推断 (100 m 网格)
```

### 3.3 关键发现

| 指标 | 数值 |
|------|------|
| 有效分析面积 | 232,487 km²（1 km 像元） |
| TDPI 正压力区 | 7,780 km²（3.3%） |
| 冲突预警区（高 HAI-低 EQI） | ≈ 2,167 km²（0.9%） |
| 出现效应（ΔEQI） | -0.0336（500 次 Bootstrap CI 全负） |
| 强度效应（p 值） | 0.438（不显著） |
| TDPI 候选结构变化点 | 0.099（ΔAIC=-9.49, 95% CI [0.051, 0.162]） |
| 局部负相关窗口比例 | 69.97% |
| 治理排名 #1 | 泸定县（优先级指数 0.2759） |
| 九寨沟 NDVI 准 DID | -0.124（斑块 Bootstrap CI 全负） |

---

## 四、系统功能

### 4.1 Streamlit Web 应用

```
┌──────────────────────────────────────────────────────────┐
│          川西旅游生态冲突预警与规划辅助平台                │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  📊 展示已分析数据                                        │
│  ├─ 🗺️  交互地图        7 个图层切换，县域边界叠加       │
│  ├─ 🏛️  县域诊断         冲突饼图 + EQI 雷达 + 智能诊断   │
│  ├─ ⚠️  预警面板         三级预警 + Top 10 + 阈值说明    │
│  ├─ 📋  侧边栏排名       31 县治理优先级完整排名          │
│  └─ 📥  下载报告         一键生成县域治理建议报告          │
│                                                          │
│  🔬 现场分析                                             │
│  ├─ 📤  上传数据         任意 GeoTIFF → 31 县分区统计     │
│  ├─ ⚙️  阈值探索器       滑块调整 TDPI 阈值 → 实时重分类  │
│  ├─ 📈  情景模拟         旅游增长 20%–200% → 风险升级预测 │
│  └─ 🎚️  EQI 权重自定义   5 分量权重调整 → 新 EQI/冲突图   │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

### 4.2 GeoScene Pro 工具箱

| 工具 | 功能 | 主要输入 | 输出 |
|------|------|---------|------|
| **县域旅游生态风险评估** | 选定县 → 裁剪栅格 → 分区统计 → 风险简报 | 县名 + 管理优先区栅格 + 县界 | `.txt` 风险评估简报 |
| **全州冲突预警扫描** | 全州扫描 → 提取一级预警区 → 统计分析 | 冲突分区 + 管理优先区 + 县界 | 预警区 `.tif` + 统计摘要 |
| **点位诊断查询** | 地图选点 → 提取冲突类型/优先级/TDPI/EQI | 点击坐标 + 4 个输入栅格 | 点位诊断报告 |

**所有输入参数均已预设默认路径**，指向仓库 `data/` 文件夹下对应数据，加载工具箱后直接使用。

---

## 五、运行说明

### 5.1 Streamlit 在线访问

直接打开浏览器访问部署地址（无需安装任何软件）：

🔗 **[https://b1774geotool.streamlit.app](https://b1774geotool.streamlit.app)**

### 5.2 Streamlit 本地运行

**环境要求**

- Python 3.9+
- 依赖包见 `requirements.txt`

**启动步骤**

```bash
# 1. 克隆仓库
git clone https://github.com/847135643/tourism-ecology-analize-tool.git
cd tourism-ecology-analize-tool

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动应用
streamlit run app.py
```

浏览器自动打开 `http://localhost:8501`。

### 5.3 GeoScene Pro 工具箱

1. 下载本仓库（Code → Download ZIP，或 `git clone`）
2. 打开 GeoScene Pro（或 ArcGIS Pro 3.x+）
3. Catalog 面板 → 右键 Toolboxes → **Add Toolbox**
4. 选择 `川西旅游生态预警工具箱.pyt`
5. 打开任意工具，参数已自动填入 `data/` 下对应数据，即可运行

> **兼容性**：`.pyt` 语法在 GeoScene Pro 与 ArcGIS Pro 中完全兼容。

---

## 六、适用场景

| 用户角色 | 使用场景 | 推荐功能 |
|---------|---------|---------|
| 州/县级自然资源局 | 新旅游项目选址前评估 | 县域诊断 + 点位查询 |
| 文旅局 | 景区容量管控决策 | 情景模拟（增长 20%/50% 哪些县升级） |
| 生态环境局 | 生态红线预警 | 全州预警扫描 + 阈值探索器 |
| 规划编制单位 | 旅游发展规划修编 | 四象限冲突图 + 治理优先级排名 |
| 科研人员 | 参数敏感性分析 | EQI 权重自定义 + 上传新数据 |

---

## 七、文件结构

```
tourism-ecology-analize-tool/
├── .gitignore
├── README.md
├── requirements.txt
├── app.py                              # Streamlit Web 应用主程序
├── 川西旅游生态预警工具箱.pyt           # GeoScene Pro Python 工具箱（预设默认路径）
└── data/                               # 分析数据（11 MB）
    ├── 01_EQI_expected_from_natural_background.tif
    ├── 02_EQI_natural_adjusted_residual.tif
    ├── 06_TDPI_EQI_adjusted_relationship_class.tif
    ├── controlled_analysis_summary.json
    ├── EQI/
    │   ├── EQI_v02_bbox_1km.tif
    │   └── components/
    │       ├── BRI_norm_1km.tif
    │       ├── EROSION_quality_1km.tif
    │       ├── FVC_1km.tif
    │       ├── PM25_reverse_norm_1km.tif
    │       └── WATER_norm_1km.tif
    ├── HAI/
    │   └── HAI_阿坝甘孜_1km_20260809.tif
    ├── TDPI叠加后的一级、二级、三级管理优先区/
    │   ├── HAI_EQI_conflict_4class_1km.tif
    │   ├── TDPI_level_1km.tif
    │   ├── TDPI_v02_aligned_1km.tif
    │   ├── management_priority_3class_1km.tif
    │   └── conflict_priority_stats.json
    └── 县域旅游生态治理优先级/
        └── 03_表格与矢量/
            ├── 县域管理优先区统计.csv
            └── 县域管理优先区统计.geojson
```

---

## 八、参考文献

1. Liu, H., et al. (2023). Conflict or coordination? The spatiotemporal relationship between humans and nature on the Qinghai-Tibet Plateau. *Earth's Future*, 11, e2022EF003452. https://doi.org/10.1029/2022EF003452
2. Zhang, Y., Ren, Y., et al. (2021). A long-term and high-resolution global gridded photosynthetically active radiation product. 国家青藏高原数据中心. https://doi.org/10.11888/Socioeco.tpdc.271202
3. Chen, J., et al. (2022). Global 1 km × 1 km gridded GDP. *Scientific Data*, 9, 180. https://doi.org/10.6084/m9.figshare.17004523.v1
4. Wang, Y., et al. (2022). A global gridded water conservation dataset. 国家青藏高原数据中心. https://doi.org/10.11888/Terre.tpdc.272341
5. Hua, F., et al. (2022). Protected areas and tourism. *Current Biology*, 32(16). https://doi.org/10.1016/j.cub.2022.06.062
6. Fan, Y., et al. (2023). Using social media data to map tourism's ecological footprint. *People and Nature*, 5(4). https://doi.org/10.1002/pan3.10497
7. ESA. (2021). WorldCover 10m v100. https://esa-worldcover.org/
8. WorldPop. (2020). Population Density 1km. https://hub.worldpop.org/
9. USGS. MODIS MOD13A3 (NDVI) & MOD17A3HGF (NPP). https://lpdaac.usgs.gov/
10. WUSTL ACAG. Surface PM2.5 V5.GL.02. https://sites.wustl.edu/acag/datasets/surface-pm2-5/

---

## 九、团队信息

| 角色 | 姓名 | 分工 |
|------|------|------|
| 队长 | （填写） | 总体设计、分析方法、TDPI 构建 |
| 队员 | （填写） | 数据处理、栅格计算、GIS 制图 |
| 队员 | （填写） | 工具开发、前端展示、文档撰写 |

**指导教师**：（填写）

**所在院校**：（填写）

---

> © 2026 三人小组 · 易智瑞杯中国大学生GIS软件开发竞赛
