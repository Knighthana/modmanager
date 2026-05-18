我为你逐一拆解 Steam 的底层逻辑，并给出工具开发所需的**算法判定公式**。

---

## 1. 机制判断：Steam 是否永远保证 MOD 尽力保持最新？

**结论：不会。MOD 依然可以被“卡更新”，不能盲目信任 Steam 会自动帮玩家装好。**

虽然 Steam 创意工坊没有像游戏本体那样显眼的“暂停更新”按钮，但在以下几种常见场景下，玩家的 MOD 会处于“有更新，但本地没装上”的卡死状态：

* **游戏正在运行（最常见）**：如果玩家正在运行该游戏（甚至运行其他部分游戏），Steam 会默认**暂停所有工坊内容的下载**，防止占用硬盘和网络。
* **Steam 下载设置限制**：玩家可能在 Steam 设置中开启了“仅在以下时间段自动更新”或“在游戏中时限制后台下载”。
* **下载队列被积压**：如果玩家订阅了大量 MOD，或者有大型游戏正在更新，MOD 会在下载列表里“排队（Queued）”，显示为“需要更新”但迟迟不开始。
* **Steam 处于离线模式 / 网络故障**。

> **工具开发结论**：你的工具**绝对不能**假设“只要有更新，玩家电脑里就一定是最新版”。你必须在代码里做状态检查。

---

## 2. 核心算法：如何拿到在所有玩家之间一致的“版本核验时间戳”？

在所有玩家都处于“游戏未运行、MOD 已完全下载”的稳定期间内，**唯一绝对一致、适合作为版本 ID 的时间戳，是 `WorkshopItemDetails` 中的 `latest_timeupdated**`。

在你的代码中，对于某一个特定的 `workshopid`，提取版本戳的伪代码逻辑与校验如下：

### 校验算法

假设你想核验两个玩家（或玩家与服务器）的 MOD 版本是否完全一致，你需要从 `appworkshop_{appid}.acf` 中提取两个值：

* $T_{local}$ = `WorkshopItemsInstalled` $\rightarrow$ `workshopid` $\rightarrow$ `timeupdated`
* $T_{remote}$ = `WorkshopItemDetails` $\rightarrow$ `workshopid` $\rightarrow$ `latest_timeupdated`

### 提取与核验步骤：

1. **第一步：检查本地是否“版本落实”**
* 判断公式：$T_{local} \ge T_{remote}$
* 如果不满足，说明本地还没下载完（属于不稳定期间），直接拒绝核验，提示玩家“等待 Steam 下载”。


2. **第二步：跨玩家比对**
* 当所有玩家都满足第一步后，**直接取各个玩家的 $T_{remote}$（即 `latest_timeupdated`）进行对比**。
* 如果 玩家A的 $T_{remote} ==$ 玩家B的 $T_{remote}$，则**版本绝对一致**。这个 $T_{remote}$ 就是你们联机或核验时唯一的“Version ID”。



---

## 3. 状态判断：如何判断当前“情况不稳定”，需要等待下载？

作为第三方工具，如果你想判断“现在能不能安全地备份/读取 MOD”，可以通过解析 `appworkshop_{appid}.acf` 文件，结合以下 **3 层漏斗算法** 来断定系统是否处于“不稳定”状态：

### 第一层：ACF 状态码判定（最快）

在 ACF 文件的根节点，有一个全局字段叫 `"NeedsUpdate"` 或 `"NeedsDownload"`（部分游戏表现为 `WorkshopItemDetails` 下的 `"manifest"` 缺失或为 `"0"`）。

* **不稳定信号**：如果全局检测到需要更新，或者某个 MOD 块里有明显的排队标志。

### 第二层：时间戳差值判定（最精准）

循环遍历你工具关心的所有 `workshopid`：

* **不稳定定义**：

$$\exists \, \text{workshopid} \quad \text{s.t.} \quad T_{local} < T_{remote}$$


* **含义**：只要存在任意一个 MOD，它的本地安装时间（$T_{local}$）**小于** 服务器最新发布时间（$T_{remote}$），说明该 MOD 已经有新版本发布，但本地还没下载/还没下载完。
* **工具动作**：判定为“不稳定”，**禁止备份**，提示用户：“MOD [ID] 正在等待 Steam 更新，请确保 Steam 下载队列完成”。

### 第三层：文件锁与临时文件夹判定（防极端情况）

有时候 Steam 正在写入文件，ACF 文件还没来得及更新。你可以让工具去扫描 Steam 的临时下载目录：

* **路径**：`steamapps/workshop/downloads/{appid}/`
* **不稳定定义**：如果这个 `downloads` 文件夹内存在正在下载的缓存文件，或者对应的 MOD ID 文件夹不为空。
* **含义**：Steam 正在疯狂写盘，此时 MOD 文件是不完整的碎块。
* **工具动作**：判定为“严重不稳定”，**绝对禁止备份**，否则会备份到一个损坏的 MOD。

### 总结工具伪代码逻辑：

```python
def check_download_dir_status(download_dir):
    """
    检查 Steam 临时下载目录的状态
    返回: (is_safe, status_type, message)
    """
    if not os.path.exists(download_dir):
        return True, "SUCCESS", "目录不存在，安全"
        
    # 获取该目录下所有的文件和文件夹
    items = os.listdir(download_dir)
    if not items:
        return True, "SUCCESS", "目录为空，安全"

    # 检查目录下是否存在任何实际文件（包括深层子目录里的文件）
    has_real_files = False
    for root, dirs, files in os.walk(download_dir):
        if files: # 只要任意子目录下找到了文件
            has_real_files = True
            break

    if has_real_files:
        # 核心逻辑 1：对应目录非空（有实际文件），属于错误
        return False, "ERROR", "Steam正在下载MOD文件中"
    else:
        # 核心逻辑 2：对应目录虽有文件夹，但均为空，属于警告
        warn_msg = (
            f"`downloads/`目录非空（存在空残留目录），正在尝试尽力处理。\n"
            f"如果备份结果出现错误，请删除备份目录；\n"
            f"如果此MOD目前并不处于更新状态，建议手动删除 `downloads/` 中对应的空目录以清除此警告。"
        )
        return True, "WARNING", warn_msg
        
    # 2. 遍历检查每个MOD的时间戳
    for mod_id in acf_file.get_all_mod_ids():
        t_local = acf_file.get_installed_time(mod_id)
        t_remote = acf_file.get_latest_time(mod_id)
        
        if t_local < t_remote:
            return False, f"MOD {mod_id} 版本滞后，等待Steam更新"
            
    return True, "环境稳定，可以备份/核验"

```

# 对游戏本体进行版本核验

## 使用 "buildid"（Steam 官方的绝对版本号）

在 appmanifest_{appid}.acf 中，有一个天然就是为了标记版本而存在的字段："AppState" -> "buildid"。

什么是 BuildID：当游戏开发者向 Steam 开发者后台（Steamworks）提交一个新版本并发布到 public 分支时，Steam 服务器会自动为该次提交生成一个全局唯一的、递增的数字（例如：14325678）。

为什么用它：

全服统一：只要游戏开发者推送了更新，全世界所有更新到该版本的玩家，其 ACF 文件中的 "buildid" 都是完全相同的数字。

不受个人行为影响：无论玩家何时下载、何时关游戏、是否同步云存档，"buildid" 只要不更新就永远锁死。

如何提取：
直接用文本或 JSON/KeyValues 解析器读取 ACF 文件中的 "buildid" 字段值即可。

## 游戏本体环境的“稳定状态”判定算法

类似于创意工坊，在你要获取版本或进行备份前，必须判断游戏现在是否处于“正在更新/由于运行而被卡更新”的不稳定状态。

你可以通过 appmanifest_{appid}.acf 中的另一个核心字段 "StateFlags"（状态标志位）来判定：

"AppState"."StateFlags" 状态魔术数字
StateFlags 是一个位掩码（Bitmask）整数，常见的状态组合如下：

4：StateFullyInstalled（环境绝对稳定）。说明游戏已完全安装，没有排队，没有正在下载，也没有损坏。

6 / 1026：游戏正在运行（StateRunning）。

8 / 12 / 1032 等：游戏需要更新（StateUpdateRequired）、正在下载（StateDownloading）、或者更新被暂停（StateUpdatePaused）。

推荐的工具校验逻辑（Python 示例）：
```python
def check_game_environment_status(acf_data):
    """
    检查游戏本体是否处于稳定可备份/核验状态
    """
    state_flags = int(acf_data.get("AppState", {}).get("StateFlags", 0))
    build_id = acf_data.get("AppState", {}).get("buildid", "")

    # 1. 安全锁：只有当 StateFlags 正好等于 4 时，才说明游戏处于完美的静态、已完全安装状态
    if state_flags != 4:
        # 如果包含运行中、更新中、排队中等标志
        return False, f"游戏当前状态不稳定(StateFlags:{state_flags})，请确保游戏已关闭且Steam中没有未完成的下载。", None

    # 2. 获取版本验证数字
    if not build_id:
        return False, "未能读取到合法的 buildid", None

    # 环境稳定，返回唯一的版本确定数字 build_id
    return True, "游戏环境稳定", build_id
```
