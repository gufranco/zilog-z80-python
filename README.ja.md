# Zilog Z80

Zilog Z80、NEC µPD780C、Zilog Z84C00をPythonで実装したものです。1命令単位、または1Tステート単位で駆動できます。すべてのマシンサイクルの形はZilogのユーザーマニュアルに、すべてのオペコードのすべてのTステートはオペコードごとのコーパスに照らして検証しています。

[English](README.md) | 日本語 | [简体中文](README.zh-Hans.md) | [繁體中文（香港）](README.zh-HK.md)

[![CI](https://github.com/gufranco/zilog-z80-python/actions/workflows/ci.yml/badge.svg)](https://github.com/gufranco/zilog-z80-python/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/gufranco/zilog-z80-python)](https://github.com/gufranco/zilog-z80-python/releases)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

**3**種類のパーツ、**1,604,000**件の適合性ケースと**22,005,372**Tステートを比較して失敗は**0**件、テスト**1,439**件、ステートメントとブランチのカバレッジ**100%**、依存関係なし

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

プログラムは`ld a,$42`、`ld b,a`、`halt`です。`step()`は1命令を実行し、かかったTステート数を返します。ここでは7、4、4です。`held()`は`HALT`が実行されるとtrueになります。`reset()`が最初の命令の前に5Tステートを消費するため、`cycles`は20になります。

## インストール

| 要件 | バージョン |
|:--|:--|
| Python | 3.12以降 |
| git | 任意、クローン用 |

```bash
git clone https://github.com/gufranco/zilog-z80-python.git
cd zilog-z80-python
python3 z80/doctor.py
```

パッケージは標準ライブラリ以外を何もインポートしません。`pip install git+https://github.com/gufranco/zilog-z80-python.git`は`z80`パッケージだけをインストールし、適合性ツールは含みません。

ドクターは、マシン、構築してリセットする3種類のパーツのそれぞれ、そしてコーパスが取得済みで完全かどうかを報告します。パッケージがインポートできない場合でも報告できるよう、ファイルとして実行します。すべてのチェックに合格すれば0、そうでなければ1で終了します。バグ報告には出力全体を貼り付けてください。クローン直後の状態では、次の行で終わります。

```
  8 checks, nothing to report
```

リリースは[Semantic Versioning](https://semver.org/)に従い、semantic-releaseがコミット履歴から作成します。すべてのリリースにはタグが付き、[リリースページ](https://github.com/gufranco/zilog-z80-python/releases)に掲載されます。

## インターフェース

以下はすべて`z80`からエクスポートされています。それ以外は公開されていません。

### パーツの構築

`Cpu(model, memory=None, fill=None, ports=None, seed=UNSET_SEED, recording=False, shape="manual")`はパーツを1つ構築します。電源は入っていますが、リセットはされていません。

| 引数 | 意味 |
|:--|:--|
| `model` | 必須です。モデル名または別名で、大文字小文字と区切り文字は無視されます。省略すると`UnknownModelError`が送出され、すべてのモデルが列挙されます |
| `memory` | `read8(address)`と`write8(address, value)`を持つ任意のオブジェクトです。パーツは渡されたものをそのまま保持します。省略すると、パーツは`SparseMemory`を構築します |
| `fill` | `memory`を省略したときだけ使われます。全体がそのバイトで埋まった64 KBの`Memory`を構築します |
| `ports` | `read(address)`と`write(address, value)`を持つ任意のオブジェクトです。省略すると、入力はモデルのフローティング出力を読み、出力はどこにも届きません |
| `seed` | 電源投入時のレジスタのスクランブルのシードです |
| `recording` | `True`にすると、Tステートごとのログを`cpu.bus.log`に保持します |
| `shape` | `"manual"`または`"recording"`で、各制御ピンを読むエッジです。それ以外を指定すると`UnknownShape`が送出されます |

### 実行

| 呼び出し | 動作 | 戻り値 |
|:--|:--|:--|
| `reset()` | RESETを駆動します。Zilogがピンを保持する最小時間として示す3Tステートと、解除後にパーツが費やす2Tステートです。`pc`、`i`、`r`、`im`を0にし、両方の割り込みフリップフロップと`steps`をクリアし、その他のレジスタはそのまま残します | `Cpu` |
| `step()` | 1命令を実行します。ホルト中は`HALT`サイクルを1つ実行します | かかったTステート数 |
| `run_for(cycles)` | 少なくとも`cycles`Tステートが経過するまで、命令単位で実行します | 費やしたTステート数。`cycles`を超えることがあります |
| `run_until(check, limit=None)` | `check(cpu)`がfalseの間ステップ実行します。`limit`命令を実行すると`RunLimit`を送出します | `Cpu` |
| `held()` | `HALT`を実行中かどうか | `bool` |
| `irq(vector=0xFF)` | その時点でマスク可能割り込みを要求します。`vector`はデバイスが供給するバイト、または読み出しごとに1バイトを返すcallableです。後者は、デバイスがモード0でより長い命令を供給する方法です | 受け付けられれば`True` |
| `nmi()` | その時点でマスク不可能割り込みを受け付け、`$0066`から再開します | `None` |

### ピンと状態

| 属性 | 内容 |
|:--|:--|
| `irq_line` | レベルとしてのマスク可能割り込み要求です。各命令の最後のTステートでサンプリングされます |
| `nmi_line` | マスク不可能割り込み要求です。遷移で割り込みます。保持し続けても再び割り込むことはありません |
| `wait_line` | すべてのマシンサイクルのT2の後に読まれます。セットされたままのTステートごとにT2が繰り返されます |
| `on_cycle` | Tステートごとに1回、その終わりに呼ばれます。そのステートのバス動作と、次のステートまでに行う処理の後です |
| `cycles` | パーツの構築以降のTステート数で、リセットをまたいで数えます |
| `steps` | 最後のリセット以降の命令数です |
| `halted` | `HALT`を実行中かどうかです。`HALT`サイクルはそれぞれ4Tステートかかります |
| `registers` | 後述の`Registers`ファイルです |
| `bus` | 最後の命令です。`states`はそのTステート数、`cycles`はマシンサイクルごとの`(state, kind)`のリスト、`log`はTステートごとの`(address, value, pins)`のリストです。2つのリストは`recording=True`のときだけ埋まります。`kind`は`fetch`、`read`、`write`、`portRead`、`portWrite`、`acknowledge`のいずれかです |
| `memory`、`ports` | パーツの構築に使われたものです |
| `model` | 正規のモデル名です |

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

`ld a,n`は7Tステートかかります。オペコードフェッチのT2の後に読まれたとき、さらにその1ステート後にもウェイトラインがセットされたままなので、T2が2回繰り返され、命令は9Tステートかかります。`on_cycle`はそのすべてを見ています。

### 割り込み

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

プログラムは`im 1`、`ei`、`nop`、そして`nop`へ戻る`jr`です。ラインがセットされた状態で`jr`が完了し、パーツはその最後のTステートで要求をサンプリングし、戻りアドレス`$0003`をプッシュして`$0038`から再開します。決して成立しないチェックを渡した`run_until`は、`limit`が許す3命令の後にあきらめます。

### メモリとポート

| 名前 | 内容 |
|:--|:--|
| `SparseMemory(seed=UNSET_SEED)` | 書き込まれたものだけを保存する64 KBです。書き込まれていないバイトは、`seed`とアドレスから導かれる値として読めます |
| `Memory(size=0x10000, image=None, seed=UNSET_SEED, fill=None)` | フラットな`bytearray`です。`fill`がなければ`seed`からスクランブルされます。`image`はアドレス0からコピーされます |
| `Ports(seed=UNSET_SEED)` | I/O空間です。読み書きは`(address, value, "r" or "w")`として`log`に記録されます。書き込まれていないポートは、`seed`から導かれる値として読めます |
| `UNSET_SEED` | `0x5A5A5A5A`です。シードが与えられないときにすべてのスクランブルが使うシードです |

どのバスでもアドレスは16ビットです。ポートアドレスは、パーツが駆動するとおり、上位バイトにアキュムレータまたは`B`を持ちます。

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

`out ($34),a`は、オペコードフェッチ、オペランド読み出し、ポート書き込みからなり、11Tステートです。ログの各行は、バス上のアドレス、データライン上の値または`None`、そしてRD、WR、MREQ、IORQの順の4つのピンで、非アクティブは`-`です。フェッチの最後の2ステートには、`I`と`R`から作られるリフレッシュアドレスが載ります。続いてZ84C00上の`out (c),0`がポート`$0099`に`$FF`を送り、これがポートログの最後のエントリになります。

### レジスタ

`cpu.registers`は、`a`、`f`、`b`、`c`、`d`、`e`、`h`、`l`とペアの`af`、`bc`、`de`、`hl`、`sp`と`pc`、`ix`と`iy`およびその半分の`ixh`、`ixl`、`iyh`、`iyl`、シャドウセットの`af_`、`bc_`、`de_`、`hl_`、`i`、`r`、`iff1`、`iff2`、`im`、内部ペアの`wz`およびその半分の`w`と`z`、そして`q`を保持します。`q`は、直前の命令のフラグ結果についてコーパスが記録するラッチです。書き込みはレジスタの幅でマスクされます。

`Registers(seed=UNSET_SEED)`は、レジスタファイルを単独で構築します。`reset()`はRESETピンがレジスタファイルに対して行うことを行い、`exchange_set()`は`exx`、`exchange_accumulator()`は`ex af,af'`です。

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

### モデルとエラー

| 名前 | 内容 |
|:--|:--|
| `MODELS` | 3つの`Model`レコードで、正規名をキーとします |
| `Model` | `name`、`aliases`、`summary`、`floating_output`、`carry_rule`、`interrupt_clears_parity`、`verified`、そして`build(memory, **options)`です |
| `UnknownModelError` | モデルが指定されていない場合や、どのモデルにも該当しない名前の場合に`Cpu`が送出します。メッセージには3つのモデルが列挙されます |
| `UnknownShape` | `manual`または`recording`以外の`shape`に対して`Cpu`が送出します |
| `UnknownCarryRule` | `zilog`または`nec`以外のキャリールールに対して`Model`が送出します |
| `RunLimit` | `limit`命令を実行してもチェックが成立しなかったときに`run_until`が送出します |
| `Truncated` | 命令の途中でバイト列が終わったときに`decode`が送出します |
| `ClockClosed` | クロックが閉じられた後に`Clock.tick()`が送出します |
| `__version__` | インストールされているバージョンです |

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

### コマンドラインツール

どのツールもリポジトリのルートから実行します。適合性ツールはモジュールとして実行します。

| コマンド | 動作 | 終了コード |
|:--|:--|:--|
| `python3 z80/doctor.py` | マシン、パーツ、コーパスを報告します | 0はすべてのチェックに合格、1は不合格あり |
| `python3 -m conformance.fetch [directory] [--latest]` | コーパスを固定されたコミットで、`--latest`の場合はupstreamのheadで、`directory`にクローンします。デフォルトは`~/.cache/conformance-suites`です | 0は取得済み、1はupstreamに到達できないかgitのステップが失敗 |
| `python3 -m conformance.singlestep <suite-directory> [--limit N] [--opcode NAME]` | 各ケースの後のレジスタとメモリを比較します | 0は失敗なし、1は失敗ありまたはケースが見つからない、2は引数が不正 |
| `python3 -m conformance.cycles <suite-directory> [--limit N] [--opcode NAME] [--shape manual\|recording]` | 各Tステートのアドレス、データ、ピンを比較します。shapeのデフォルトは`recording`です | 0は失敗なし、1は失敗ありまたはケースが見つからない、2は引数が不正 |
| `python3 -m conformance.regenerate <output-directory> [--full] [--clone DIR]` | コーパスを生成したジェネレータからコーパスを再構築します。`node`が必要です | 0は書き込み済み、失敗時はジェネレータ自身のコード、1は引数が不正 |
| `python3 -m conformance.timing` | 記録にある命令ごとのタイミング行をすべて実行し、Tステート数を比較します | 0はすべての行が一致、1は不一致あり |
| `python3 -m conformance.quotes` | 文書を保持しているマシン上で、引用されたすべての文を引用元の文書の中から探します | 0はすべての引用が見つかった、1は見つからないものあり |
| `python3 -m conformance.documents [--check] [--only SUBSTRING]` | アドレスを持つ文書をダウンロードし、すべてのダイジェストを検証します。`--check`は検証だけを行います | 0はすべて検証済み、1は拒否されたものがあるか引数が不正 |
| `python3 -m conformance.netlist [--half-cycles N]` | トランジスタネットリストをリセットから`N`ハーフサイクル実行します。デフォルトは130です | 0はすべてのノードが安定、1は安定しないノードがあるかデータファイルがない |
| `python3 -m conformance.wz [output]` | ネットリストが`WZ`に残すものを読み、`output`に書き込みます。デフォルトは[`conformance/wz.json`](conformance/wz.json)です | 0は書き込み済み、1はネットリストがないかプローブが未較正 |
| `python3 -m conformance.speed [--instructions N] [--repeats N]` | 64 KBのイメージで`run_for(N)`の時間を計測します。デフォルトは200,000Tステートを7回です | 0は毎秒400,000Tステート以上、1は未満、2は引数が不正 |
| `python3 -m conformance.links` | このファイル内のすべてのアドレスにリクエストします | 0はすべてのアドレスがまだ存在、1はステータス`404`または`410`を返すものあり |
| `python3 -m conformance.package <wheel>` | ビルドされたwheelがすべてのモジュールを含み、テストを含まないことを確認します | 0は問題なし、1は不備ありまたはファイルが存在しない、2は引数なし |

## 実際の速度で動かす

`step()`は命令にかかったコストを報告するので、ホストは実時間のスライスごとに予算を費やすことで、パーツを水晶の周波数に合わせられます。

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

命令は途中で分割できないので、`run_for()`は予算を超過し、費やした分を返します。超過分を次のスライスに繰り越すことで、長時間の実行でもずれが生じません。

## 1Tステートずつ駆動する

`Clock(cpu)`は、任意の2つのTステートの間でパーツを止めます。ボードが読み出しへの応答を変えるのはそこです。

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

`$0001`のバイトはオペコードフェッチの最初のTステートの後に変更され、フェッチに続くオペランド読み出しが新しい値を取り込みました。

| 呼び出し | 動作 |
|:--|:--|
| `tick()` | 1Tステート進め、クロックのカウントを返します |
| `run_for(cycles)` | `tick()`を`cycles`回呼び、カウントを返します |
| `close()` | パーツを止め、`on_cycle`を元に戻します。`with`ブロックを抜けると呼ばれます |
| `cycles`、`closed` | tickのカウントと、クロックが閉じられているかどうかです |

クロックをイテレートすると、閉じられるまでtickします。パーツの内部で送出された例外は`tick()`から再送出され、クロックは閉じられます。

ティックはそのTステートの処理が終わってから止まります。命令の最後のTステートまでティックしたクロックは、開いていても閉じていても、パーツを`step()`と同じ状態にします。

Pythonは命令のコールスタックを中断できないため、パーツはスレッド上で動きます。各Tステートは2つのセマフォ間の受け渡しなので、クロックは`step()`よりはるかに遅く動きます。速度が必要なときは`step()`を、Tステートがどこに当たるかが問題のときは`Clock`を使ってください。

## モデル

命令セットは3つとも同じです。異なる動作は3つあります。

| 構築方法 | 単独の`OUT (C)`が送る値 | `SCF`と`CCF`の後の非公開フラグビット | `LD A,I`または`LD A,R`の後の割り込みがパリティをクリアするか | この3列の測定 |
|:--|:--|:--|:--|:--|
| `Cpu("z80")` | `$00` | アキュムレータとラッチ | はい、Zilogが記載しています | はい、コーパスで測定 |
| `Cpu("z84c00")` | `$FF` | アキュムレータとラッチ | いいえ、Zilogが修正しました | いいえ、Zilog自身の文 |
| `Cpu("upd780c")` | `$00` | アキュムレータのみ | 記載なし | いいえ、独立した研究 |

コーパスが記録しているのはNMOS Z80だけです。他の2つがZ80と共有する部分はすべて、Z80を通じて測定されています。それらを別のパーツにしている3つの列は測定されておらず、両方とも`Model.verified`は`False`です。

各モデルは、メーカーが販売したときの型番で指定できます。大文字小文字、`-`、`_`は無視されるので、`Cpu("Z84C00-10")`は`z84c00`を構築します。

| 構築方法 | 別名 |
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

このパッケージが実装していない型番は、近いものに解決されずに拒否されます。そのため`Cpu("z180")`は、呼び出し側が求めた命令を持たないZ80を返すのではなく、例外を送出します。

## 実行せずに読む

`decode(data, offset=0, address=0)`は1命令を読みます。`disassemble(data, address=0)`はすべての命令を読みます。どちらもパーツを必要としません。どちらも`address`、`size`、`raw`、`text`を持つ`Instruction`オブジェクトを返します。

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

相対ジャンプはジャンプ先を表示します。命令の途中でバイト列が終わると、`decode`は`Truncated`を送出します。`disassemble`はそのような命令の最初のバイトを`db`として書き出し、処理を続けます。

## 何もクリーンな状態では始まらない

レジスタとメモリは、電源投入時に再現可能なスクランブルされたパターンを保持します。何も書き込んでいないバイトの読み出しは実際のシリコンでは欠陥であり、ゼロを返すメモリはその欠陥を合格するテストに変えてしまうからです。レジスタをクリアする引数はありません。メモリが単一の値を保持するのは、呼び出し側が`fill`で構築したときだけです。

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

バイトはシードとアドレスから導かれるので、どの実行でも同じで、ゼロではありません。プログラムカウンタもスクランブルされており、まだ何もRESETを駆動していないので`cycles`は0です。`reset()`の前にパーツをステップ実行すると、そのアドレスにあるものが何であれ実行されます。

## 正しいのか

すべての命令はSingleStepTestsコーパスに照らして実行されます。このコーパスは、各レジスタとメモリの各バイトの前後の状態を記述しています。結果は**1,604,000件、失敗0件**です。2つ目のランナーは、パーツがバスに出したものを、Tステートごとにアドレス、データ、ピンで比較します。結果は**22,005,372Tステート、失敗0件**です。

```bash
python3 -m conformance.fetch ~/.cache/conformance-suites
python3 -m conformance.singlestep ~/.cache/conformance-suites/z80/v1
python3 -m conformance.cycles ~/.cache/conformance-suites/z80/v1
```

```
1604000 cases, 0 failed, 0 opcodes affected
1604000 cases, 22005372 T states compared, 0 failed, 0 opcodes affected, 0 opening states skipped, shape recording
```

コーパスのコミットは[`conformance/suites.json`](conformance/suites.json)で固定されており、週次のジョブがupstreamのheadに対して実行され、プルリクエストまたはissueを作成します。何もパースしなかった実行も、すべてをチェックした実行と同じく0で終了するため、各ランナーはチェックしたケース数を表示します。

マニュアルは別に管理しています。[`conformance/hardware.json`](conformance/hardware.json)は、文書から取ったすべての事実をその文とページとともに保持し、[`conformance/hardware.test.py`](conformance/hardware.test.py)とその隣の`hardware_*.test.py`ファイルは、マシン上にコーパスがない状態でパーツを動かし、マシンサイクルを1つずつそれに照らしてチェックします。`python3 -m conformance.timing`は、命令ごとのタイミング行217行をすべて実行し、それぞれをパーツが費やすTステート数と比較します。マニュアルは5か所で自己矛盾しています。3か所は99、260、269ページのタイミング行で、Mサイクル数が自身のTステートの内訳と一致しません。残りの2か所は本文と図が一致しません。2つの情報源が食い違うすべての箇所は、それを決着させる方法とともに[`conformance/divergences.json`](conformance/divergences.json)にあります。

[OPEN-QUESTIONS.md](OPEN-QUESTIONS.md)には、忠実性が測定ではなく主張にとどまっている18の問いが、それぞれを解決する測定とともに列挙されています。フラグレジスタのビット3とビット5、および内部の`WZ`レジスタは、Zilogのユーザーマニュアルとデータブックの780ページのどこにも登場しません。

### ダイに尋ねる

[`conformance/netlist.py`](conformance/netlist.py)は、ダイ写真から抽出したネットリストを使い、パーツをトランジスタのネットとして実行します。リセットから駆動すると、`$0000`からフェッチし、サンプルプログラムを実行します。

```bash
python3 -m conformance.netlist
```

リゾルバは、Visual 6502プロジェクトの`chipsim.js`と`wires.js`に倣っています。これらはMITライセンスです。その告知は[THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md)にあります。3つのデータファイルはこのリポジトリにはありません。[`conformance/netlist.manifest.json`](conformance/netlist.manifest.json)がそれらの名前、入手元、各ダイジェストを記録しています。`docs/independent/visual6502`に置いてください。ダイジェストが異なるファイルは読み込み時に拒否されます。

トランジスタファイルは32個のエントリをプルアップとしてマークしており、それらをプルアップとして読み込んだときだけネットが安定します。名前が二重になったネットは命令が書き込むレジスタセットを、1文字の名前のネットはシャドウセットを保持します。これは、すべてのレジスタとすべてのビット位置にわたる`LD r,n`で確認できます。

パッケージ内のどの部分もネットリストに照らして検証されてはいません。ネットリストは抽出物であり、抽出は誤ることがあるため、メーカーの文書や実際のパーツからの記録よりも下位に位置付けています。

## 開発に参加する

| 必要なもの | 場所 |
|:--|:--|
| すべてのゲートと実行順序 | [CONTRIBUTING.md](CONTRIBUTING.md) |
| コーディングエージェント向けの同じ内容 | [AGENTS.md](AGENTS.md) |
| このリポジトリがファミリーの他のリポジトリと共有する標準 | [FAMILY.md](FAMILY.md) |
| バグ報告 | [GitHub Issues](https://github.com/gufranco/zilog-z80-python/issues) |
| セキュリティ報告 | [SECURITY.md](SECURITY.md) |

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

各モジュールには`<module>.test.py`という名前のテストファイルが隣にあり、それぞれ単独で実行できます。カバレッジはステートメントとブランチで100%を求める必須のゲートです。型は`mypy`のstrictです。速度チェックは毎秒400,000Tステートを下回ると失敗し、カバレッジのステップとは別に実行されます。コミットは[Conventional Commits](https://www.conventionalcommits.org/)に従います。

## 参考文献

このリポジトリは文書を含みません。各行にはページ数とファイルのSHA-256の先頭16文字を記載しているので、読者は同じファイルを取得して同じページを確認できます。完全なダイジェストは`shasum -a 256 <file>`で計算してください。

以下のメーカー文書はすべて著作権で保護されており、再配布できません。個々の文は、引用元のページとともに[`conformance/hardware.json`](conformance/hardware.json)に引用されています。

| 文書 | 日付 | ページ数 | SHA-256 | 再配布 |
|:---------|:-----|------:|:--------|:----------------|
| [Zilog, *Z80 CPU User Manual*, UM008011-0816](https://www.zilog.com/docs/z80/um0080.pdf) | 2016-08 | 332 | `e3c83da5a5d8e372…` | 不可 |
| Zilog, *Z80 Family Data Book*, 00-2490-01 | 1989-01 | 448 | `844681b63ffc45bd…` | 不可 |
| Zilog, *Z84C00 Product Specification*, PS017801-0602 | 日付なし | 36 | `06198d3c22a79a3f…` | 不可 |
| NEC, *µPD780C*データシート | 日付なし | 24 | `2036fa845533feee…` | 不可 |

独立した研究は、互いに参照し合っていない2つの系統が一致する場合にだけ使い、メーカーが示した数値の出典としては決して使いません。

| 文書 | 著者 | ページ数 | SHA-256 | ライセンス |
|:---------|:-------|------:|:--------|:--------|
| [*The Undocumented Z80 Documented*, v0.91](https://archive.org/details/the-undocumented-z80-documented) | Sean Young, 2005-09-18 | 52 | `6413048f39c2e735…` | GFDL 1.1以降 |
| [*Z80 CCF SCF Outcome Stability*](https://github.com/redcode/Z80/wiki/Z80-CCF-SCF-Outcome-Stability) | Sainz de Baranda y Goñi, Brewer, Helcmanovsky | 4 | `be87311012f9edaf…` | GFDL 1.3 |
| *Undocumented Z80 Flags*, rev 1.0 | David Banks, 2018-08-21 | 3 | `33766df5494e2fdf…` | 記載なし |
| *MEMPTR, esoteric register of the ZiLOG Z80 CPU* | Boo-boo、Vladimir Kladov訳 | テキスト | `f9e8e87cdd205e15…` | 記載なし |
| [redcode/Z80 wiki: Interrupts](https://github.com/redcode/Z80/wiki/Interrupts)と[MEMPTR](https://github.com/redcode/Z80/wiki/MEMPTR) | Sainz de Baranda y Goñiほか貢献者 | Web | n/a | GFDL 1.3 |

| 情報源 | 用途 |
|:-------|:---------|
| [SingleStepTests/z80](https://github.com/SingleStepTests/z80.git) | 固定されたコーパス、1,604,000件です。コミットは[`conformance/suites.json`](conformance/suites.json)にあります |
| [raddad772/jsmoo](https://github.com/raddad772/jsmoo.git) | コーパスを生成したジェネレータです。ダウンロードするだけでなく再構築できるようにするためです |
| [gdevic/Z80Explorer](https://github.com/gdevic/Z80Explorer) | その動作が[`conformance/divergences.json`](conformance/divergences.json)に記録されているネットリストです |

[`conformance/documents.json`](conformance/documents.json)は、各文書の完全なダイジェストとバイト数を保持しています。[`conformance/documents.py`](conformance/documents.py)は、gitが無視する`docs/`にダウンロードし、ダイジェストが一致しないファイルを拒否します。

```bash
python3 -m conformance.documents
python3 -m conformance.documents --check
```

8つの文書のうち2つはアドレスを持ち、ダウンロードされます。残りの6つはWebページから印刷されたものなので、コマンドは利用者が用意したコピーを検証し、それを置き換えることはありません。

MEMPTRの論文は上記でテキストとして固定されています。`docs/`にあるコピーは同じ文章を印刷したものなので、2つのダイジェストは異なり、一方を他方のダイジェストで照合すると不一致が報告されますが、それには何の意味もありません。

## 引用

[CITATION.cff](CITATION.cff)は、パッケージのバージョンを刻むスクリプトによってリリースごとに更新されます。GitHubはこれを「Cite this repository」ボタンとして表示します。

## ライセンス

MITです。[LICENSE](LICENSE)を参照してください。
