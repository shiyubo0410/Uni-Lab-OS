# 香橙派网关 · 蓝牙(BLE)配网协议契约 v1

> 本文档是**网关固件**与 **APP** 之间的接口契约。双方按此实现即可独立开发、
> 后期联调。任何字段/UUID/流程的改动都必须双方同步更新本文件的版本号。
>
> - 配置范围:**仅 WiFi**(SSID + 密码)。AK/SK 等云端参数仍走现有网页管理后台。
> - APP 载体:**原生 Android + iOS**。
> - 角色:网关 = BLE Peripheral / GATT Server;APP = Central / GATT Client。

---

## 1. 广播(Advertising)

| 项 | 值 |
|---|---|
| Local Name | `UniLab-GW-XXXX`(XXXX = WiFi MAC 后 4 位 hex 大写,规则同现有 AP SSID) |
| 广播 Service UUID | `0000A100-0000-1000-8000-00805F9B34FB`(供 APP 扫描过滤) |
| 可连接 | 是(Connectable, Undirected) |
| 广播间隔 | 建议 100~200ms |

APP 扫描时**按广播里的 Service UUID `A100` 过滤**,只展示名称前缀 `UniLab-GW-` 的设备。

---

## 2. GATT 服务与特征

主服务 **UniLab Provisioning Service**:`0000A100-0000-1000-8000-00805F9B34FB`

下面 5 个特征,UUID 形如 `0000A1xx-0000-1000-8000-00805F9B34FB`(仅 `xx` 不同):

| 特征 | 短 UUID | 属性 | 方向 | 作用 |
|---|---|---|---|---|
| DeviceInfo | `A101` | Read + Notify | 网关→APP | 设备信息 + 配网状态 + 加密公钥 |
| ScanCtrl | `A102` | Write | APP→网关 | 触发/控制 WiFi 扫描 |
| ScanResult | `A103` | Notify | 网关→APP | 逐条下发扫描到的 WiFi |
| Provision | `A104` | Write | APP→网关 | 提交 WiFi 凭证(加密) |
| Status | `A105` | Notify | 网关→APP | 实时配网进度/结果 |

APP 连接后应先对 **DeviceInfo / ScanResult / Status** 开启 notify(写 CCCD)。

---

## 3. MTU 与分帧

1. APP 连接后**必须发起 MTU 协商**,请求 ATT_MTU = **247**(有效载荷 244B)。
2. 为避免重组复杂度,协议设计为**"每条消息尽量单包"**:
   - **ScanResult**:网关**每个 WiFi 发一条独立 notify**(单个 AP 的 JSON 远小于 244B),扫描结束后再发一条 `{"done":true,"count":N}`。APP 无需重组。
   - **Status**:每次状态更新一条独立 notify,天然单包。
   - **Provision**:加密后的载荷(见 §6)对典型 SSID/密码约 100~160B,MTU=247 下**单次 Write 即可**。
3. 兜底:若某次 Provision 载荷超过一次 ATT 写入上限,APP 用 **Write Long(Prepared Write)**,由 BLE 协议栈透明分片,网关侧 BlueZ 自动重组;**不引入自定义分帧头**。

---

## 4. 特征数据格式(JSON,UTF-8)

### 4.1 DeviceInfo(A101,Read/Notify)

```json
{
  "name": "UniLab-GW-5121",
  "sn": "f41ac1665121",
  "fw": "1.2.0",
  "state": "need_provision",
  "pubkey": "<base64(32B X25519 公钥)>"
}
```

- `state` 枚举:`need_provision`(待配网) / `connecting`(配网进行中) / `online`(已联网)。
- `pubkey`:网关本次会话的**临时 X25519 公钥**,APP 用它做密钥协商(见 §6)。每次 BLE 连接建立时网关**重新生成**一对临时密钥。
- APP 连上后先 Read 一次;之后 `state` 变化网关会主动 Notify。

### 4.2 ScanCtrl(A102,Write)

```json
{ "cmd": "scan" }
```

- 目前仅 `scan` 一个命令。网关收到后在 STA 模式扫描,通过 ScanResult 逐条回传。

### 4.3 ScanResult(A103,Notify)

每个 WiFi 一条:

```json
{ "ssid": "MyWiFi", "signal": 82, "security": "WPA2" }
```

扫描结束标志(最后一条):

```json
{ "done": true, "count": 12 }
```

- `signal`:0~100。`security`:`Open` / `WPA2` / `WPA3` 等(透传 nmcli 结果)。
- 隐藏网络不出现在列表里,APP 需支持**手动输入 SSID**。

### 4.4 Provision(A104,Write)—— 加密,见 §6 的封装

明文(加密前)结构:

```json
{ "ssid": "MyWiFi", "password": "12345678" }
```

### 4.5 Status(A105,Notify)

```json
{ "step": 1, "ok": null, "msg": "正在连接 WiFi…" }
```

- `step`:见 §5 状态码。
- `ok`:`true`/`false`/`null`(进行中)。
- `msg`:可直接展示的中文文案(网关侧复用现有 `wifi_manager._translate_nmcli_error()` 的语义)。

---

## 5. 状态码(Status.step 枚举)

| step | 含义 | ok |
|---|---|---|
| 0 | 已收到凭证 | null |
| 1 | 正在连接 WiFi | null |
| 2 | 已获取 IP | null |
| 3 | 正在验证公网连通 | null |
| 10 | ✅ 配网成功(已联网) | true |
| 20 | ❌ 密码错误 | false |
| 21 | ❌ 找不到该 SSID | false |
| 22 | ❌ 已连上但无法访问公网 | false |
| 23 | ❌ 连接超时 | false |
| 29 | ❌ 其它失败(msg 给详情) | false |

- 成功(step=10)后,网关 `DeviceInfo.state` 变为 `online`,并可在 msg 或后续 Notify 里附带拿到的 LAN IP。
- 失败(step≥20)后,网关**保持 BLE 连接不断、不重启**,APP 可直接重新走 §7 的第 4 步重试。

---

## 6. 加密(X25519 ECDH + AES-256-GCM)

WiFi 密码敏感,`Provision` 特征内容必须加密。链路层不依赖 BLE 配对,改用**应用层加密**,双端一致、体验可控。

**密钥协商:**
1. 网关每次连接生成临时 X25519 密钥对,公钥放在 `DeviceInfo.pubkey`。
2. APP 生成自己的临时 X25519 密钥对,读到网关公钥后计算 ECDH 共享密钥 `Z`。
3. 双方用 **HKDF-SHA256**(salt 为空,info = `"unilab-ble-prov-v1"`)从 `Z` 导出 **32B AES-256 密钥 `K`**。

**Provision 写入的字节布局(不是 JSON,是二进制):**

```
[0]      version    = 0x01           (1B)
[1..32]  app_pubkey = APP X25519 公钥 (32B)
[33..44] nonce      = 随机           (12B)
[45..]   ciphertext = AES-256-GCM(K, nonce, 明文JSON) ‖ tag(16B)
```

- 明文 JSON 即 §4.4 的 `{"ssid","password"}`。
- GCM 的 AAD 为空。tag 16B 附在密文末尾(标准 AEAD 布局)。
- 网关用自己私钥 + `app_pubkey` 复算 `K`,解密得到凭证。

> **联调提示**:bring-up 阶段网关会提供一个**明文调试开关**(`version=0x00` 表示后续直接是明文 JSON,不加密),方便用 nRF Connect 手测。**正式版必须走 `0x01` 加密路径,生产固件应拒绝 `0x00`。**

---

## 7. 完整交互时序

```
APP                                            网关(GW)
 |  BLE 扫描(过滤 Service A100)                 | 广播 UniLab-GW-XXXX
 |------------------ 连接 ---------------------->|
 |  协商 MTU=247                                 |
 |  订阅 DeviceInfo/ScanResult/Status 的 notify   |
 |  Read DeviceInfo ---------------------------->|
 |<-- {name,sn,fw,state,pubkey} -----------------|
 |                                               |
 | ① 扫描 WiFi                                   |
 |  Write ScanCtrl {"cmd":"scan"} -------------->| STA 模式扫描
 |<-- Notify ScanResult {ssid,signal,security} --|  (逐条)
 |<-- Notify ScanResult {...} -------------------|
 |<-- Notify ScanResult {"done":true,"count":N}--|
 |                                               |
 | ② 用户选 SSID + 输密码                         |
 | ③ ECDH 协商出 K,加密凭证                       |
 |  Write Provision [ver|pubkey|nonce|cipher] -->| 解密
 |                                               |
 | ④ 实时进度                                     |
 |<-- Notify Status {step:0,...} ----------------| 收到凭证
 |<-- Notify Status {step:1,...} ----------------| 连接 WiFi(在线,不 reboot)
 |<-- Notify Status {step:3,...} ----------------| 验证公网
 |<-- Notify Status {step:10,ok:true,msg:...} ---| ✅ 成功
 |<-- Notify DeviceInfo {state:"online"} --------|
 |  (可断开蓝牙,配网完成)                          |
 |                                               |
 | 若失败:Status {step:20,ok:false} → APP 回到②重试(蓝牙不断、GW 不重启)
```

---

## 8. 边界与错误处理

- **蓝牙断连**:配网进行中 APP 意外断连,网关应中止当前尝试、回到 `need_provision`,不残留半连状态。
- **重复提交**:网关一次只处理一个 Provision;进行中再收到新的应拒绝或排队(建议拒绝并回 `step:29`)。
- **超时**:单次连接尝试建议 30~45s 超时(与现有 `WiFiManager.CONNECTION_TIMEOUT` 对齐),超时回 `step:23`。
- **权限(APP 侧)**:Android 需运行时申请蓝牙扫描/连接权限(Android 12+ 的 `BLUETOOTH_SCAN`/`BLUETOOTH_CONNECT`,更低版本需定位权限);iOS 需 `NSBluetoothAlwaysUsageDescription`。
- **多网关同现场**:靠广播名后 4 位区分,建议设备贴 MAC 后 4 位贴纸辅助识别。

---

## 9. 版本

- v1(本文件):仅 WiFi 配网,原生 App,X25519+AES-GCM 加密。
