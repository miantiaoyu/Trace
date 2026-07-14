# 项目经验

本文件只记录仍然有效的工程经验。每次发现新的船司路径或推翻既有判断时必须更新。

## 查询路径

- 不要因为单一字段（例如 SO/Booking）查询失败就判断船司不可用。
  先验证柜号、B/L、Booking、官网 URL 参数和公开页面组件等所有可用路径。
- 官方直连优先。微运只用于发现船司代码、官方跳转 URL 或识别失败兜底；一旦确认官方 URL 参数，应在项目中直接构造该 URL。
- 一个页面查询成功不等于 JSON 接口可直接复现。页面 DOM Provider 仍是可接受的确定性实现，不使用视觉识别或大模型。

## DOM Provider 规则

- 使用稳定 URL 参数进入查询页，不通过坐标点击或截图 OCR 获取数据。
- 结果必须同时通过柜号回显、最低数据行数和关键表头校验。
- 选择器优先使用语义和表头契约；页面结构变化要明确报错，禁止静默返回空数据。
- 超时只允许有限重试；验证码、登录、加密协议和访问控制均不绕过。
- 不同船司的原始格式不能硬拼。统一输出应采用“固定摘要 + `raw` 原始返回”：摘要中没有明确来源的字段必须为 `null`，并用 `coverage` 标注字段可用性。
- 批量查询的超时必须在独立 Provider 子进程中执行并可终止；线程超时无法可靠清理浏览器子进程，不适合作为官网查询的硬超时方案。
- 官网返回的事件数组不能直接等同于当前位置。`ACTUAL` 表示已确认发生，`EXPECTED` 表示计划或预测；当前位置应取最新实际事件，下一节点应取之后最早的预计事件。马士基使用 `event_time_type`，SM Line 使用 `actTpCd=A/E`，MSC 可从 `Estimated` 事件描述识别预计节点。
- 健壮性必须分层：官网查询失败返回 `query_failed`，原始数据成功但归一化失败返回 `partial_success`，路由内部未预期异常返回 `internal_error`。三种情况都只影响单柜，不中断批次。
- 顶层船名航次不能取原始数组第一条；优先使用当前实际事件的船舶，其次使用下一预计事件的船舶，再使用来源提供的计划航段摘要。

## 已验证事实

- ONE: `trakNoParam=<柜号>` 可直接打开 ONE 官方查询页并返回主表、船期和事件表。
- COSCO: `trackingType=containerNumber&number=<柜号>` 可直接打开官方查询页并返回事件表。
- SM Line: 必须先建立临时 `JSESSIONID`，且柜号首查 `f_cmd=122`；后续状态、船期、明细依次使用 123、124、125。
- Yang Ming: 公开 JSON 接口可直接按柜号调用；微运给出的旧页面路径需要修正。
- Evergreen: 官方中国站的公开页面可直接 `POST` 到 `TDB1_CargoTracking.do`。柜号查询参数为 `TYPE=CNTR`、`SEL=s_cntr`、`CNTR=<柜号>`、`NO=<柜号>`；页面返回柜型、最新动态和地点，无需验证码或登录。
- Maersk: 直接重放追踪接口会返回 401，但官网中国站 `tracking/<柜号>` 可在全新浏览器会话中返回页面自身请求的完整 JSON。应由 Playwright 等待 `/synergy/tracking/` 的 200 响应并读取响应体，不提取或伪造凭证。
- MSC: 直接访问部分入口时可能遇到 Akamai 403，但标准官网查询页 `https://www.msc.com/en/track-a-shipment?agencyPath=hkg` 可通过普通浏览器流程完成查询。先接受 Cookie，再填写 `#trackingNumber`，点击 `form.js-form button.msc-search-autocomplete__search`，随后等待 `/api/feature/tools/TrackingInfo` 的 `POST 200` 响应并读取原始 JSON；不复用外部 Cookie，不补伪造请求头。
- HMM: 无头 Chromium/Edge 会遇到 Akamai 403 或 HTTP/2 协议错误，但有界 Chromium 可直接进入 `https://www.hmm21.com/e-service/general/trackNTrace/TrackNTrace.do`。填写 `input[name="srchCntrNo1"]` 后点击 `button[onclick="search()"]`，页面会带着自己的 CSRF token 向 `selectTrackNTrace.do` 提交 POST 并返回追踪 HTML。服务器应使用有界 Chromium；Linux 通过 Xvfb 提供显示，不绕过官网校验。只读库中的 HMM 名称可能为 `HMM` 加乱码后缀，SQL 需要 `HMM%` 前缀兜底。
- HMM 的真实样本页面包含 8 至 9 张表，单据状态表会随业务状态出现或缺失，不能按表格序号解析。稳定区块应按表头识别：航线表包含 `Origin/Destination`，柜摘要包含 `Container No./Movement`，航段表包含 `Vessel / Voyage`，事件表包含 `Date/Time/Location/Status Description`。事件表的 `Mode` 在陆运时是 `Truck`，在海运时实际是“船名 + 航次”，需要拆分后再映射到统一字段。
- Wan Hai: 新站 `https://cn.wanhai.com/cec/#/cargotracking` 在当前环境会先落到前置校验页，普通 HTTP 和直接首跳浏览器抓取都不稳定。可行路径是访问旧站 `https://www.wanhai.com/views/cargoTrack/CargoTrack.xhtml?file_num=65580`，在同一标准浏览器会话中预热两次后进入 `tracking_query.xhtml`，再带着官网发下来的会话 Cookie 与 `javax.faces.ViewState` 向 `tracking_query.xhtml` 发送标准表单 POST。返回页可稳定提取 `Ctnr No.`、`Status Name`、`Ctnr Depot Name`、`Voyage`、`Vessel Name` 等字段。列表页 `More detail` 会带出 Booking/B/L 编号，例如 `026G533793`；继续用 `cargoType=2` 的 `Book No. / BL no.` 模式查询，可取得 `BL no.`、`Oboard Date`、`Voyage`、`Vessel Name` 摘要。`Booking Data / B/L Data` 的弹窗 redirect 页当前只稳定到 `loading...` 壳页，不作为项目数据源。

## 访问限制分类

- 已确认可自动化：Yang Ming、SM Line、COSCO、ONE、Evergreen、Maersk、MSC、Wan Hai、HMM（有界浏览器）。
- 需要人工验证码，当前不绕过：CMA CGM（DataDome）、OOCL（Cloudflare Turnstile）、ZIM 中国站（Cloudflare）、TS Lines（查询表单含验证码）、Hapag-Lloyd（Cloudflare）。
- 访问前置校验或 CDN 拒绝：KMTC（Akamai HTTP 403）。
- 临时服务不可用：SeaLead 的表单可提交，但官网返回追踪页维护通知。
- APL 目前入口返回 HTTP 403。未验证到稳定的官网查询路线前，统一入口保持 `route_unavailable`；不接入 API 凭证、人工会话或验证码处理作为替代方案。
