# WrenchVR-Chinese · Wrench 简体中文汉化补丁

给 Steam 游戏 **Wrench**（Missing Digit，UE4 赛车维修模拟）做的非官方简体中文补丁。
由两部分组成：
1. 往游戏的 `Paks` 文件夹加一个约 1 MB 的补丁包 `zzz_WrenchZhCN_P.pak`（资源里的文本）；
2. 把游戏 exe 里写死的英文**原位替换**成中文（教程步骤、任务评价、设置页等）。改之前自动备份原版 exe，卸载时还原。

已在 v162~3615（2026-06 版本）实测：主菜单、平板应用名、更新日志、教程板等显示中文，字形正常、长文本自动换行。

## 用法

```
git clone https://github.com/GuangxianZhu/WrenchVR-Chinese.git
```
克隆到任意位置都行，然后双击下面的 bat。


| 文件 | 作用 |
|---|---|
| `一键安装汉化.bat` | `git pull` 检查更新 → 从**你自己的游戏文件**提取文本、生成补丁 → 装进游戏 → 可选直接启动游戏 |
| `卸载汉化.bat` | 删除补丁包、还原原版 exe，恢复英文 |

- 需要 Python 3.8+（bat 会依次找 `py -3`、`%USERPROFILE%\miniconda3`、`anaconda3`、`python`）。
- 游戏路径自动从 Steam 注册表和 `libraryfolders.vdf` 找；找不到就在本文件夹建 `game_path.txt`，写一行游戏目录，例如 `D:\SteamLibrary\steamapps\common\Wrench`。
- 只想要补丁包、不想动 exe：在命令行运行 `一键安装汉化.bat --no-exe`。
- 安装/卸载前请**完全退出游戏**（exe 运行时被占用，改不了）。
- **游戏更新后**重新双击一次安装 bat（Steam 更新会把 exe 换回英文原版，这是正常的）：会按新版本重新提取并生成。新增的、还没翻译的句子会显示英文，并列在 `data/untranslated.json`。

## 覆盖范围

| 文本来源 | 数量 | 状态 |
|---|---|---|
| 资源里的 FText（界面、零件名、目录、教程、故障症状…） | 2,462 条 | ✅ |
| 蓝图字节码里的文本常量（弹窗、提示、比赛信息、日期…） | 607 条 | ✅ |
| 平板应用名（FName，locres 管不到） | 16 个 | ✅ 改名表方式 |
| 写死在 exe 里的 C++ 文本（开场教程、任务评价、生涯说明、设置页…） | 约 1,700 条 | ✅ exe 原位替换 |
| exe 里同时被当作「标识符」用的词（如按键动作名 Sprint、Tablet，应用 ID Settings） | 少量 | ❌ 故意不改，见原理 6 |
| 文化无关文本（如 "Multiplayer Log"）、3D 贴图上的字 | 少量 | ❌ |

## 原理（为什么这样做）

1. **UE4 怎么显示文本**：资源里的每句可翻译文本存成（命名空间, key, 英文原文）。显示时引擎拿 (命名空间, key) 去当前语言的 `Game.locres` 翻译表里查；
   查到了还要比对「原文哈希」（CRC32，按 UTF-32 计算），一致才用译文，不一致就当翻译过期、退回英文。
   → 所以补丁只需要一张 locres，不用改资源本体；游戏更新改了某句英文，那句会**安全地退回英文**而不是乱码或崩溃。
2. **为什么把中文放在 `en` 文件夹**：游戏打包时只带了英文的 ICU 语言数据（`CulturesToStage=en`），切到 `zh-Hans` 会失败、留在英文。
   直接用中文表「冒充」英文表，引擎照常加载 `en`，显示的就是中文。（也同时放了 zh/zh-Hans/zh-CN/ja 几份，作保险。）
3. **补丁包为什么能覆盖**：UE 挂载 pak 时，文件名以 `_P` 结尾的优先级更高，同路径文件以补丁为准。原版 pak 没加密、没压缩（pak v11），所以能直接读，也能用纯 Python 写出引擎认可的 pak。
4. **平板应用名**：它们是 `WrenchOSAppConfigs` 里的 FName 属性（运行时 `FText::FromName`），不走翻译表。
   而且同一个名字条目常被 `DisplayName` 和 `NameId`（程序内部用的 ID）共用，直接改名会让程序找不到应用。
   做法是在该资源的名字表**末尾追加**中文名，只把 `DisplayName` 指向新条目；原有条目编号和含义都不变。改好的这份资源只放在补丁包里。
6. **exe 里写死的文本**：C++ 代码是按「地址」引用字符串常量的，所以译文必须放在原地址。中文通常比英文短，写进去后用 0 补齐剩余字节（字符串只是提前结束）；
   超长的译文会被跳过、保持英文。只替换 `.rdata` 段里前后都以 `\0\0` 结尾的**完整**字符串，不碰部分匹配。
   风险在于同一个字符串常量可能既用于显示、又被代码当作 ID（比如按键动作名 `Sprint`）——改了 ID 会让按键失灵。
   所以提取时把所有在游戏资源名字表（FName）和配置文件里出现过的字符串都当作「可能是标识符」排除掉，宁可少翻也不冒险。
   安装时先备份原版 exe（`*.zh_backup`），并记录原版/汉化版的哈希：重复安装总是从干净的原版重新打补丁；检测到 exe 变了（游戏更新或 Steam 校验）就把新 exe 当作新原版。
7. **中文字形**：引擎默认字体 Roboto 带 DroidSansFallback 作为后备字体，所以中文能显示，不需要额外打字体。

## 依赖的假设 / 什么情况下会失效

- pak 保持「不加密、不压缩、v10/v11 带完整目录索引」。如果开发者改成加密 pak 或 IoStore（.utoc/.ucas），提取器会报错。
- 文本仍用 UE 标准本地化文本。如果之后改用 StringTable 或更多 C++ 硬编码文本，那些会显示英文。
- exe 补丁基于「完整字符串内容」匹配，不依赖地址，所以游戏更新后重跑 bat 仍有效；新增的 C++ 文本会是英文，可用 `python tools/extract_exe.py` 列出来补翻。
- 如果 exe 补丁导致异常：运行卸载 bat，或在 Steam 里「验证游戏文件完整性」即可恢复原版 exe。
- `WrenchOSAppConfigs` 结构变了时，构建会自动**跳过**应用名这一步（打印提示），其余照常。
- 翻译是 AI 机翻 + 术语表约束，难免有不地道的地方，欢迎直接改 `data/zh_CN.json`（英文原文 → 中文），改完重跑安装 bat。

## 文件结构

```
一键安装汉化.bat / 卸载汉化.bat
data/zh_CN.json        资源文本：英文原文 → 中文（可手改）
data/zh_exe.json       exe 内置文本：英文 → 中文（译文不能比英文长）
data/glossary.md       术语表
tools/build.py         入口：提取 → 生成 locres → 打 pak → 安装/卸载
tools/extract.py       从游戏 pak 提取 FText（属性 + 蓝图字节码）
tools/locres.py        写 UE4 .locres（legacy 格式）
tools/pakfile.py       纯 Python 读写 UE4 pak v11（无压缩、无加密）
tools/uasset.py        解析/改写 uasset 包头与名字表
tools/appnames.py      平板应用名汉化
tools/exepatch.py      exe 原位替换（备份/还原/哈希状态）
tools/extract_exe.py   维护用：列出 exe 里还没翻译的文本
```
