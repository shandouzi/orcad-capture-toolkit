# 主工作流详细说明

本文档说明跨板连接器网络验证的完整工作流程。

## 概述

该工作流用于验证两块板通过连接器对接时，对应引脚的网络名是否一致。典型场景：板 A 的连接器 J1 与板 B 的连接器 J1 对接，验证两端引脚的网络名是否匹配。

## 前置准备

### 1. 准备连接器引脚映射表

创建 `connector_pin_map.csv`，定义两板连接器的引脚对接关系：

```csv
ConnectorPin,Row,Col,MatingPin,MatingRow,MatingCol
A3,A,3,L3,L,3
A4,A,4,L4,L,4
...
```

- `ConnectorPin`：板 A 连接器的引脚编号
- `MatingPin`：板 B 连接器对应引脚的编号
- `Row`/`Col`：引脚的物理位置（用于可视化）

对于同型对接连接器，配对关系通常为行对称：A↔L, B↔K, C↔J, D↔H, E↔G, F↔F。

### 2. 确认 OrCAD 环境

- 已安装 OrCAD Capture CIS 17.2+
- 在 Capture 中分别打开两块板的 DSN 文件

## 步骤 1：提取引脚-网络数据

在 OrCAD Capture 中，分别为两块板执行数据提取。

### 1.1 提取板 A 数据

```
1. 在 Capture 中打开板 A 的 DSN 文件
2. 在 Command Window 中输入：set targetRefDes "J1"
3. 回车执行
4. 输入：source ./scripts/get_component_nets.tcl
5. 回车执行
6. 得到输出文件：board_a_J1_pin_nets.csv
```

### 1.2 提取板 B 数据

```
1. 在 Capture 中打开板 B 的 DSN 文件
2. 在 Command Window 中输入：set targetRefDes "J1"
3. 回车执行
4. 输入：source ./scripts/get_component_nets.tcl
5. 回车执行
6. 得到输出文件：board_b_J1_pin_nets.csv
```

### 1.3 输出格式

两个 CSV 文件具有相同的列结构：

| 列 | 含义 |
|---|---|
| RefDes | 器件位号 |
| PartValue | 器件值/型号 |
| PinNumber | 引脚编号 |
| PinName | 引脚名称 |
| NetName | 网络名 |
| PagePath | 层级路径 |

### 注意事项

- `targetRefDes` 留空可导出全部器件，但大型工程耗时较长
- 脚本会递归遍历层次化设计，自动进入子模块
- 控制台会预览前 20 行数据，可快速验证
- CSV 文件使用 UTF-8 BOM 编码

## 步骤 2：网络对比

在 Windows 命令行中运行对比脚本。

### 2.1 运行命令

```
py scripts/match_nets_interactive.py
```

### 2.2 选择文件

脚本弹出 GUI 对话框（无 GUI 环境自动回退命令行模式），依次选择：

1. 板 A 的 `pin_nets.csv`
2. 板 B 的 `pin_nets.csv`
3. `connector_pin_map.csv`

### 2.3 输出文件

| 文件 | 说明 |
|---|---|
| `match_report_<A>_vs_<B>.csv` | 匹配报告 CSV |
| `match_report_<A>_vs_<B>.xlsx` | Excel 格式，MISMATCH 行黄色高亮 |

### 2.4 匹配状态说明

| 状态 | 含义 | 需要关注 |
|---|---|---|
| OK | 两端网络名完全一致 | 否 |
| MISMATCH | 两端网络名不同 | **是** |
| NC | 两端均为空（未连接） | 视情况 |
| NC_A | 仅 A 侧为空 | **是** |
| NC_B | 仅 B 侧为空 | **是** |
| MISSING | 引脚未在映射表中找到 | **是** |

### 2.5 注意事项

- 网络名比较为严格字符串匹配。命名规范差异（如 `VCC_3V3` 与 `VCC_3V3_MODULE`）视为 MISMATCH
- 匹配基于 PinNumber + 映射表，不基于 PinName
- 源文件仅做一次 `.bak` 备份
- 控制台输出包含 MISMATCH 明细，可快速定位问题

## 步骤 3（可选）：可视化审查

### 3.1 专用可视化（固定布局）

```
py scripts/generate_visualization.py
```

适用于 Molex 209311-1115（688 引脚）等特定连接器。

### 3.2 通用可视化（任意连接器）

```
py scripts/generate_universal_viz.py
```

选择匹配报告 CSV 和引脚映射 CSV，支持上下/左右布局方向选择。

### 3.3 可视化功能

- 鼠标悬停引脚显示详情
- 点击引脚高亮对端
- 颜色编码：绿=OK，红=MISMATCH，灰=NC，蓝=MISSING
- 顶部状态徽章栏显示各类别统计
- 单个自包含 HTML 文件，无需服务器

## 典型问题排查

### MISMATCH 数量过多

1. 检查命名规范差异（如模块前缀/后缀不同）
2. 检查引脚映射表是否正确
3. 确认两板使用的连接器型号一致

### MISSING 引脚

1. 检查引脚映射表是否覆盖所有引脚
2. 确认 `targetRefDes` 是否指定了正确的连接器位号

### 网络名为空

1. 确认引脚在原理图中确实连接了网络
2. 检查层次化设计中的跨页连接
3. 确认引脚不是 NC（No Connect）引脚
