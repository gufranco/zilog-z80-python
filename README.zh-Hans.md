# Zilog Z80

用 Python 实现的 Zilog Z80、NEC µPD780C 和 Zilog Z84C00，可以按单条指令或单个 T 状态驱动。每个机器周期的形态以 Zilog 的用户手册为准，每个操作码的每个 T 状态以逐操作码的语料库为准。

[English](README.md) | [日本語](README.ja.md) | 简体中文 | [繁體中文（香港）](README.zh-HK.md)

[![CI](https://github.com/gufranco/zilog-z80-python/actions/workflows/ci.yml/badge.svg)](https://github.com/gufranco/zilog-z80-python/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/gufranco/zilog-z80-python)](https://github.com/gufranco/zilog-z80-python/releases)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

**3** 种芯片，比对了 **1,604,000** 个一致性用例和 **22,005,372** 个 T 状态，**0** 个失败，**1,438** 个测试，**100%** 语句和分支覆盖率，无依赖

```python
from z80 import Cpu, Memory

cpu = Cpu("z80", Memory(image=bytes([0x3E, 0x42, 0x47, 0x76])))
cpu.reset()

spent = [cpu.step(), cpu.step(), cpu.step()]
print(f"b={cpu.registers.b:02X} pc={cpu.registers.pc:04X}", spent, cpu.held(), cpu.cycles)
```

```
b=42 pc=0004 [7, 4, 4] True 20
```

程序是 `ld a,$42`、`ld b,a`、`halt`。每次 `step()` 执行一条指令，并返回它耗费的 T 状态数：7、4 和 4。`HALT` 执行后，`held()` 为真。`cycles` 读数为 20，因为 `reset()` 在第一条指令之前耗费了 5 个 T 状态。

## 安装

| 要求 | 版本 |
|:--|:--|
| Python | 3.12 或更高 |
| git | 任意，用于克隆 |

```bash
git clone https://github.com/gufranco/zilog-z80-python.git
cd zilog-z80-python
python3 z80/doctor.py
```

本包只导入标准库中的内容。`pip install git+https://github.com/gufranco/zilog-z80-python.git` 只安装 `z80` 包，不含一致性工具。

诊断脚本会报告本机情况、它构建并复位的三种芯片各自的结果，以及语料库是否已获取且完整。它以文件方式运行，这样即使包无法导入，它也仍能报告。所有检查都通过时退出码为 0，否则为 1。提交任何缺陷报告时，请粘贴它的完整输出。在全新的检出上，它以如下内容结尾：

```
  8 checks, nothing to report
```

版本遵循[语义化版本](https://semver.org/)，由 semantic-release 根据提交历史生成。每个版本都会打标签，并列在[发布页面](https://github.com/gufranco/zilog-z80-python/releases)上。

## 接口

下面的所有内容都从 `z80` 导出。其他内容均不公开。

### 构建芯片

`Cpu(model, memory=None, fill=None, ports=None, seed=UNSET_SEED, recording=False, shape="manual")` 构建一个芯片，已上电但未复位。

| 参数 | 含义 |
|:--|:--|
| `model` | 必填。型号名称或别名，忽略大小写和分隔符。省略时抛出 `UnknownModelError`，其中列出所有型号 |
| `memory` | 任何具有 `read8(address)` 和 `write8(address, value)` 的对象。芯片保留传入的那个对象。省略时，芯片构建一个 `SparseMemory` |
| `fill` | 仅在省略 `memory` 时使用：构建一个每处都是该字节的 64 KB `Memory` |
| `ports` | 任何具有 `read(address)` 和 `write(address, value)` 的对象。省略时，输入读取型号的浮空输出，输出不去往任何地方 |
| `seed` | 为寄存器的上电乱序提供种子 |
| `recording` | 为 `True` 时，在 `cpu.bus.log` 中保留逐 T 状态日志 |
| `shape` | `"manual"` 或 `"recording"`，即读取每个控制引脚所依据的边沿。其他值抛出 `UnknownShape` |

### 运行

| 调用 | 作用 | 返回 |
|:--|:--|:--|
| `reset()` | 驱动 RESET：先是 Zilog 规定的引脚最少保持的 3 个 T 状态，再是芯片在释放后耗费的 2 个。将 `pc`、`i`、`r` 和 `im` 置 0，清除两个中断触发器和 `steps`，其他寄存器保持原样 | 该 `Cpu` |
| `step()` | 执行一条指令；处于暂停状态时执行一个 `HALT` 周期 | 耗费的 T 状态数 |
| `run_for(cycles)` | 执行完整的指令，直到至少经过 `cycles` 个 T 状态 | 耗费的 T 状态数，可能超过 `cycles` |
| `run_until(check, limit=None)` | 在 `check(cpu)` 为假时持续单步执行。执行 `limit` 条指令后抛出 `RunLimit` | 该 `Cpu` |
| `held()` | 是否正在执行 `HALT` | `bool` |
| `irq(vector=0xFF)` | 立即发出可屏蔽中断。`vector` 是设备提供的字节，或者是每次读取返回一个字节的可调用对象，设备在模式 0 下正是这样提供更长的指令 | 被接受时为 `True` |
| `nmi()` | 立即响应不可屏蔽中断，并从 `$0066` 重新开始 | `None` |

### 引脚与状态

| 属性 | 含义 |
|:--|:--|
| `irq_line` | 以电平表示的可屏蔽请求，在每条指令的最后一个 T 状态采样 |
| `nmi_line` | 不可屏蔽请求。跳变会触发中断；保持不变不会再次中断 |
| `wait_line` | 在每个机器周期的 T2 之后读取。它每保持置位一个 T 状态，T2 就重复一次 |
| `on_cycle` | 每个 T 状态调用一次，在其结束时：在该状态的总线活动以及下一个状态之前的工作之后 |
| `cycles` | 自芯片构建以来的 T 状态数，跨越复位累计 |
| `steps` | 自上次复位以来的指令数 |
| `halted` | 是否正在执行 `HALT`；每个 `HALT` 周期耗费 4 个 T 状态 |
| `registers` | 下文的 `Registers` 寄存器组 |
| `bus` | 上一条指令：`states`，其 T 状态数；`cycles`，每个机器周期一个 `(state, kind)` 的列表；`log`，每个 T 状态一个 `(address, value, pins)` 的列表。这两个列表仅在 `recording=True` 时填充。`kind` 是 `fetch`、`read`、`write`、`portRead`、`portWrite` 或 `acknowledge` 之一 |
| `memory`、`ports` | 构建芯片时传入的对象 |
| `model` | 规范型号名称 |

```python
from z80 import Cpu, Memory

cpu = Cpu("z80", Memory(image=bytes([0x3E, 0x42])))
cpu.reset()
seen = []


def each_state() -> None:
    seen.append(cpu.bus.states)
    cpu.wait_line = len(seen) < 4


cpu.on_cycle = each_state
cpu.wait_line = True
print(cpu.step(), seen)
```

```
9 [1, 2, 3, 4, 5, 6, 7, 8, 9]
```

`ld a,n` 耗费 7 个 T 状态。在操作码取指的 T2 之后读取等待线时，它仍然置位，一个状态之后再次读取时也仍然置位，因此 T2 重复两次，该指令耗费 9 个。`on_cycle` 看到了其中的每一个。

### 中断

```python
from z80 import Cpu, Memory, RunLimit

program = bytes([0xED, 0x56, 0xFB, 0x00, 0x18, 0xFD])
space = Memory(image=program, fill=0x00)
cpu = Cpu("z80", space)
cpu.reset()
cpu.registers.sp = 0x8000

cpu.run_until(lambda part: part.registers.pc == 0x0004)
cpu.irq_line = True
cpu.step()
cpu.irq_line = False
print(f"pc={cpu.registers.pc:04X} iff1={cpu.registers.iff1} im={cpu.registers.im}")
print(f"pushed {space.read8(0x7FFF):02X}{space.read8(0x7FFE):02X}")

try:
    cpu.run_until(lambda part: False, limit=3)
except RunLimit as error:
    print(error)
```

```
pc=0038 iff1=False im=1
pushed 0003
gave up after 3 instructions at $003B
```

程序是 `im 1`、`ei`、`nop`，然后用 `jr` 跳回 `nop`。请求线置位后，`jr` 执行完毕，芯片在它的最后一个 T 状态采样请求，压入返回地址 `$0003`，并从 `$0038` 重新开始。检查条件永远不成立的 `run_until` 在 `limit` 允许的 3 条指令之后放弃。

### 内存与端口

| 名称 | 含义 |
|:--|:--|
| `SparseMemory(seed=UNSET_SEED)` | 只存储写入内容的 64 KB 空间。未写入的字节读出由 `seed` 和地址推导出的值 |
| `Memory(size=0x10000, image=None, seed=UNSET_SEED, fill=None)` | 平坦的 `bytearray`。没有 `fill` 时，由 `seed` 乱序填充。`image` 从地址 0 开始复制进来 |
| `Ports(seed=UNSET_SEED)` | I/O 空间。读写以 `(address, value, "r" or "w")` 的形式记入 `log`。未写入的端口读出由 `seed` 推导出的值 |
| `UNSET_SEED` | `0x5A5A5A5A`，未给出种子时所有乱序使用的种子 |

每条总线上的地址都是 16 位。端口地址的高字节携带累加器或 `B`，与芯片实际驱动的一致。

```python
from z80 import Cpu, Memory, Ports

program = bytes([0x3E, 0x12, 0xD3, 0x34, 0x01, 0x99, 0x00, 0xED, 0x71])
ports = Ports()
cpu = Cpu("z84c00", Memory(image=program), ports=ports, recording=True)
cpu.reset()

cpu.step()
cpu.step()
print(cpu.bus.states, cpu.bus.cycles)
for address, value, pins in cpu.bus.log:
    print(f"{address:04X} {value} {pins}")

cpu.step()
cpu.step()
print(ports.log)
```

```
11 [(0, 'fetch'), (4, 'read'), (7, 'portWrite')]
0002 None r-m-
0002 None r-m-
0001 211 --m-
0001 None ----
0003 None r-m-
0003 None r-m-
0003 52 ----
1234 18 ----
1234 18 -w-i
1234 18 -w-i
1234 18 ----
[(4660, 18, 'w'), (153, 255, 'w')]
```

`out ($34),a` 由一次操作码取指、一次操作数读取和一次端口写入组成：11 个 T 状态。每行日志依次是总线上的地址、数据线上的值或 `None`，以及按 RD、WR、MREQ、IORQ 顺序排列的四个引脚，`-` 表示无效。取指的最后两个状态携带由 `I` 和 `R` 构成的刷新地址。随后，Z84C00 上的 `out (c),0` 向端口 `$0099` 发送 `$FF`，这就是端口日志的最后一项。

### 寄存器

`cpu.registers` 包含 `a`、`f`、`b`、`c`、`d`、`e`、`h`、`l` 以及寄存器对 `af`、`bc`、`de`、`hl`；`sp` 和 `pc`；`ix` 和 `iy` 及其半部 `ixh`、`ixl`、`iyh`、`iyl`；影子寄存器组 `af_`、`bc_`、`de_`、`hl_`；`i`、`r`、`iff1`、`iff2` 和 `im`；内部寄存器对 `wz` 及其半部 `w` 和 `z`；以及 `q`，即语料库为上一条指令的标志结果记录的锁存器。写入会按寄存器的宽度截断。

`Registers(seed=UNSET_SEED)` 单独构建一个寄存器组。`reset()` 对它执行 RESET 引脚所做的操作，`exchange_set()` 即 `exx`，`exchange_accumulator()` 即 `ex af,af'`。

```python
from z80 import Registers

held = Registers(seed=7)
print(held)
held.reset()
held.hl = 0x1234
held.exchange_set()
print(f"pc={held.pc:04X} hl={held.hl:04X} hl_={held.hl_:04X} im={held.im} iff1={held.iff1}")
```

```
<Registers pc=1FAC af=A54D hl=BB1D>
pc=0000 hl=724C hl_=1234 im=0 iff1=False
```

### 型号与错误

| 名称 | 含义 |
|:--|:--|
| `MODELS` | 三条 `Model` 记录，以规范名称为键 |
| `Model` | `name`、`aliases`、`summary`、`floating_output`、`carry_rule`、`interrupt_clears_parity`、`verified`，以及 `build(memory, **options)` |
| `UnknownModelError` | 型号缺失，或名称不对应任何型号时，由 `Cpu` 抛出。消息中列出这三种型号 |
| `UnknownShape` | `shape` 不是 `manual` 或 `recording` 时，由 `Cpu` 抛出 |
| `UnknownCarryRule` | 进位规则不是 `zilog` 或 `nec` 时，由 `Model` 抛出 |
| `RunLimit` | 经过 `limit` 条指令而检查条件始终不成立时，由 `run_until` 抛出 |
| `Truncated` | 字节在指令中途结束时，由 `decode` 抛出 |
| `ClockClosed` | 时钟关闭后，由 `Clock.tick()` 抛出 |
| `__version__` | 已安装的版本 |

```python
import z80
from z80 import Clock, ClockClosed, Cpu, Model, UnknownCarryRule, UnknownShape

try:
    Cpu("z80", shape="sampled")
except UnknownShape as error:
    print(error)

try:
    Model("z80x", "a part nobody made", 0x00, carry_rule="intel")
except UnknownCarryRule as error:
    print(error)

clock = Clock(Cpu("z80").reset())
clock.run_for(3)
clock.close()
try:
    clock.tick()
except ClockClosed as error:
    print(error, clock.cycles)

print(len(z80.__version__.split(".")))
```

```
sampled is not a pin shape; there are manual, recording
intel is not a carry flag rule; there are zilog, nec
this clock has been closed 3
3
```

### 命令行工具

每个工具都从仓库根目录运行。一致性工具以模块方式运行。

| 命令 | 作用 | 退出码 |
|:--|:--|:--|
| `python3 z80/doctor.py` | 报告本机、各芯片和语料库 | 0 所有检查通过，1 有检查未通过 |
| `python3 -m conformance.fetch [directory] [--latest]` | 将语料库按其固定的提交克隆到 `directory`，使用 `--latest` 时按上游最新提交克隆，默认目录为 `~/.cache/conformance-suites` | 0 已获取，1 上游不可达或某个 git 步骤失败 |
| `python3 -m conformance.singlestep <suite-directory> [--limit N] [--opcode NAME]` | 在每个用例之后比对寄存器和内存 | 0 无失败，1 有失败或未找到用例，2 参数错误 |
| `python3 -m conformance.cycles <suite-directory> [--limit N] [--opcode NAME] [--shape manual\|recording]` | 比对每个 T 状态的地址、数据和引脚。形态默认为 `recording` | 0 无失败，1 有失败或未找到用例，2 参数错误 |
| `python3 -m conformance.regenerate <output-directory> [--full] [--clone DIR]` | 用生成该语料库的生成器重建它。需要 `node` | 0 已写入，生成器失败时为生成器自身的退出码，1 参数错误 |
| `python3 -m conformance.timing` | 运行记录中的每一行逐指令时序，并比对 T 状态数 | 0 每一行都一致，1 有一行不一致 |
| `python3 -m conformance.quotes` | 在存有文档的机器上，在所引用的文档中查找每一句引文 | 0 每句引文都找到，1 有一句未找到 |
| `python3 -m conformance.documents [--check] [--only SUBSTRING]` | 下载有地址的文档，并校验每个摘要。`--check` 只做校验 | 0 每份都校验通过，1 有一份被拒绝或参数错误 |
| `python3 -m conformance.netlist [--half-cycles N]` | 从复位开始运行晶体管网表 `N` 个半周期，默认 130 | 0 每个节点都已稳定，1 有节点未稳定或缺少数据文件 |
| `python3 -m conformance.wz [output]` | 读取网表在 `WZ` 中留下的内容，并写入 `output`，默认为 [`conformance/wz.json`](conformance/wz.json) | 0 已写入，1 缺少网表或探针未校准 |
| `python3 -m conformance.speed [--instructions N] [--repeats N]` | 在 64 KB 镜像上为 `run_for(N)` 计时，默认 200,000 个 T 状态、运行 7 次 | 0 达到或超过每秒 400,000 个 T 状态，1 低于该值，2 参数错误 |
| `python3 -m conformance.links` | 请求本文件中的每个地址 | 0 每个地址仍然存在，1 有地址返回状态 `404` 或 `410` |
| `python3 -m conformance.package <wheel>` | 检查构建好的 wheel 是否包含每个模块且不含测试 | 0 正常，1 有问题或文件不存在，2 未提供参数 |

## 以真实速度运行

`step()` 会报告一条指令的开销，因此宿主可以为每段墙钟时间分配预算，让芯片保持在其晶振频率上。

```python
import time

from z80 import Cpu

HERTZ = 3_546_895
SLICE = 0.02

cpu = Cpu("z80")
cpu.reset()
per_slice = round(HERTZ * SLICE)
owed = 0

for _ in range(5):
    began = time.perf_counter()
    owed += per_slice
    owed -= cpu.run_for(owed)
    time.sleep(max(0.0, SLICE - (time.perf_counter() - began)))
```

一条指令不能拆成两半，所以 `run_for()` 会超出预算，并返回实际耗费。把超出的部分计入下一段，可以防止长时间运行出现漂移。

## 逐个 T 状态驱动

`Clock(cpu)` 可以在任意两个 T 状态之间暂停芯片，电路板正是在这个位置改变一次读取将得到的应答。

```python
from z80 import Clock, Cpu, Memory

space = Memory(image=bytes([0x3E, 0x42, 0x00, 0x00, 0x00, 0x00]))
cpu = Cpu("z80", space, recording=True)
cpu.reset()
cpu.registers.pc = 0x0000

with Clock(cpu) as clock:
    clock.tick()
    space.write8(0x0001, 0x99)
    clock.run_for(6)

print(0x99 in [value for _, value, _ in cpu.bus.log])
```

```
True
```

`$0001` 处的字节在操作码取指的第一个 T 状态之后被改变，紧随取指的操作数读取取到了新值。

| 调用 | 作用 |
|:--|:--|
| `tick()` | 前进一个 T 状态，并返回时钟的计数 |
| `run_for(cycles)` | 调用 `tick()` 共 `cycles` 次，并返回计数 |
| `close()` | 停止芯片，并交还 `on_cycle`。离开 `with` 块时会调用它 |
| `cycles`、`closed` | 节拍计数，以及时钟是否已关闭 |

对时钟进行迭代会不断推进它，直到它被关闭。芯片内部抛出的异常会从 `tick()` 再次抛出，并且时钟会关闭。

节拍要等其 T 状态的工作完成后才停下。推进到某条指令最后一个 T 状态的时钟，无论是否关闭，都让芯片处于与 `step()` 相同的状态。

芯片运行在一个线程上，因为 Python 无法挂起一条指令的调用栈。每个 T 状态都是两个信号量之间的一次交接，因此时钟比 `step()` 慢很多倍。追求速度时用 `step()`，关心 T 状态落在哪里时用 `Clock`。

## 型号

三者的指令集相同。有三处行为不同。

| 构建方式 | 单独的 `OUT (C)` 发送 | `SCF` 和 `CCF` 之后的未公开标志位 | `LD A,I` 或 `LD A,R` 之后的中断会清除奇偶校验位 | 这三列是否经过测量 |
|:--|:--|:--|:--|:--|
| `Cpu("z80")` | `$00` | 累加器和锁存器 | 是，Zilog 有文档说明 | 是，由语料库测量 |
| `Cpu("z84c00")` | `$FF` | 累加器和锁存器 | 否，Zilog 已修复 | 否，依据 Zilog 自己的说法 |
| `Cpu("upd780c")` | `$00` | 仅累加器 | 未说明 | 否，依据独立研究 |

语料库只记录了 NMOS Z80。另外两种与它共有的一切，都通过它来测量。使它们成为不同芯片的那三列没有经过测量，两者的 `Model.verified` 均为 `False`。

每个型号都接受其制造商销售时使用的型号编号。大小写、`-` 和 `_` 会被忽略，因此 `Cpu("Z84C00-10")` 构建的是 `z84c00`。

| 构建方式 | 同样接受的名称 |
|:--|:--|
| `Cpu("z80")` | `z8400`, `nmosz80`, `z0840004psc`, `z0840006psc`, `z0840008psc`, `mostekmk3880`, `mk3880`, `mk3880n`, `sharplh0080`, `lh0080`, `lh0080a`, `u880`, `ud880d`, `kr1858vm1`, `t34vm1`, `mme`, `goldstargms z80`, `thesysz80` |
| `Cpu("upd780c")` | `necupd780c`, `d780c`, `d780c1`, `d780c2`, `upd780`, `upd780c1`, `upd780c2` |
| `Cpu("z84c00")` | `cmosz80`, `z80c`, `z8400c`, `z84c0006`, `z84c0008`, `z84c0010`, `z84c0020`, `toshibatmpz84c00`, `tmpz84c00`, `t84c00`, `kr1858vm3` |

```python
import z80

for name, model in z80.MODELS.items():
    floating = f"${model.floating_output:02X}"
    print(name, floating, model.carry_rule, model.interrupt_clears_parity, model.verified)

print(z80.Cpu("Z84C00-10").model, z80.Cpu("mk3880").model)

for asked in (None, "z180"):
    try:
        z80.Cpu(asked)
    except z80.UnknownModelError as error:
        print(error)
```

```
z80 $00 zilog True True
upd780c $00 nec False False
z84c00 $FF zilog False False
z84c00 z80
no model was named, and this package will not choose one for you. Name one of: upd780c, z80, z84c00
z180 is not a model this family covers; it has upd780c, z80, z84c00
```

本包未实现的型号编号会被拒绝，而不是解析为相近的型号。因此 `Cpu("z180")` 会抛出异常，而不是返回一个缺少调用方所需指令的 Z80。

## 不运行，只读取

`decode(data, offset=0, address=0)` 读取一条指令。`disassemble(data, address=0)` 读取全部指令。两者都不需要芯片。它们都返回带有 `address`、`size`、`raw` 和 `text` 的 `Instruction` 对象。

```python
from z80 import Truncated, decode, disassemble

program = bytes([0x3E, 0x42, 0xDD, 0x7E, 0xFE, 0x10, 0xFA, 0xED, 0x71, 0xC3])

for found in disassemble(program, 0x8000):
    print(f"{found.address:04X}  {found.raw.hex(' '):<9} {found.text}")

one = decode(bytes([0xCD, 0x34, 0x12]), address=0x0100)
print(one, one.size)

try:
    decode(bytes([0xCD, 0x34]))
except Truncated as error:
    print(error)
```

```
8000  3e 42     ld a,$42
8002  dd 7e fe  ld a,(ix-$02)
8005  10 fa     djnz $8001
8007  ed 71     out (c),0
8009  c3        db $C3
<0100 call $1234> 3
instruction at 0 runs past the end of the data
```

相对跳转会打印其目标地址。字节在指令中途结束时，`decode` 抛出 `Truncated`。`disassemble` 则把这种指令的第一个字节写成 `db`，然后继续。

## 没有什么是干净启动的

寄存器和内存上电时持有可复现的乱序模式。原因是，在真实芯片上读取一个从未写入的字节是缺陷，而读出零的内存会把这个缺陷变成一个通过的测试。没有任何参数能清空寄存器。只有调用方用 `fill` 构建内存时，内存才持有单一值。

```python
from z80 import Cpu, SparseMemory

print(hex(SparseMemory().read8(0x1234)))
print(SparseMemory().read8(0x1234) == SparseMemory().read8(0x1234))

powered = Cpu("z80", SparseMemory())
print(hex(powered.registers.pc), powered.cycles)
```

```
0x84
True
0x8926 0
```

该字节由种子和地址推导而来，因此每次运行都相同，并且不为零。程序计数器同样被乱序，`cycles` 为 0，因为还没有任何东西驱动过 RESET。在 `reset()` 之前单步执行芯片，会执行该地址中存放的任何内容。

## 是否正确

每条指令都会对照 SingleStepTests 语料库运行。该语料库给出了每个寄存器和每个内存字节在执行前后的状态：**1,604,000 个用例，0 个失败**。第二个运行器逐个 T 状态比对芯片放到总线上的内容，包括地址、数据和引脚：**22,005,372 个 T 状态，0 个失败**。

```bash
python3 -m conformance.fetch ~/.cache/conformance-suites
python3 -m conformance.singlestep ~/.cache/conformance-suites/z80/v1
python3 -m conformance.cycles ~/.cache/conformance-suites/z80/v1
```

```
1604000 cases, 0 failed, 0 opcodes affected
1604000 cases, 22005372 T states compared, 0 failed, 0 opcodes affected, 0 opening states skipped, shape recording
```

语料库的提交固定在 [`conformance/suites.json`](conformance/suites.json) 中。每周有一个任务对照上游最新提交运行，并开启一个拉取请求或议题。每个运行器都会打印它检查了多少用例，因为什么都没解析的运行与检查了全部内容的运行一样，都会以 0 退出。

手册单独对照。[`conformance/hardware.json`](conformance/hardware.json) 收录了取自文档的每一条事实，并附有原句和页码。[`conformance/hardware.test.py`](conformance/hardware.test.py) 及其旁边的 `hardware_*.test.py` 文件在机器上没有语料库的情况下运行芯片，据此逐个检查其机器周期。`python3 -m conformance.timing` 运行全部 217 行逐指令时序，并将每一行与芯片实际耗费的 T 状态比对。手册有五处自相矛盾：三行时序，分别在第 99、260 和 269 页，其 M 周期数与它们自己的 T 状态分解不符；另外两处是正文与插图不一致。两个来源出现分歧的每一处都记录在 [`conformance/divergences.json`](conformance/divergences.json) 中，并附有能够解决它的依据。

[OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) 列出了 18 个问题，在这些问题上保真度仍是一种声明而不是测量结果，每个问题都附有能关闭它的测量。标志寄存器的第 3 位和第 5 位以及内部的 `WZ` 寄存器，在 Zilog 用户手册和数据手册共 780 页中都没有出现。

### 询问晶片

[`conformance/netlist.py`](conformance/netlist.py) 把芯片作为晶体管网络来运行，所用网表提取自晶片照片。从复位开始驱动时，它从 `$0000` 取指，并执行一个示例程序。

```bash
python3 -m conformance.netlist
```

解析器参照了 Visual 6502 项目中的 `chipsim.js` 和 `wires.js`，二者采用 MIT 许可证。它们的许可声明见 [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md)。三个数据文件不在本仓库中。[`conformance/netlist.manifest.json`](conformance/netlist.manifest.json) 列出了它们的名称和来源，并记录了各自的摘要。把它们放到 `docs/independent/visual6502` 中，加载时会拒绝摘要不符的任何文件。

晶体管文件把 32 个条目标记为上拉，只有把它们作为上拉加载时，网络才会稳定。字母重复的网络名称保存指令写入的寄存器组，单字母的网络名称保存影子寄存器组。对每个寄存器和每个位位置执行 `LD r,n` 可以证明这一点。

包中没有任何内容以网表为准。它的可信度低于制造商的文档，也低于真实芯片的录制数据，因为网表是一种提取结果，而提取可能出错。

## 参与开发

| 需求 | 位置 |
|:--|:--|
| 每个门禁检查及其运行顺序 | [CONTRIBUTING.md](CONTRIBUTING.md) |
| 面向编程智能体的相同内容 | [AGENTS.md](AGENTS.md) |
| 本仓库与本系列其他仓库共享的标准 | [FAMILY.md](FAMILY.md) |
| 缺陷报告 | [GitHub Issues](https://github.com/gufranco/zilog-z80-python/issues) |
| 安全报告 | [SECURITY.md](SECURITY.md) |

```bash
uvx ruff@0.16.3 format --check .
uvx ruff@0.16.3 check .
uvx --python 3.12 mypy==1.14.1
python3 -m coverage erase
for file in $(find z80 conformance -name '*.test.py' | sort); do
  python3 -m coverage run -a "$file"
done
python3 -m coverage report
python3 -m conformance.speed
```

每个模块旁边都有一个名为 `<module>.test.py` 的测试文件，每个都可以单独运行。覆盖率是一道硬性门禁检查，要求语句和分支覆盖率均为 100%。类型检查使用严格模式的 `mypy`。速度检查在低于每秒 400,000 个 T 状态时失败，并且在覆盖率步骤之外运行。提交遵循 [Conventional Commits](https://www.conventionalcommits.org/)。

## 参考资料

本仓库不包含任何文档。每一行给出页数以及文件 SHA-256 的前十六个字符，以便读者获取同一文件并核对同一页。用 `shasum -a 256 <file>` 计算完整摘要。

下列所有制造商文档均受版权保护，不可再分发。个别句子连同其出处页码引用在 [`conformance/hardware.json`](conformance/hardware.json) 中。

| 文档 | 日期 | 页数 | SHA-256 | 可再分发 |
|:---------|:-----|------:|:--------|:----------------|
| [Zilog，*Z80 CPU User Manual*，UM008011-0816](https://www.zilog.com/docs/z80/um0080.pdf) | 2016-08 | 332 | `e3c83da5a5d8e372…` | 否 |
| Zilog，*Z80 Family Data Book*，00-2490-01 | 1989-01 | 448 | `844681b63ffc45bd…` | 否 |
| Zilog，*Z84C00 Product Specification*，PS017801-0602 | 无日期 | 36 | `06198d3c22a79a3f…` | 否 |
| NEC，*µPD780C* 数据表 | 无日期 | 24 | `2036fa845533feee…` | 否 |

只有当两条从未互相参考的研究脉络结论一致时，才采用独立研究，并且从不将其作为制造商已给出数值的引用来源。

| 文档 | 作者 | 页数 | SHA-256 | 许可证 |
|:---------|:-------|------:|:--------|:--------|
| [*The Undocumented Z80 Documented*，v0.91](https://archive.org/details/the-undocumented-z80-documented) | Sean Young，2005-09-18 | 52 | `6413048f39c2e735…` | GFDL 1.1 或更高版本 |
| [*Z80 CCF SCF Outcome Stability*](https://github.com/redcode/Z80/wiki/Z80-CCF-SCF-Outcome-Stability) | Sainz de Baranda y Goñi、Brewer、Helcmanovsky | 4 | `be87311012f9edaf…` | GFDL 1.3 |
| *Undocumented Z80 Flags*，rev 1.0 | David Banks，2018-08-21 | 3 | `33766df5494e2fdf…` | 未说明 |
| *MEMPTR, esoteric register of the ZiLOG Z80 CPU* | Boo-boo，Vladimir Kladov 译 | 文本 | `f9e8e87cdd205e15…` | 未说明 |
| [redcode/Z80 wiki: Interrupts](https://github.com/redcode/Z80/wiki/Interrupts) 和 [MEMPTR](https://github.com/redcode/Z80/wiki/MEMPTR) | Sainz de Baranda y Goñi 及其他贡献者 | 网页 | n/a | GFDL 1.3 |

| 来源 | 用途 |
|:-------|:---------|
| [SingleStepTests/z80](https://github.com/SingleStepTests/z80.git) | 固定的语料库，1,604,000 个用例。提交记录在 [`conformance/suites.json`](conformance/suites.json) 中 |
| [raddad772/jsmoo](https://github.com/raddad772/jsmoo.git) | 生成该语料库的生成器，因此语料库可以重建，而不只是下载 |
| [gdevic/Z80Explorer](https://github.com/gdevic/Z80Explorer) | 其行为记录在 [`conformance/divergences.json`](conformance/divergences.json) 中的网表 |

[`conformance/documents.json`](conformance/documents.json) 记录了每份文档的完整摘要和字节数。[`conformance/documents.py`](conformance/documents.py) 把文档下载到 git 忽略的 `docs/` 中，并拒绝摘要不符的任何文件。

```bash
python3 -m conformance.documents
python3 -m conformance.documents --check
```

八份文档中有两份带有地址，会被下载。另外六份是从网页打印的，因此该命令只校验你提供的副本，从不替换它。

上表中的 MEMPTR 论文以文本形式固定。`docs/` 中的副本是同一篇文章的打印版，因此两个摘要不同。用其中一个的摘要去检查另一个，会报告一个毫无意义的不匹配。

## 引用本项目

[CITATION.cff](CITATION.cff) 在每次发布时，由写入包版本号的脚本更新。GitHub 会将其渲染为 Cite this repository 按钮。

## 许可证

MIT。见 [LICENSE](LICENSE)。
