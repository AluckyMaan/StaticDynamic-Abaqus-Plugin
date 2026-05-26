# StaticDynamic Abaqus 插件

[English README](README.md)

当前版本：`0.2.0`

StaticDynamic 是一个 Abaqus/CAE Python 插件，用于土体静动力转换和粘弹性人工边界施加。当前版本重点支持复杂土-结构模型的外部地应力平衡结果导入，再由插件完成边界节点识别、反力读取、粘弹性边界施加和静力反力回填。

<p align="center">
  <img src="docs/assets/v0.2.0-release-hero.png" alt="StaticDynamic v0.2.0 多层土粘弹性边界转换" width="900">
</p>

## 页面概览

插件将已经完成地应力平衡的土体模型转换为带粘弹性人工边界的动力分析模型。程序会按边界面/边、相邻材料贡献和节点控制面积或长度，对边界节点进行分组和加权。

<p align="center">
  <img src="docs/assets/v0.2.0-static-dynamic-workflow.svg" alt="StaticDynamic 程序运行框图：边界识别、地应力反力输入、平衡检查、分层分组、边界转换" width="900">
</p>

### 插件 GUI

Abaqus/CAE 对话框将模型参数、地应力反力来源、动力分析参数和可选输出控制集中在同一套流程中。

<p align="center">
  <img src="docs/assets/staticdynamic-plugin-gui.png" alt="StaticDynamic Abaqus 插件 GUI 对话框" width="760">
</p>

### 粘弹性边界施加示例

以下图片直接截取自 Abaqus/CAE，相互作用显示中可见插件生成的 `SpringDashpotToGround` 粘弹性边界符号。

<table>
  <tr>
    <td width="50%" align="center">
      <img src="docs/assets/abaqus-interaction-viscous-boundary-readme.png" alt="Abaqus 相互作用视图中显示多层土粘弹性边界符号" width="100%"><br>
      <sub>整体相互作用视图，可见粘弹性边界符号。</sub>
    </td>
    <td width="50%" align="center">
      <img src="docs/assets/abaqus-interaction-side-boundary-readme.png" alt="Abaqus 侧视图中显示多层土侧边界弹簧阻尼符号" width="100%"><br>
      <sub>侧边界细节视图，可见分层节点分组。</sub>
    </td>
  </tr>
</table>

## 主要功能

- 自动识别 3D 五个截断边界面，或 2D 三条截断边界边。
- 支持 `X / Y / Z` 竖向轴选择，并自动调整 Abaqus 视图。
- 支持多层土体边界参数：按边界相邻单元材料自动分组。
- 层间界面节点按相邻材料贡献分摊弹簧和阻尼。
- 根据节点控制面积或控制长度加权粘弹性边界参数。
- 使用 Abaqus 可视化的 `SpringDashpotToGround` 施加粘弹性边界。
- 支持从外部地应力平衡结果读取边界反力：
  - `ODB`：从平衡后的 ODB 指定 step 最后一帧读取 `RF`。
  - `CSV`：读取边界节点反力表。
- ODB 输入时检查最后一帧位移场 `U`，默认容许值为 `1.0e-4`。
- 导出 `BoundaryInfo.csv`，用于外部地应力反力表生成和核对。

## 适用思路

插件不再内部求解地应力平衡。复杂结构、分步施工、接触、开挖、隧道、桩土等问题，应先在 Abaqus 中按真实工况完成地应力平衡，并确认最后一帧位移场 `U` 满足工程要求。随后将平衡后的 ODB 或边界反力 CSV 提供给本插件，插件负责完成静力边界到粘弹性动力边界的转换。

## 安装

将本仓库文件夹复制到 Abaqus 插件搜索路径，例如：

```text
C:\Users\<USER>\abaqus_plugins\StaticDynamic_v1
```

重启 Abaqus/CAE 后，插件菜单中应出现 `StaticDynamic v0.2.0`。

## 基本流程

1. 在 Abaqus/CAE 中打开或建立土体模型。
2. 确保土体材料包含弹性参数和密度。
3. 在模型中完成地应力平衡，并检查 ODB 最后一帧 `U`。
4. 打开 StaticDynamic 插件。
5. 填写模型名、土体部件名、实例名、节点集和竖向轴。
6. 选择地应力反力来源：
   - `ODB`
   - `CSV`
7. 选择地应力文件和 step 名称。
8. 勾选 `Node Set Establishment` 和 `Spring Damping`。
9. 运行插件。
10. 检查生成的节点集、`SpringDashpotToGround` 和 `SD_RF_*` 反力荷载。

## 地应力输入

### ODB

ODB 输入要求：

- ODB 来自已经完成地应力平衡的模型。
- 指定 step 的最后一帧包含 `U` 和 `RF` 场输出。
- ODB 中的实例名和当前 CAE 模型中的土体实例名一致。
- 边界节点编号和当前模型一致。

插件会检查最大位移：

```text
Umax <= Balance Tol
```

默认：

```text
Balance Tol = 1.0e-4
```

若不满足，插件会停止静动边界转换。

### CSV

CSV 输入格式：

```csv
nodeLabel,RF1,RF2,RF3
1,-441759.12,441759.12,1293986.8
2,-441759.12,-441759.12,1293986.8
```

也支持无表头四列数据：

```csv
1,-441759.12,441759.12,1293986.8
2,-441759.12,-441759.12,1293986.8
```

CSV 方式无法检查位移场，用户需要自行保证地应力平衡已经满足要求。

## BoundaryInfo.csv

勾选 `Node Information` 后，插件会导出 `BoundaryInfo.csv`，字段包括：

```csv
nodeLabel,x,y,z,faceName,materialFractions,areaOrLength
```

该文件可用于：

- 核对自动识别的人工边界节点。
- 查看节点属于哪个边界面。
- 查看多层土材料分摊比例。
- 生成或审查外部边界反力 CSV。

## 边界逻辑

3D 土体自由顶面模型：

- 底面
- 两个 X 侧面
- 两个另一水平轴侧面

2D 土体模型：

- 底边
- 左边
- 右边

自由顶面不施加粘弹性人工边界。

## 验证状态

当前版本已验证：

- 均质 3D 土体五面粘弹性边界。
- 两层 3D 土体材料分组和界面节点分摊。
- 1 m 加密网格下的多层土边界识别。
- ODB 地应力反力输入。
- CSV 地应力反力输入。
- ODB 位移平衡阈值拦截。

## 注意

本插件不能替代工程模型验证。正式计算前，应使用基准算例、网格敏感性分析和足够远的截断边界距离验证边界参数。

## 许可证

MIT License.
