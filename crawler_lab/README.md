# 爬虫与网页自动化实验区

本目录只用于本地调研和探针，不进入 Docker 镜像或服务器发布包。已接入生产运行链路的船司适配器位于 `trace_api_probe/providers/`。

目标站点：

```text
https://www.weiyun001.com/track?regionredirected=true
```

## 当前目标

先验证是否能用“纯 HTTP 爬虫”拿到查询接口线索；如果纯爬虫拿不到，再进入网页自动化实验。

## 当前发现

- 页面是 Next.js 应用。
- 纯 HTTP 可以拿到 HTML。
- HTML 中包含大量 `/_next/static/chunks/...js`。
- 页面引入了阿里 `antidom.js`，说明可能存在前端保护或反自动化逻辑。
- 页面源码里能看到船司卡片和图片资源，但真正提交查询的 API 需要继续从 JS chunk 或浏览器 Network 中定位。

## 脚本

### 1. 探测 HTML

```bash
python crawler_lab/http_probe.py
```

输出：

- HTTP 状态码
- Content-Type
- 页面标题
- script 列表
- 页面中疑似 tracking/API 的关键词

### 2. 搜索 JS chunk

```bash
python -m crawler_lab.chunk_probe
```

输出：

- 下载页面中同域名 JS chunk
- 搜索疑似接口关键词
- 打印包含 `api`、`track`、`booking`、`container`、`bill`、`shipment` 等关键词的片段

### 3. 抽取疑似接口端点

```bash
python -m crawler_lab.endpoint_probe
```

当前已发现关键 API 基址：

```text
https://wywapi.weiyun001.com/api
```

当前已发现疑似货物追踪端点：

```text
/cargoTracking/recognitionCarrierNumber
/cargoTracking/recognizeExpressNo
/cargoTracking/recognitionCarrierByBLNo
/cargoTracking/recognitionIsContainerNo
/cargoTracking/getCarrierSearchLink
/cargoTracking/batchAddShippingSubscribes
/cargoTracking/getSubscribeUsableCountByType
/cargoTracking/getCarrierSource
```

### 4. 调用维运网识别/搜索链接接口

```bash
python -m crawler_lab.weiyun_api_probe --number CMAU4616180
python -m crawler_lab.weiyun_api_probe --number GVTU5148354 --carrier-code MSK
```

当前已验证：

- `recognitionIsContainerNo` 可匿名 GET，能判断柜号格式。
- `recognitionCarrierNumber` 可匿名 GET，可对部分柜号自动识别船司；例如 `CMAU4616180` 可识别为 CMA。
- `getCarrierSource` 可匿名 GET，能拿到 116 家船司及是否支持柜号。
- `getCarrierSearchLink` 可匿名 POST，传 `number + code` 可返回对应船司官网查询链接。

建议优先级：

1. 先让维运网用 `recognitionCarrierNumber` / `recognitionCarrierByBLNo` 自动识别船司。
2. 自动识别失败时，再使用 `getCarrierSource` 返回的船司映射表兜底。
3. 仍然失败时，再回退到我们自己的船司字段归一化。

示例：

```text
POST https://wywapi.weiyun001.com/api/cargoTracking/getCarrierSearchLink
{"number":"GVTU5148354","code":"MSK"}
```

返回：

```json
{
  "success": true,
  "message": "获取检索地址成功",
  "code": 200,
  "result": {
    "url": "https://www.maersk.com/tracking/GVTU5148354",
    "form": null
  }
}
```

目前该公开接口更像“识别船司/生成官网查询链接”，不是直接返回集装箱轨迹事件。

### 5. 获取维运网船司来源表

```bash
python -m crawler_lab.weiyun_carriers
```

该脚本会拉取：

```text
GET https://wywapi.weiyun001.com/api/cargoTracking/getCarrierSource
```

返回字段里比较关键的是：

- `code`：生成跳转链接时要传的船司代码，例如 Maersk 用 `MSK`。
- `wyCode`：维运网内部代码，例如 Maersk 为 `MAERSK`。
- `cnName`：中文船司名。
- `enName`：英文船司名。
- `isSupport`：是否支持该船司。
- `isCntrNoSupport`：是否支持柜号查询。
- `cnWebsite` / `enWebsite`：船司官网查询地址。

这一步适合作为后续批量任务的船司映射来源。

## 注意事项

- 当前实验不绕验证码、不破解加密参数、不绕过登录或访问控制。
- 当前脚本只做公开页面读取和静态 JS 分析。
- 如后续做网页自动化，优先用人工可见浏览器观察 Network，而不是高频批量请求。

## 6. 阳明海运公开查询接口（已验证）

维运返回的旧地址 `/en/esolution/cargo_tracking` 目前不会加载查询组件。阳明官网当前有效路径是：

```text
https://www.yangming.com/en/esolution/tracking/cargo_tracking?service=<柜号>
```

页面实际调用的公开 JSON 接口为：

```text
GET https://www.yangming.com/api/CargoTracking/GetTracking
```

请求参数：

```text
paramTrackNo=<柜号>
paramTrackPosition=SEARCH
paramRefNo=
```

可直接运行：

```bash
python -m trace_api_probe.providers.yang_ming_probe --container YMMU7349033
```

接口返回 `containerList[].ctStatusInfo`（站点展示事件）及
`containerList[].dcsaStatusInfo`（DCSA 标准事件）。本实验以低频单票验证为限；
如接口返回验证码、登录或访问限制，不绕过该限制。

## 7. SM Line 公开查询接口（已验证）

SM Line 需要先访问官网查询页建立本次查询的 `JSESSIONID`，再调用同域接口。
不需要登录、验证码或长期保存 Cookie。

```bash
python -m trace_api_probe.providers.sm_line_probe --container SMCU1311081
```

查询顺序如下：

```text
GET  CUP_HOM_3301.do?sessLocale=zh
POST CUP_HOM_3301GS.do f_cmd=122  -> 取得 bkgNo / copNo
POST CUP_HOM_3301GS.do f_cmd=123  -> 当前状态
POST CUP_HOM_3301GS.do f_cmd=124  -> 船期
POST CUP_HOM_3301GS.do f_cmd=125  -> 轨迹明细
```

脚本只在进程内保留会话 Cookie，并把官网原始 JSON 打印到终端。

## 8. 万海官网查询（已验证）

万海新站 `cec/#/cargotracking` 在当前环境会先经过前置校验，不适合直接抓取。当前可用路径是：

```text
https://www.wanhai.com/views/cargoTrack/CargoTrack.xhtml?file_num=65580
```

实现方式不是硬解校验，而是：

1. 用标准浏览器会话访问旧站并完成一次官网自己的会话预热
2. 同一会话再次进入后拿到 `tracking_query.xhtml`
3. 读取页面里的 `javax.faces.ViewState`
4. 带着官网发下来的会话 Cookie，向 `tracking_query.xhtml` 发送标准表单 POST

可直接运行：

```bash
E:\miniconda\envs\py312\python.exe -m trace_api_probe.providers.wan_hai_probe --container WHSU6376250
```

当前返回的是集装箱列表结果页，可提取字段包括：

- `Ctnr No.`
- `Ctnr Date`
- `Status Name`
- `Ctnr Depot Name`
- `Voyage`
- `Vessel Name`
- `More detail`

如果 `More detail` 中带出 Booking/B/L 编号，脚本会继续使用官网 `Book No. / BL no.` 查询模式拉取一层摘要。当前样本 `WHSU6376250` 会继续查到：

```text
BL no.      026G533793
Oboard Date 2026/06/21
Voyage      E016
Vessel Name WAN HAI A03
```

`Booking Data / B/L Data` 弹窗 redirect 页当前只稳定返回 `loading...` 壳页，暂不作为程序数据源。
