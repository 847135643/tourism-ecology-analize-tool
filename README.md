# 川西旅游生态冲突预警与规划辅助平台

> **参赛组别**：应用开发组（C组）
> **竞赛名称**：易智瑞杯中国大学生GIS软件开发竞赛（2026）
> **开发平台**：GeoScene Pro + Python (Streamlit)

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
| 三级预警 | 管理优先区 → 县域治理排名 → 政策建议 | 冲突类型 × TDPI等级叠加 |

**最终交付物**：（1）基于 GeoScene Pro 的 Python 工具箱（3个工具）；（2）基于 Streamlit 的交互式 Web 决策辅助平台（双模式：预计算数据浏览 + 现场实时分析）。

---

## 二、技术创新点

| # | 创新点 | 说明 |
|---|--------|------|
| 1 | **TDPI（旅游业发展压力指数）** | 区别于传统的 HAI（Liu et al., 2023），聚焦旅游活动——景区等级/设施密度/服务聚集度——构建旅游业特异性压力指标 |
| 2 | **自然本底控制分析** | 剔除海拔、坡度、气温、降水等自然因素的混淆效应（空间CV R²=0.515），分离出旅游对生态的"净"影响 |
| 3 | **候选结构变化点检测** | 在 TDPI≈0.099 处识别出非线性阈值（ΔAIC=-9.49, Bootstrap 95% CI [0.051, 0.162]），为管控决策提供定量依据 |
| 4 | **双模式实时分析** | 用户可上传任意栅格数据做县域分区统计，也可通过滑块调整阈值/权重/增长情景，实时观察分析结果变化 |
| 5 | **GeoScene + Web 双平台** | 既提供 GeoScene Pro 原生工具箱（.pyt，竞赛规定平台），也提供浏览器端 Streamlit 应用（降低使用门槛） |

---

## 三、技术路线

### 3.1 数据体系

| 指数 | 分量 | 数据来源 | 分辨率 | 年份 |
|------|------|---------|--------|------|
| **HAI** | 人口密度 | WorldPop | 1 km | 2020 |
| | GDP密度 | Chen et al. (2022) | 1 km | 2019 |
| | 夜间灯光 | 国家青藏高原数据中心 (Zhang 2021) | 1 km | 2020 |
| | 放牧强度 | Gridded Livestock of the World | 1 km | 2015 |
| | 土地利用强度 | 中科院 RESDC | 1 km | 2020 |
| | 道路密度 | OpenStreetMap | 矢量 | 2024 |
| **TDPI** | 景区等级与规模 | 百度地图 POI + 四川省文旅厅 | 点/面 | 2024 |
| | 旅游设施密度 | OSM tourism 标签 | 点 | 2024 |
| | 旅游服务集聚度 | 酒店/餐饮/交通 POI | 点 | 2024 |
| **EQI** | BRI（生物多样性） | 国家青藏高原数据中心 | 1 km | 2020 |
| | FVC（植被覆盖度） | MODIS MOD13A3 | 1 km | 2020 |
| | WATER（水源涵养） | Wang (2022) | 1 km | 2020 |
| | PM2.5（空气质量） | WUSTL ACAG V5.GL.02 | 0.01° | 2020 |
| | EROSION（土壤侵蚀） | 中科院 RESDC | 1 km | 2020 |
| **自然控制** | 高程/坡度/起伏度 | SRTM DEM | 1 km | — |
| | 气温/降水 | TerraClimate | ~4 km | 2020 |

### 3.2 分析方法

```
原始数据 → 重采样至统一1km网格 (EPSG:6933 等面积投影)
         → 归一化处理 (0-1)
         → 权重合成 (HAI / TDPI / EQI)
         → 自然本底控制回归 (5 自然因子 → EQI, 岭惩罚 + 50km空间CV)
         → 四象限冲突分区 (HAI 中位数 × EQI 中位数)
         → TDPI 叠加 → 三级管理优先区
         → 县域分区统计 → 31县治理优先级排名
         → 非线性结构变化点检测 (分段线性回归 + ΔAIC)
         → 31km局部滑动窗口秩相关
```

### 3.3 关键发现

| 指标 | 数值 |
|------|------|
| 有效分析面积 | 232,487 km²（1km 像元） |
| TDPI 正压力区 | 7,780 km²（3.3%） |
| 冲突预警区（高HAI-低EQI） | 约 2,167 km²（0.9%） |
| TDPI 候选阈值 | 0.099（ΔAIC=-9.49） |
| 局部负相关窗口比例 | 69.97%（70%窗口TDPI↑时EQI↓） |
| 治理排名 #1 | 泸定县（优先级指数 0.2759） |

---

## 四、系统功能

### 4.1 功能总览

```
┌─────────────────────────────────────────────────────────┐
│           川西旅游生态冲突预警与规划辅助平台              │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  📊 模式一：展示已分析数据                                │
│  ├─ 🗺️  交互地图         7个图层可切换，县域边界叠加     │
│  ├─ 🏛️  县域诊断          冲突饼图 + EQI雷达 + 智能诊断  │
│  ├─ ⚠️  预警面板          三级预警 + Top10 + 阈值说明   │
│  └─ 📋  关于平台          方法说明与数据来源             │
│                                                         │
│  🔬 模式二：现场分析                                     │
│  ├─ 📤  上传数据做县域统计  任意GeoTIFF → 31县分区统计   │
│  ├─ ⚙️  阈值探索器         滑块调整TDPI阈值 → 重分类      │
│  ├─ 📈  情景模拟           旅游增长20%-200% → 风险预测   │
│  └─ 🎚️  EQI权重自定义      5分量权重调整 → 新EQI/冲突图  │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 4.2 GeoScene Pro 工具箱

| 工具 | 功能 | 输入 | 输出 |
|------|------|------|------|
| **县域旅游生态风险评估** | 选定县 → 裁剪栅格 → 分区统计 → 风险简报 | 县界矢量 + 管理优先区栅格 | .txt 风险评估简报 |
| **全州冲突预警扫描** | 全州扫描 → 提取一级预警区 → 统计分析 | 冲突分区栅格 + 管理优先区栅格 + 县界 | 预警区.tif + 统计摘要 |
| **点位诊断查询** | 地图选点 → 提取冲突/优先级/TDPI/EQI | 点击坐标 + 4个输入栅格 | 点位诊断报告 |

---

## 五、运行说明

### 5.1 Streamlit Web 应用

**环境要求**

- Python 3.9+
- 依赖包（`requirements.txt`）：streamlit, folium, rasterio, geopandas, matplotlib, numpy, pandas, Pillow

**启动步骤**

```bash
# 1. 进入工具目录
cd tool/

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动应用
streamlit run app.py
```

浏览器自动打开 `http://localhost:8501`。

**数据准备**

将分析结果栅格（GeoTIFF）和县域统计数据（GeoJSON/CSV）放置于 `data/` 目录下，目录结构如下：

```
data/
├── EQI/
│   ├── EQI_v02_bbox_1km.tif           # EQI 合成栅格
│   └── components/                    # EQI 5个分量栅格
│       ├── BRI_norm_1km.tif
│       ├── FVC_1km.tif
│       ├── WATER_norm_1km.tif
│       ├── PM25_reverse_norm_1km.tif
│       └── EROSION_quality_1km.tif
├── HAI/
│   └── HAI_阿坝甘孜_1km_20260809.tif
├── TDPI叠加后的一级、二级、三级管理优先区/
│   ├── HAI_EQI_conflict_4class_1km.tif       # 四类冲突分区
│   ├── management_priority_3class_1km.tif     # 三级管理优先区
│   ├── TDPI_v02_aligned_1km.tif               # TDPI 栅格
│   └── conflict_priority_stats.json           # 统计元数据
├── 县域旅游生态治理优先级/
│   └── 03_表格与矢量/
│       ├── 县域管理优先区统计.geojson
│       └── 县域管理优先区统计.csv
├── 02_EQI_natural_adjusted_residual.tif       # 自然校正残差
├── 06_TDPI_EQI_adjusted_relationship_class.tif # 校正后关系分类
└── controlled_analysis_summary.json            # 自然本底控制分析报告
```

### 5.2 GeoScene Pro 工具箱

**加载方式**

1. 打开 GeoScene Pro（或 ArcGIS Pro 3.x+）
2. 打开 Catalog 面板 → 右键 Toolboxes → Add Toolbox
3. 选择 `川西旅游生态预警工具箱.pyt`

**使用前提**

- 需将研究区相关栅格数据在 GeoScene Pro 中注册为数据源
- 需县域边界矢量要素类（shapefile / geodatabase feature class）
- arcpy 语法在 GeoScene Pro 和 ArcGIS Pro 中完全兼容

---

## 六、适用场景

| 用户角色 | 使用场景 | 推荐功能 |
|---------|---------|---------|
| 州/县级自然资源局 | 新旅游项目选址前评估 | 县域诊断 + 点位查询 |
| 文旅局 | 景区容量管控决策 | 情景模拟（增长20%/50%时哪些县升级） |
| 生态环境局 | 生态红线预警 | 全州预警扫描 + 阈值探索器 |
| 规划编制单位 | 旅游发展规划修编 | 四象限冲突图 + 治理优先级排名 |
| 科研人员 | 参数敏感性分析 | EQI权重自定义 + 上传新数据 |

---

## 七、作品文件清单

```
tool/
├── app.py                          # Streamlit Web 应用主程序
├── 川西旅游生态预警工具箱.pyt       # GeoScene Pro Python 工具箱
├── requirements.txt                # Python 依赖清单
├── README.md                       # 本文件
├── 实时分析功能_可行性分析.md        # 技术可行性论证
└── data/                           # 分析数据（栅格 + 矢量 + 统计）
    ├── EQI/                        # 生态质量指数及分量
    ├── HAI/                        # 人类活动强度指数
    ├── TDPI叠加后的一级、二级、三级管理优先区/  # 核心输出
    ├── 四类冲突图/                   # 冲突分区结果
    ├── 县域旅游生态治理优先级/        # 县域排名与统计
    └── 自然本底控制分析输出/          # 控制分析结果 + QA图表
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
| 队长 | （填写） | 总体设计、分析方法、TDPI构建 |
| 队员 | （填写） | 数据处理、栅格计算、GIS制图 |
| 队员 | （填写） | 工具开发、前端展示、文档撰写 |

**指导教师**：（填写）

**所在院校**：（填写）

---

> © 2026 三人小组 · 易智瑞杯中国大学生GIS软件开发竞赛
