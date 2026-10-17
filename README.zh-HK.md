# Zilog Z80

以 Python 實現的 Zilog Z80、NEC µPD780C 和 Zilog Z84C00，可按一條指令或一個 T 狀態驅動。每個機器週期的形態以 Zilog 的用戶手冊為準，每個操作碼的每個 T 狀態以逐操作碼的測試語料庫為準。

[English](README.md) | [日本語](README.ja.md) | [简体中文](README.zh-Hans.md) | 繁體中文（香港）

[![CI](https://github.com/gufranco/zilog-z80-python/actions/workflows/ci.yml/badge.svg)](https://github.com/gufranco/zilog-z80-python/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/gufranco/zilog-z80-python)](https://github.com/gufranco/zilog-z80-python/releases)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

**3** 款晶片，比對了 **1,604,000** 個一致性案例和 **22,005,372** 個 T 狀態，**0** 個失敗，**1,422** 個測試，**100%** 語句及分支覆蓋率，沒有任何依賴項

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

程式是 `ld a,$42`、`ld b,a`、`halt`。每次 `step()` 執行一條指令，並傳回其耗費的 T 狀態數：7、4 和 4。`HALT` 執行後，`held()` 為真。`cycles` 讀數為 20，因為 `reset()` 在第一條指令之前耗費 5 個 T 狀態。

## 安裝

| 需求 | 版本 |
|:--|:--|
| Python | 3.12 或更新 |
| git | 任何版本，用於複製儲存庫 |

```bash
git clone https://github.com/gufranco/zilog-z80-python.git
cd zilog-z80-python
python3 z80/doctor.py
```

套件只匯入標準庫的內容。`pip install git+https://github.com/gufranco/zilog-z80-python.git` 只安裝 `z80` 套件，不包括一致性工具。

診斷腳本會報告本機、它建立並重設的三款晶片，以及語料庫是否已取得且完整。它以檔案形式執行，因此即使套件無法匯入，它仍能報告。所有檢查通過時以 0 結束，否則以 1 結束。提交錯誤報告時，請貼上它的全部輸出。在全新的檢出上，它的結尾是：

```
  8 checks, nothing to report
```

版本發佈遵循[語義化版本](https://semver.org/)，由 semantic-release 從提交歷史產生。每個版本都有標籤，並列於[版本發佈頁面](https://github.com/gufranco/zilog-z80-python/releases)。

## 介面

以下所有內容均從 `z80` 匯出。其他內容均非公開。

### 建立晶片

`Cpu(model, memory=None, fill=None, ports=None, seed=UNSET_SEED, recording=False, shape="manual")` 建立一款晶片，已通電但未重設。

| 參數 | 含義 |
|:--|:--|
| `model` | 必需。型號名稱或別名，忽略大小寫和分隔符。省略時會引發 `UnknownModelError`，其訊息列出所有型號 |
| `memory` | 任何具有 `read8(address)` 和 `write8(address, value)` 的物件。晶片保留傳入的那一個。省略時，晶片會建立一個 `SparseMemory` |
| `fill` | 只在省略 `memory` 時使用：建立一個 64 KB 的 `Memory`，每個位置都存放該位元組 |
| `ports` | 任何具有 `read(address)` 和 `write(address, value)` 的物件。省略時，輸入讀到型號的浮空輸出值，輸出則無去處 |
| `seed` | 為通電時暫存器的擾亂值提供種子 |
| `recording` | `True` 時在 `cpu.bus.log` 保留逐 T 狀態的記錄 |
| `shape` | `"manual"` 或 `"recording"`，即讀取各控制引腳的時鐘邊沿。其他值會引發 `UnknownShape` |

### 執行

| 呼叫 | 作用 | 傳回 |
|:--|:--|:--|
| `reset()` | 驅動 RESET：Zilog 指明引腳最少須保持的 3 個 T 狀態，然後是晶片在釋放後耗費的 2 個。將 `pc`、`i`、`r` 和 `im` 設為 0，清除兩個中斷觸發器及 `steps`，其他暫存器保持原狀 | 該 `Cpu` |
| `step()` | 執行一條指令，停機時則執行一個 `HALT` 週期 | 耗費的 T 狀態數 |
| `run_for(cycles)` | 執行完整的指令，直至至少經過 `cycles` 個 T 狀態 | 耗費的 T 狀態數，可能超過 `cycles` |
| `run_until(check, limit=None)` | 在 `check(cpu)` 為假時逐步執行。執行 `limit` 條指令後會引發 `RunLimit` | 該 `Cpu` |
| `held()` | 是否正在執行 `HALT` | `bool` |
| `irq(vector=0xFF)` | 立即發出可屏蔽中斷。`vector` 是裝置提供的位元組，或每次讀取傳回一個位元組的可呼叫物件，裝置在模式 0 下就是這樣提供較長的指令 | 被接受時為 `True` |
| `nmi()` | 立即接受不可屏蔽中斷，並從 `$0066` 重新開始 | `None` |

### 引腳與狀態

| 屬性 | 說明 |
|:--|:--|
| `irq_line` | 可屏蔽請求，為電平信號，在每條指令的最後一個 T 狀態取樣 |
| `nmi_line` | 不可屏蔽請求。觸發中斷的是轉變；保持不會再次中斷 |
| `wait_line` | 在每個機器週期的 T2 之後讀取。每個保持設定的 T 狀態都會重複 T2 |
| `on_cycle` | 每個 T 狀態呼叫一次，在該狀態的匯流排活動之後 |
| `cycles` | 自晶片建立以來的 T 狀態數，跨越重設 |
| `steps` | 自上次重設以來的指令數 |
| `halted` | 是否正在執行 `HALT`；每個 `HALT` 週期耗費 4 個 T 狀態 |
| `registers` | 下文的 `Registers` 暫存器組 |
| `bus` | 最後一條指令：`states`，其 T 狀態數；`cycles`，每個機器週期一個 `(state, kind)` 的列表；`log`，每個 T 狀態一個 `(address, value, pins)` 的列表。這兩個列表只在 `recording=True` 時填入 |
| `memory`、`ports` | 建立晶片時使用的物件 |
| `model` | 正式型號名稱 |

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

`ld a,n` 耗費 7 個 T 狀態。在操作碼擷取的 T2 之後讀取時，等待線仍然設定，一個狀態之後再讀取時也是如此，因此 T2 重複兩次，指令耗費 9 個 T 狀態。`on_cycle` 看到了每一個狀態。

### 中斷

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

程式是 `im 1`、`ei`、`nop`，然後以 `jr` 跳回 `nop`。中斷線設定後，`jr` 完成，晶片在其最後一個 T 狀態取樣請求，推入返回地址 `$0003`，並從 `$0038` 重新開始。以一個永不通過的檢查呼叫 `run_until`，會在 `limit` 允許的 3 條指令後放棄。

### 記憶體與連接埠

| 名稱 | 說明 |
|:--|:--|
| `SparseMemory(seed=UNSET_SEED)` | 64 KB，只儲存寫入的內容。未寫入的位元組讀出的值由 `seed` 和地址推導 |
| `Memory(size=0x10000, image=None, seed=UNSET_SEED, fill=None)` | 一個平面的 `bytearray`。沒有 `fill` 時，以 `seed` 擾亂。`image` 從地址 0 開始複製進去 |
| `Ports(seed=UNSET_SEED)` | 一個 I/O 空間。讀寫以 `(address, value, "r" or "w")` 記入 `log`。未寫入的連接埠讀出的值由 `seed` 推導 |
| `UNSET_SEED` | `0x5A5A5A5A`，未提供種子時所有擾亂使用的種子 |

每條匯流排的地址都是 16 位元。連接埠地址的高位元組是累加器或 `B`，與晶片的驅動方式一致。

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

`out ($34),a` 由一次操作碼擷取、一次運算元讀取和一次連接埠寫入組成：11 個 T 狀態。每行記錄依次是匯流排上的地址、數據線上的值或 `None`，以及按 RD、WR、MREQ、IORQ 次序排列的四個引腳，`-` 表示非作用中。擷取的最後兩個狀態帶有由 `I` 和 `R` 組成的刷新地址。之後 Z84C00 上的 `out (c),0` 將 `$FF` 送往連接埠 `$0099`，這是連接埠記錄的最後一項。

### 暫存器

`cpu.registers` 包含 `a`、`f`、`b`、`c`、`d`、`e`、`h`、`l` 及暫存器對 `af`、`bc`、`de`、`hl`；`sp` 和 `pc`；`ix` 和 `iy` 及其半部 `ixh`、`ixl`、`iyh`、`iyl`；影子暫存器組 `af_`、`bc_`、`de_`、`hl_`；`i`、`r`、`iff1`、`iff2` 和 `im`；內部暫存器對 `wz` 及其半部 `w` 和 `z`；以及 `q`，即語料庫為上一條指令的旗標結果記錄的鎖存器。寫入會按暫存器的寬度遮罩。

`Registers(seed=UNSET_SEED)` 單獨建立一個暫存器組。`reset()` 對它做 RESET 引腳所做的事，`exchange_set()` 即 `exx`，`exchange_accumulator()` 即 `ex af,af'`。

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

### 型號與錯誤

| 名稱 | 說明 |
|:--|:--|
| `MODELS` | 三個 `Model` 記錄，以正式名稱為鍵 |
| `Model` | `name`、`aliases`、`summary`、`floating_output`、`carry_rule`、`interrupt_clears_parity`、`verified`，以及 `build(memory, **options)` |
| `UnknownModelError` | 缺少型號，或名稱不屬於任何型號時，由 `Cpu` 引發。訊息列出三個型號 |
| `UnknownShape` | `shape` 不是 `manual` 或 `recording` 時，由 `Cpu` 引發 |
| `UnknownCarryRule` | 進位規則不是 `zilog` 或 `nec` 時，由 `Model` 引發 |
| `RunLimit` | 經過 `limit` 條指令而檢查始終不成立時，由 `run_until` 引發 |
| `Truncated` | 位元組在指令中途結束時，由 `decode` 引發 |
| `ClockClosed` | 時鐘關閉後呼叫 `Clock.tick()` 時引發 |
| `__version__` | 已安裝的版本 |

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

### 命令列工具

每個工具都從儲存庫根目錄執行。一致性工具以模組形式執行。

| 命令 | 作用 | 結束碼 |
|:--|:--|:--|
| `python3 z80/doctor.py` | 報告本機、各晶片及語料庫 | 0 所有檢查通過，1 有檢查未通過 |
| `python3 -m conformance.fetch [directory] [--latest]` | 將語料庫按固定的提交，或以 `--latest` 按上游的最新提交，複製到 `directory`，預設為 `~/.cache/conformance-suites` | 0 已取得，1 無法連接上游或某個 git 步驟失敗 |
| `python3 -m conformance.singlestep <suite-directory> [--limit N] [--opcode NAME]` | 在每個案例之後比對暫存器和記憶體 | 0 沒有失敗，1 有失敗或找不到案例，2 參數錯誤 |
| `python3 -m conformance.cycles <suite-directory> [--limit N] [--opcode NAME] [--shape manual\|recording]` | 比對每個 T 狀態的地址、數據和引腳。形態預設為 `recording` | 0 沒有失敗，1 有失敗或找不到案例，2 參數錯誤 |
| `python3 -m conformance.regenerate <output-directory> [--full] [--clone DIR]` | 以產生語料庫的產生器重建語料庫。需要 `node` | 0 已寫入，失敗時為產生器自身的結束碼，1 參數錯誤 |
| `python3 -m conformance.timing` | 執行記錄中每一行逐指令時序，並比對 T 狀態 | 0 每行一致，1 有一行不一致 |
| `python3 -m conformance.quotes` | 在存有文件的機器上，於所引用的文件中找出每一句引文 | 0 找到所有引文，1 有一句找不到 |
| `python3 -m conformance.documents [--check] [--only SUBSTRING]` | 下載有地址的文件，並核實每個摘要值。`--check` 只核實 | 0 全部核實，1 有一個被拒絕或參數錯誤 |
| `python3 -m conformance.netlist [--half-cycles N]` | 從重設開始執行電晶體網表 `N` 個半週期，預設為 130 | 0 每個節點都已穩定，1 有節點未穩定或缺少數據檔案 |
| `python3 -m conformance.wz [output]` | 讀取網表留在 `WZ` 中的內容，並寫入 `output`，預設為 [`conformance/wz.json`](conformance/wz.json) | 0 已寫入，1 缺少網表或探針未校準 |
| `python3 -m conformance.speed [--instructions N] [--repeats N]` | 在 64 KB 映像檔上為 `run_for(N)` 計時，預設為 200,000 個 T 狀態，執行 7 次 | 0 達到或高於每秒 400,000 個 T 狀態，1 低於此值，2 參數錯誤 |
| `python3 -m conformance.links` | 請求本檔案中的每個地址 | 0 每個地址仍然存在，1 有地址傳回狀態 `404` 或 `410` |
| `python3 -m conformance.package <wheel>` | 檢查已建置的 wheel 包含每個模組且不含任何測試 | 0 無問題，1 有問題或檔案不存在，2 沒有參數 |

## 以真實速度執行

`step()` 報告一條指令的耗費，因此宿主可以為每段實際時間分配預算，使晶片保持其晶振的速度。

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

指令無法從中間切開，因此 `run_for()` 會超出預算，並傳回實際的耗費。將超出部分帶到下一段時間，可防止長時間執行時出現漂移。

## 逐個 T 狀態驅動

`Clock(cpu)` 可在任意兩個 T 狀態之間停住晶片，電路板正是在這裏改變一次讀取將得到的值。

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

`$0001` 的位元組在操作碼擷取的第一個 T 狀態之後改變，擷取之後的運算元讀取取得了新值。

| 呼叫 | 作用 |
|:--|:--|
| `tick()` | 前進一個 T 狀態，並傳回時鐘的計數 |
| `run_for(cycles)` | 呼叫 `tick()` `cycles` 次，並傳回計數 |
| `close()` | 停止晶片，並交還 `on_cycle`。離開 `with` 區塊時會呼叫它 |
| `cycles`、`closed` | 節拍計數，以及時鐘是否已關閉 |

迭代時鐘會令它一直前進，直至關閉。晶片內部引發的異常會從 `tick()` 再次引發，時鐘隨之關閉。

晶片在一個執行緒上執行，因為 Python 無法暫停一條指令的呼叫堆疊。每個 T 狀態都是兩個訊號量之間的一次交接，因此時鐘比 `step()` 慢很多倍。追求速度時用 `step()`，需要知道 T 狀態落在何處時用 `Clock`。

## 型號

三款晶片的指令集相同。有三項行為不同。

| 建立方式 | 單獨的 `OUT (C)` 送出 | `SCF` 和 `CCF` 之後的未記載旗標位元 | `LD A,I` 或 `LD A,R` 之後的中斷清除奇偶位 | 這三欄是否經過測量 |
|:--|:--|:--|:--|:--|
| `Cpu("z80")` | `$00` | 累加器和鎖存器 | 是，且 Zilog 有記載 | 是，由語料庫測量 |
| `Cpu("z84c00")` | `$FF` | 累加器和鎖存器 | 否，Zilog 已修正 | 否，依據 Zilog 自己的一句說明 |
| `Cpu("upd780c")` | `$00` | 只有累加器 | 未說明 | 否，依據獨立研究 |

語料庫只記錄 NMOS Z80。另外兩款與它共有的一切都經它測量。令它們成為不同晶片的三欄則未經測量，兩者的 `Model.verified` 均為 `False`。

每個型號都接受其製造商銷售時使用的零件編號。大小寫、`-` 和 `_` 均被忽略，因此 `Cpu("Z84C00-10")` 會建立一個 `z84c00`。

| 建立方式 | 也接受 |
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

本套件未實現的零件編號會被拒絕，而不會解析為相近的型號，因此 `Cpu("z180")` 會引發錯誤，而不是傳回一個缺少呼叫者所要指令的 Z80。

## 不執行而讀取

`decode(data, offset=0, address=0)` 讀取一條指令。`disassemble(data, address=0)` 讀取全部指令。兩者都不需要晶片。各自傳回帶有 `address`、`size`、`raw` 和 `text` 的 `Instruction` 物件。

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

相對跳轉會印出其目標。位元組在指令中途結束時，`decode` 會引發 `Truncated`。`disassemble` 則將這種指令的第一個位元組寫成 `db`，然後繼續。

## 沒有任何東西以乾淨狀態開始

暫存器和記憶體通電時存有可重現的擾亂模式，因為讀取未曾寫入的位元組在真實晶片上是缺陷，而回答零的記憶體會把這種缺陷變成通過的測試。沒有任何參數可以清除暫存器。只有呼叫者以 `fill` 建立記憶體時，記憶體才存放單一的值。

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

位元組由種子和地址推導，因此每次執行都相同，而且不是零。程式計數器也經過擾亂，而 `cycles` 為 0，因為尚未驅動 RESET。在 `reset()` 之前逐步執行晶片，會執行該地址上的任何內容。

## 它是否正確

每條指令都以 SingleStepTests 語料庫執行，該語料庫列明每個暫存器和每個記憶體位元組在執行前後的值：**1,604,000 個案例，0 個失敗**。第二個執行器逐個 T 狀態比對晶片放到匯流排上的地址、數據和引腳：**22,005,372 個 T 狀態，0 個失敗**。

```bash
python3 -m conformance.fetch ~/.cache/conformance-suites
python3 -m conformance.singlestep ~/.cache/conformance-suites/z80/v1
python3 -m conformance.cycles ~/.cache/conformance-suites/z80/v1
```

```
1604000 cases, 0 failed, 0 opcodes affected
1604000 cases, 22005372 T states compared, 0 failed, 0 opcodes affected, 0 opening states skipped, shape recording
```

語料庫的提交固定在 [`conformance/suites.json`](conformance/suites.json)，每週有一個作業以上游的最新提交執行，並開啟拉取請求或問題。每個執行器都會印出它檢查了多少個案例，因為什麼都沒解析的執行，與檢查了全部內容的執行一樣以 0 結束。

手冊單獨處理。[`conformance/hardware.json`](conformance/hardware.json) 載有取自文件的每項事實，連同其原句和頁碼，[`conformance/hardware.test.py`](conformance/hardware.test.py) 在機器上沒有語料庫的情況下，以它檢查型號的常數和機器週期。`python3 -m conformance.timing` 執行全部 217 行逐指令時序，並將每行與晶片耗費的 T 狀態比對。手冊有五處自相矛盾：三行時序，分別在第 99、260 和 269 頁，其 M 週期數與其自身的 T 狀態分解不符；另外兩處是正文與圖表不符。兩個來源出現分歧的每一處，都連同可解決它的方法列於 [`conformance/divergences.json`](conformance/divergences.json)。

[OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) 列出 18 個問題，其中的保真度是一項聲稱而非測量，每個問題都附有可解決它的測量。旗標暫存器的第 3 和第 5 位元以及內部的 `WZ` 暫存器，在 Zilog 用戶手冊和數據手冊合共 780 頁中都沒有出現。

### 向晶粒求證

[`conformance/netlist.py`](conformance/netlist.py) 將晶片作為電晶體網絡執行，所用網表從晶粒照片提取。從重設開始驅動，它從 `$0000` 擷取並執行一個範例程式。

```bash
python3 -m conformance.netlist
```

解析器依照 Visual 6502 項目的 `chipsim.js` 和 `wires.js`，兩者以 MIT 授權。其授權聲明載於 [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md)。三個數據檔案不在本儲存庫中。[`conformance/netlist.manifest.json`](conformance/netlist.manifest.json) 列出它們的名稱、來源，並記錄每個摘要值。將它們放在 `docs/independent/visual6502`，載入時會拒絕任何摘要值不符的檔案。

電晶體檔案將 32 個項目標記為上拉，只有將它們作為上拉載入時，網絡才會穩定。名稱重複字母的網絡存放指令寫入的暫存器組，單字母名稱的網絡則存放影子暫存器組，對每個暫存器和每個位元位置執行 `LD r,n` 即可看出這一點。

套件中沒有任何部分以網表為準。它的地位低於製造商的文件，也低於從真實晶片取得的記錄，因為網表是提取的結果，而提取可能出錯。

## 參與開發

| 需要 | 位置 |
|:--|:--|
| 每項關卡檢查及其執行次序 | [CONTRIBUTING.md](CONTRIBUTING.md) |
| 供編程代理使用的同一份資料 | [AGENTS.md](AGENTS.md) |
| 本儲存庫與同系列其他儲存庫共用的標準 | [FAMILY.md](FAMILY.md) |
| 錯誤報告 | [GitHub Issues](https://github.com/gufranco/zilog-z80-python/issues) |
| 安全報告 | [SECURITY.md](SECURITY.md) |

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

每個模組旁邊都有一個測試檔案，名為 `<module>.test.py`，每個都可單獨執行。覆蓋率是硬性關卡檢查，要求 100% 語句及分支覆蓋。類型檢查是嚴格模式的 `mypy`。速度檢查在低於每秒 400,000 個 T 狀態時失敗，並在覆蓋率步驟之外執行。提交遵循 [Conventional Commits](https://www.conventionalcommits.org/)。

## 參考資料

本儲存庫不附帶任何文件。每行列出頁數及檔案 SHA-256 的前十六個字元，讓讀者可以取得同一檔案並核對同一頁。以 `shasum -a 256 <file>` 計算完整摘要值。

下列每份製造商文件均受版權保護，不可再分發。個別句子連同出處頁碼引用於 [`conformance/hardware.json`](conformance/hardware.json)。

| 文件 | 日期 | 頁數 | SHA-256 | 可再分發 |
|:---------|:-----|------:|:--------|:----------------|
| [Zilog, *Z80 CPU User Manual*, UM008011-0816](https://www.zilog.com/docs/z80/um0080.pdf) | 2016-08 | 332 | `e3c83da5a5d8e372…` | 否 |
| Zilog, *Z80 Family Data Book*, 00-2490-01 | 1989-01 | 448 | `844681b63ffc45bd…` | 否 |
| Zilog, *Z84C00 Product Specification*, PS017801-0602 | 未註明日期 | 36 | `06198d3c22a79a3f…` | 否 |
| NEC, *µPD780C* data sheet | 未註明日期 | 24 | `2036fa845533feee…` | 否 |

獨立研究只在兩個從未互相參考的來源一致時才會使用，而且從不用作製造商已給出數字的引證。

| 文件 | 作者 | 頁數 | SHA-256 | 授權 |
|:---------|:-------|------:|:--------|:--------|
| [*The Undocumented Z80 Documented*, v0.91](https://archive.org/details/the-undocumented-z80-documented) | Sean Young, 2005-09-18 | 52 | `6413048f39c2e735…` | GFDL 1.1 或更新版本 |
| [*Z80 CCF SCF Outcome Stability*](https://github.com/redcode/Z80/wiki/Z80-CCF-SCF-Outcome-Stability) | Sainz de Baranda y Goñi, Brewer, Helcmanovsky | 4 | `be87311012f9edaf…` | GFDL 1.3 |
| *Undocumented Z80 Flags*, rev 1.0 | David Banks, 2018-08-21 | 3 | `33766df5494e2fdf…` | 未註明 |
| *MEMPTR, esoteric register of the ZiLOG Z80 CPU* | Boo-boo，Vladimir Kladov 譯 | 文字 | `f9e8e87cdd205e15…` | 未註明 |
| [redcode/Z80 wiki: Interrupts](https://github.com/redcode/Z80/wiki/Interrupts) 及 [MEMPTR](https://github.com/redcode/Z80/wiki/MEMPTR) | Sainz de Baranda y Goñi 及其他貢獻者 | 網頁 | 不適用 | GFDL 1.3 |

| 來源 | 用途 |
|:-------|:---------|
| [SingleStepTests/z80](https://github.com/SingleStepTests/z80.git) | 固定的語料庫，1,604,000 個案例。提交記錄在 [`conformance/suites.json`](conformance/suites.json) |
| [raddad772/jsmoo](https://github.com/raddad772/jsmoo.git) | 產生該語料庫的產生器，使語料庫可以重建，而不只是下載 |
| [gdevic/Z80Explorer](https://github.com/gdevic/Z80Explorer) | 其行為記錄於 [`conformance/divergences.json`](conformance/divergences.json) 的網表 |

[`conformance/documents.json`](conformance/documents.json) 載有每份文件的完整摘要值和位元組數。[`conformance/documents.py`](conformance/documents.py) 下載到 git 忽略的 `docs/`，並拒絕任何摘要值不符的檔案。

```bash
python3 -m conformance.documents
python3 -m conformance.documents --check
```

八份文件中有兩份帶有地址，會被下載。其餘六份是從網頁列印出來的，因此該命令會核實你提供的副本，且從不取代它。

上文的 MEMPTR 論文以文字形式固定。`docs/` 中的副本是同一篇文章的列印本，因此兩個摘要值不同，以其中一個的摘要值核對另一個會報告不符，而這個不符沒有任何意義。

## 引用本項目

[CITATION.cff](CITATION.cff) 在每次發佈時由標記套件版本的腳本更新。GitHub 會將它顯示為 Cite this repository 按鈕。

## 授權

MIT。見 [LICENSE](LICENSE)。
