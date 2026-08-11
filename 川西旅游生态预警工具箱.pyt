# -*- coding: utf-8 -*-
"""
川西旅游生态预警工具箱
Western Sichuan Tourism-Ecology Early Warning Toolbox

使用方式：
    1. 打开 GeoScene Pro / ArcGIS Pro
    2. Catalog → Toolboxes → Add Toolbox → 选择本文件
    3. 工具箱面板中运行三个工具

兼容性：GeoScene Pro 3.x+ / ArcGIS Pro 3.x+
"""

import arcpy
import os
import json
import csv
from pathlib import Path

# ========== 工具箱定义 ==========
class Toolbox:
    def __init__(self):
        self.label = "川西旅游生态预警工具箱"
        self.alias = "WesternSichuanEcoTourismTools"
        self.description = "川西地区旅游业发展对生态环境影响的预警与规划辅助工具集"
        self.tools = [CountyRiskReport, ConflictScan, PointDiagnosis]

# ========== 工具1: 县域风险评估 ==========
class CountyRiskReport:
    def __init__(self):
        self.label = "县域旅游生态风险评估"
        self.description = "根据现有冲突分区和管理优先区数据，对指定县域生成旅游生态风险评估简报"
        self.category = "评估"

    def getParameterInfo(self):
        param0 = arcpy.Parameter(
            displayName="县域统计GeoJSON",
            name="county_geojson",
            datatype="DEFile",
            parameterType="Required",
            direction="Input")
        param0.filter.list = ["json", "geojson"]

        param1 = arcpy.Parameter(
            displayName="管理优先区栅格",
            name="mgmt_raster",
            datatype="DERasterDataset",
            parameterType="Required",
            direction="Input")

        param2 = arcpy.Parameter(
            displayName="目标县名",
            name="county_name",
            datatype="GPString",
            parameterType="Required",
            direction="Input")

        param3 = arcpy.Parameter(
            displayName="县域边界要素",
            name="county_boundary",
            datatype="DEFeatureClass",
            parameterType="Required",
            direction="Input")

        param4 = arcpy.Parameter(
            displayName="输出报告路径",
            name="output_dir",
            datatype="DEWorkspace",
            parameterType="Required",
            direction="Input")

        return [param0, param1, param2, param3, param4]

    def updateParameters(self, parameters):
        return

    def updateMessages(self, parameters):
        return

    def execute(self, parameters, messages):
        county_geojson = parameters[0].valueAsText
        mgmt_raster = parameters[1].valueAsText
        county_name = parameters[2].valueAsText
        county_boundary = parameters[3].valueAsText
        output_dir = parameters[4].valueAsText

        arcpy.AddMessage(f"========== 川西旅游生态风险评估 ==========")
        arcpy.AddMessage(f"目标县: {county_name}")
        arcpy.AddMessage(f"管理优先区数据: {mgmt_raster}")
        arcpy.AddMessage(f"输出目录: {output_dir}")

        try:
            # 1. 按属性选择目标县
            arcpy.AddMessage("\n[1/4] 提取目标县域边界...")
            county_layer = "county_lyr"
            arcpy.MakeFeatureLayer_management(county_boundary, county_layer)
            arcpy.SelectLayerByAttribute_management(county_layer, "NEW_SELECTION",
                                                    f"name = '{county_name}'")
            result = arcpy.GetCount_management(county_layer)
            if int(result.getOutput(0)) == 0:
                arcpy.AddError(f"未找到名为 '{county_name}' 的县")
                return

            # 2. 按县域裁剪管理优先区栅格
            arcpy.AddMessage("\n[2/4] 裁剪管理优先区栅格...")
            mgmt_clip = os.path.join(output_dir, f"{county_name}_mgmt_clip.tif")
            arcpy.management.Clip(
                mgmt_raster,
                "#",
                mgmt_clip,
                county_layer,
                "#",
                "ClippingGeometry"
            )
            arcpy.AddMessage(f"   已保存: {mgmt_clip}")

            # 3. Zonal Statistics 统计各级面积
            arcpy.AddMessage("\n[3/4] 计算优先区面积统计...")
            zonal_table = os.path.join(output_dir, f"{county_name}_zonal_stats.dbf")
            arcpy.sa.ZonalStatisticsAsTable(
                county_layer,
                "name",
                mgmt_raster,
                zonal_table,
                "DATA",
                "ALL"
            )

            # 4. 生成简报文本
            arcpy.AddMessage("\n[4/4] 生成风险评估简报...")
            report_path = os.path.join(output_dir, f"{county_name}_风险评估简报.txt")

            # 读取统计数据
            from arcpy.sa import Raster, ZonalStatisticsAsTable
            import numpy as np

            arr = arcpy.RasterToNumPyArray(Raster(mgmt_clip), nodata_to_value=-9999)
            valid = arr[arr > 0]
            level1 = np.sum(arr == 1)
            level2 = np.sum(arr == 2)
            level3 = np.sum(arr == 3)
            total_valid = level1 + level2 + level3

            # 判断风险等级
            if total_valid > 0:
                l1_share = level1 / total_valid
                l2_share = level2 / total_valid
                priority_index = 3 * l1_share + 2 * l2_share
            else:
                l1_share = l2_share = priority_index = 0

            if priority_index > 0.20:
                risk_level = "高风险 (应立即管控)"
            elif priority_index > 0.10:
                risk_level = "中高风险 (需动态监测)"
            elif priority_index > 0.05:
                risk_level = "中等风险"
            else:
                risk_level = "低风险 (维持保护)"

            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(f"川西旅游生态风险评估简报\n")
                f.write(f"{'='*50}\n")
                f.write(f"县名: {county_name}\n")
                f.write(f"风险等级: {risk_level}\n")
                f.write(f"治理优先级指数: {priority_index:.4f}\n")
                f.write(f"\n管理优先区统计 (1km像元):\n")
                f.write(f"  一级优先区 (立即管控): {int(level1)} km² ({l1_share*100:.1f}%)\n")
                f.write(f"  二级优先区 (动态监测): {int(level2)} km² ({l2_share*100:.1f}%)\n")
                f.write(f"  三级优先区 (一般管理): {int(level3)} km²\n")
                f.write(f"  有效分析面积: {int(total_valid)} km²\n")

            arcpy.AddMessage(f"\n✅ {county_name} 风险评估简报已生成:")
            arcpy.AddMessage(f"   {report_path}")
            arcpy.AddMessage(f"   风险等级: {risk_level}")

        except Exception as e:
            arcpy.AddError(f"执行失败: {str(e)}")
            raise


# ========== 工具2: 全州冲突预警扫描 ==========
class ConflictScan:
    def __init__(self):
        self.label = "全州冲突预警扫描"
        self.description = "扫描全州四类冲突分区和管理优先区，输出一级预警区范围和统计摘要"
        self.category = "预警"

    def getParameterInfo(self):
        param0 = arcpy.Parameter(
            displayName="四类冲突分区栅格",
            name="conflict_raster",
            datatype="DERasterDataset",
            parameterType="Required",
            direction="Input")
        param0.filter.list = ["tif"]

        param1 = arcpy.Parameter(
            displayName="管理优先区栅格",
            name="mgmt_raster",
            datatype="DERasterDataset",
            parameterType="Required",
            direction="Input")

        param2 = arcpy.Parameter(
            displayName="县域边界要素",
            name="county_boundary",
            datatype="DEFeatureClass",
            parameterType="Required",
            direction="Input")

        param3 = arcpy.Parameter(
            displayName="输出目录",
            name="output_dir",
            datatype="DEWorkspace",
            parameterType="Required",
            direction="Input")

        return [param0, param1, param2, param3]

    def updateParameters(self, parameters):
        return

    def updateMessages(self, parameters):
        return

    def execute(self, parameters, messages):
        conflict_raster = parameters[0].valueAsText
        mgmt_raster = parameters[1].valueAsText
        county_boundary = parameters[2].valueAsText
        output_dir = parameters[3].valueAsText

        arcpy.AddMessage(f"========== 全州冲突预警扫描 ==========")

        try:
            # 1. 按县域做 Zonal Statistics
            arcpy.AddMessage("\n[1/3] 逐县域统计冲突面积...")
            zonal_conflict = os.path.join(output_dir, "conflict_by_county.dbf")
            arcpy.sa.ZonalStatisticsAsTable(
                county_boundary,
                "name",
                conflict_raster,
                zonal_conflict,
                "DATA",
                "ALL"
            )

            # 2. 提取一级预警区 (冲突区 = 高HAI+低EQI = class 4)
            from arcpy.sa import Raster, Con, ExtractByAttributes
            arcpy.AddMessage("\n[2/3] 提取一级预警区...")

            conflict_obj = Raster(conflict_raster)
            high_risk = Con(conflict_obj == 4, 1, 0)
            high_risk_path = os.path.join(output_dir, "high_risk_zone.tif")
            high_risk.save(high_risk_path)
            arcpy.AddMessage(f"   一级预警区栅格已保存: {high_risk_path}")

            # 3. 生成预警摘要
            arcpy.AddMessage("\n[3/3] 生成预警摘要...")
            arr = arcpy.RasterToNumPyArray(high_risk, nodata_to_value=0)
            high_risk_km2 = int(np.sum(arr))

            report_path = os.path.join(output_dir, "全州冲突预警摘要.txt")
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(f"川西全州旅游生态冲突预警摘要\n")
                f.write(f"{'='*50}\n")
                f.write(f"一级预警区 (冲突+高TDPI) 总面积: {high_risk_km2} km²\n")
                f.write(f"\n预警说明:\n")
                f.write(f"  一级预警区 = 高人类活动强度 + 低生态质量 + 高旅游压力\n")
                f.write(f"  建议措施: 立即暂停新增旅游项目审批，启动受损生态修复\n")

            arcpy.AddMessage(f"\n✅ 预警扫描完成:")
            arcpy.AddMessage(f"   一级预警区: {high_risk_km2} km²")
            arcpy.AddMessage(f"   详细报告: {report_path}")

        except Exception as e:
            arcpy.AddError(f"执行失败: {str(e)}")
            raise


# ========== 工具3: 点位诊断查询 ==========
class PointDiagnosis:
    def __init__(self):
        self.label = "点位诊断查询"
        self.description = "在地图上点击任意位置，返回该点的TDPI/EQI/HAI/冲突类型/管理优先级"
        self.category = "查询"

    def getParameterInfo(self):
        param0 = arcpy.Parameter(
            displayName="查询点坐标 (X, Y)",
            name="point_coords",
            datatype="GPPoint",
            parameterType="Required",
            direction="Input")

        param1 = arcpy.Parameter(
            displayName="四类冲突分区栅格",
            name="conflict_raster",
            datatype="DERasterDataset",
            parameterType="Required",
            direction="Input")

        param2 = arcpy.Parameter(
            displayName="管理优先区栅格",
            name="mgmt_raster",
            datatype="DERasterDataset",
            parameterType="Required",
            direction="Input")

        param3 = arcpy.Parameter(
            displayName="TDPI栅格",
            name="tdpi_raster",
            datatype="DERasterDataset",
            parameterType="Required",
            direction="Input")

        param4 = arcpy.Parameter(
            displayName="EQI栅格",
            name="eqi_raster",
            datatype="DERasterDataset",
            parameterType="Required",
            direction="Input")

        return [param0, param1, param2, param3, param4]

    def updateParameters(self, parameters):
        return

    def updateMessages(self, parameters):
        return

    def execute(self, parameters, messages):
        point = parameters[0].value
        conflict_raster = parameters[1].valueAsText
        mgmt_raster = parameters[2].valueAsText
        tdpi_raster = parameters[3].valueAsText
        eqi_raster = parameters[4].valueAsText

        arcpy.AddMessage(f"========== 点位诊断查询 ==========")
        arcpy.AddMessage(f"查询坐标: ({point.X:.4f}, {point.Y:.4f})")

        try:
            # 创建点要素
            point_fc = "in_memory/query_point"
            arcpy.CreateFeatureclass_management(
                "in_memory", "query_point", "POINT",
                spatial_reference=arcpy.Describe(conflict_raster).spatialReference)
            with arcpy.da.InsertCursor(point_fc, ["SHAPE@"]) as cursor:
                cursor.insertRow([point])

            # 提取值
            def extract_value(raster_path, point_fc):
                result = arcpy.sa.ExtractMultiValuesToPoints(
                    point_fc, raster_path, "BILINEAR")
                with arcpy.da.SearchCursor(result, ["Value"]) as cursor:
                    for row in cursor:
                        return row[0]
                return None

            conflict_val = extract_value(conflict_raster, point_fc)
            mgmt_val = extract_value(mgmt_raster, point_fc)
            tdpi_val = extract_value(tdpi_raster, point_fc)
            eqi_val = extract_value(eqi_raster, point_fc)

            # 解释
            conflict_labels = {1: "低压力-高生态", 2: "高压力-高生态 (协调)",
                              3: "低压力-低生态", 4: "高压力-低生态 (冲突⚠️)"}
            mgmt_labels = {1: "一级优先 (立即管控)", 2: "二级优先 (动态监测)",
                          3: "三级 (一般管理)"}

            arcpy.AddMessage(f"\n📊 诊断结果:")
            arcpy.AddMessage(f"  冲突类型: {conflict_labels.get(conflict_val, '未知')}")
            arcpy.AddMessage(f"  管理优先级: {mgmt_labels.get(mgmt_val, '未知')}")
            arcpy.AddMessage(f"  TDPI值: {tdpi_val:.4f}" if tdpi_val is not None else "  TDPI值: 无数据")
            arcpy.AddMessage(f"  EQI值: {eqi_val:.4f}" if eqi_val is not None else "  EQI值: 无数据")

            # 预警判断
            if conflict_val == 4 and mgmt_val == 1:
                arcpy.AddWarning("⚠️ 该点处于高风险冲突预警区！建议限制新增旅游活动。")
            elif conflict_val == 4:
                arcpy.AddMessage("🟡 该点存在潜在冲突风险，建议关注。")
            else:
                arcpy.AddMessage("✅ 该点当前无重大冲突风险。")

        except Exception as e:
            arcpy.AddError(f"执行失败: {str(e)}")
            raise
