# OrCAD Capture Automation Toolkit

OrCAD Capture CIS 17.2 的 TCL + Python 自动化工具链。用于原理图数据提取、跨板连接器网络验证、OLB 库引脚检查、层次化工程目录导出与交互式可视化。

> ## 背景
>
> 本工具链的最初需求来源于 **OAM（OAM Module）与 UBB（UBB Board）板卡互联检查**。在实际项目中，需要验证两块板通过连接器对接时引脚级网络名的一致性，由此逐步开发了从数据提取、网络对比到交互式可视化的完整工具链。
>
> 虽然脚本中的部分设计（如连接器引脚映射、拓扑发现算法）带有 OAM/UBB 场景的痕迹，但核心功能已具备通用性，可扩展至任意板卡之间的连接器网络验证。使用者可根据自身板卡的连接器型号、引脚排列和命名规范，按需修改配置文件和脚本参数。
>
> 笔者在 Cadence 自动化方面经验尚浅，本仓库是对学习和实践过程的记录与分享。如有问题或改进建议，欢迎提 Issue 或 PR。

## 功能一览

| 脚本 | 语言 | 功能 |
|------|------|------|
| `get_olb_pins.tcl` | TCL | 从 OLB 库提取器件引脚信息，检查封装正确性 |
| `get_page_mapping.tcl` | TCL | 导出层次化工程的页码-页面名称映射 |
| `get_component_nets.tcl` | TCL | 提取指定位号器件的引脚-网络数据（CSV） |
| `match_nets_interactive.py` | Python | 跨板连接器网络对比，生成匹配报告 |
| `generate_visualization.py` | Python | 生成连接器逐引脚交互式可视化（HTML） |
| `generate_universal_viz.py` | Python | 通用连接器可视化（从引脚映射表自动推断布局） |
| `discover_oam_topology.py` | Python | 从引脚数据自动发现互联拓扑（AC 耦合电容追踪） |

## 适用场景

- 两块板通过连接器对接时的网络名一致性验证
- OLB 元器件封装引脚定义正确性检查
- 层次化原理图工程全局页码目录导出
- 从原理图导出任意器件的引脚-网络映射
- 连接器互联拓扑自动发现与可视化

## 环境要求

| 组件 | 要求 |
|------|------|
| OrCAD Capture CIS | 17.2+（TCL 脚本需在 Capture Command Window 中运行） |
| Python | 3.x |
| Python 依赖 | `openpyxl`（`pip install openpyxl`） |
| 操作系统 | Windows |
| Python 启动方式 | 使用 `py` 命令 |

## 快速开始

### 1. OLB 库引脚检查

在 Capture Library Editor 中打开 OLB 文件，执行：

```tcl
source ./scripts/get_olb_pins.tcl
```

输出：`olb_pin_info.csv`、`olb_pin_info_detail.csv`

### 2. 工程页面目录导出

在 Capture Design 模式中打开 DSN 文件，执行：

```tcl
source ./scripts/get_page_mapping.tcl
```

输出：`page_mapping.csv`

### 3. 器件引脚-网络数据提取

```tcl
set targetRefDes "J1"
source ./scripts/get_component_nets.tcl
```

输出：`<设计名>_<RefDes>_pin_nets.csv`

### 4. 跨板网络对比

```
py scripts/match_nets_interactive.py
```

弹出 GUI 对话框选择两个 CSV 文件和引脚映射表，输出匹配报告（CSV + XLSX）。

### 5. 可视化

```
py scripts/generate_universal_viz.py
```

选择匹配报告 CSV 和引脚映射 CSV，生成交互式 HTML。

## 工作流程图

```
┌─────────────────────────────────────────────────────────────┐
│                      独立功能（随时可用）                      │
│                                                             │
│  ┌──────────────────────┐    ┌──────────────────────────┐   │
│  │ get_olb_pins.tcl     │    │ get_page_mapping.tcl     │   │
│  │ OLB ──> 引脚信息CSV  │    │ DSN ──> 页面目录CSV      │   │
│  └──────────────────────┘    └──────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    主工作流（按顺序执行）                      │
│                                                             │
│  步骤 1：数据提取（OrCAD 内运行，两块板各执行一次）           │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  get_component_nets.tcl                              │   │
│  │                                                      │   │
│  │  DSN (Board-A) ──> board_a_J1_pin_nets.csv           │   │
│  │  DSN (Board-B) ──> board_b_J1_pin_nets.csv           │   │
│  └──────────────────────┬───────────────────────────────┘   │
│                         │                                   │
│  步骤 2：网络对比（Windows 命令行运行）                       │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  match_nets_interactive.py                           │   │
│  │                                                      │   │
│  │  Board-A CSV ──┐                                     │   │
│  │  Board-B CSV ──┼──> match_report.csv / .xlsx         │   │
│  │  pin_map.csv ──┘                                     │   │
│  └──────────────────────┬───────────────────────────────┘   │
│                         │                                   │
│  步骤 3（可选）：可视化审查                                  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  generate_visualization.py     （专用布局）           │   │
│  │  generate_universal_viz.py     （通用布局）           │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## 各脚本详细说明

### get_olb_pins.tcl

从已打开的 OLB 库中提取所有器件的完整引脚信息。

**使用条件：** Capture Library Editor 中已打开 OLB 文件

**输出：**
- `olb_pin_info.csv` — 纯数据，Excel 筛选排序方便
- `olb_pin_info_detail.csv` — 含分节标题和汇总信息

**CSV 列：**

| 列 | 含义 | 示例 |
|---|---|---|
| PartName | 元器件名 | GTL2003PW |
| PartRef | 参考位号前缀 | U |
| Section | Section 编号 | 1, 2, 3... |
| View | Symbol 视图 | Normal / Convert |
| PinIndex | Pin 顺序索引 | 0, 1, 2... |
| PinName | 引脚名称 | GND, S1, D1 |
| PinNumber | 引脚编号 | 1, NAG62, NP47 |
| PinPosition | Pin 位置 | 0, 1, 2... |
| PinType(Enum) | 引脚类型（枚举） | Power, Input, Passive |
| PinType(Semantic) | 引脚类型（语义） | Power, Passive |
| Package | 封装名 | GTL2003PW |

**核心特性：**
- 同时提取枚举值和语义字符串的 PinType（两者可能不一致）
- 支持多 Section 器件（门电路）
- 遍历库中所有器件

---

### get_page_mapping.tcl

从已打开的 DSN 中提取全局页码与页面名称的映射关系。

**使用条件：** Capture Design 模式中已打开 DSN 文件

**输出：**
- `page_mapping.csv` — 列：`GlobalPage, LocalPage, LocalTotal, PageName, Module`

**核心特性：**
- 使用 `DboRefDesUtils_GetPagesAsPerPagesInTitleBlockOrder` 获取标题栏正确排序
- 同时提取全局序号和模块内本地页码/总页数
- 自动去除页面名称前的字母前缀
- 从标题栏提取模块名称
- 自动处理多级层次化设计

---

### get_component_nets.tcl

从已打开的 DSN 中提取指定位号器件的引脚-网络映射关系。两块板各执行一次。

**使用条件：** Capture Design 模式中已打开 DSN 文件

**用法：**

```tcl
; 在 Command Window 中先设置目标位号
set targetRefDes "J1"
; 然后执行脚本
source ./scripts/get_component_nets.tcl
```

`targetRefDes` 留空则导出全部器件。

**输出：**
- `<设计名>_<RefDes>_pin_nets.csv` — 列：`RefDes, PartValue, PinNumber, PinName, NetName, PagePath`

**核心特性：**
- 递归遍历层次化原理图
- 自动提取设计名生成文件名
- 控制台预览前 20 行数据
- 未找到目标时列出已发现的位号供参考
- 同时通过 Net 和 Wire 两条路径获取网络名

---

### match_nets_interactive.py

通过物理引脚映射表匹配两块板连接器的引脚网络，生成对比报告。

**依赖：** `pip install openpyxl`

**输入文件：**

| 文件 | 必需列 | 来源 |
|------|--------|------|
| Board-A 引脚网络 CSV | `PinNumber, PinName, NetName` | `get_component_nets.tcl` |
| Board-B 引脚网络 CSV | `PinNumber, PinName, NetName` | `get_component_nets.tcl` |
| 连接器引脚映射 CSV | `ConnectorPin, MatingPin` | `config/connector_pin_map.csv` |

**输出：**
- `match_report_<标签A>_vs_<标签B>.csv`
- `match_report_<标签A>_vs_<标签B>.xlsx`（MISMATCH 行黄色高亮）

**匹配状态：**

| 状态 | 判定条件 |
|------|----------|
| OK | 两侧网络名完全一致 |
| MISMATCH | 两侧网络名不同 |
| NC | 两侧网络均为空 |
| NC_A | A 侧为空，B 侧非空 |
| NC_B | A 侧非空，B 侧为空 |
| MISSING | 引脚未在映射表中找到 |

---

### generate_visualization.py

从匹配报告生成交互式 HTML 可视化页面。专为 Molex 209311-1115（688 引脚）连接器设计。

**输出：** 单个自包含 HTML 文件（CSS + JS 全部内嵌）

**交互功能：**
- 悬停显示引脚详情
- 点击引脚高亮对端
- 颜色编码：绿=OK，红=MISMATCH，灰=NC，蓝=MISSING
- Board-B 镜像显示（反映物理对接方向）

---

### generate_universal_viz.py

通用版可视化工具。从 `connector_pin_map.csv` 自动推断连接器行列结构，支持任意连接器。

**额外输入：** 引脚映射 CSV 需包含 `Row, Col, MatingRow, MatingCol` 列

**与 generate_visualization.py 的区别：**

| 对比项 | generate_visualization.py | generate_universal_viz.py |
|--------|--------------------------|---------------------------|
| 连接器布局 | 硬编码 688 引脚 | 从 CSV 自动推断 |
| 适用范围 | 特定连接器 | 任意连接器 |
| 布局方向 | 仅上下 | 上下/左右可选 |

---

### discover_oam_topology.py

从全量引脚-网络 CSV 数据中，通过 AC 耦合电容追踪自动发现连接器之间的互联拓扑。

**用法：**

```
py scripts/discover_oam_topology.py <pin_nets_csv> --connectors J1 J2 ... K8 --output-dir <dir>
```

**输出：**
- `topology_report.html` — 交互式环形网络图 + 详情表
- `topology_pair_detail.csv` — 按连接器对分组的详情
- `topology_detail.csv` — 全量拓扑链路

**核心特性：**
- 不依赖网络名命名格式，仅靠 NetName 唯一性匹配
- 自动识别 AC 耦合电容（C 开头 + 2 引脚 + 两侧均有连接器引脚）
- 自然排序（差分对 _P/_N 紧邻）
- 网络名编号不匹配自动红色高亮

## 已知限制

- OrCAD 17.2 的 TCL API **不支持网络名写入**（所有 Set 操作静默失败），SPB 23.1+ 版本可能支持
- TCL 脚本必须在 Capture Command Window 中运行，无法独立执行
- CSV 读取使用 UTF-8 BOM 编码（OrCAD 导出的 CSV 可能是 gb2312，Python 脚本已做兼容）
- 仅支持 Windows 平台

## 配置文件

### connector_pin_map.csv

连接器物理引脚对接映射表。定义了同型对接连接器的引脚配对关系。

**格式：**
```csv
ConnectorPin,Row,Col,MatingPin,MatingRow,MatingCol
A3,A,3,L3,L,3
A4,A,4,L4,L,4
```

**属性：**
- 编码：UTF-8 with BOM
- 配对关系：A-L, B-K, C-J, D-H, E-G, F-F
- 本文件是 `match_nets_interactive.py` 和 `generate_universal_viz.py` 的共享输入

## 文档

| 文档 | 说明 |
|------|------|
| [API 参考](docs/api_reference.md) | OrCAD Capture TCL Dbo API 调用参考 |
| [踩坑汇总](docs/pitfalls.md) | Cadence TCL 开发中的常见陷阱与解决方案 |
| [工作流说明](docs/workflow.md) | 主工作流详细步骤说明 |

## License

MIT License
