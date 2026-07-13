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

## 已验证事实

- ONE: `trakNoParam=<柜号>` 可直接打开 ONE 官方查询页并返回主表、船期和事件表。
- COSCO: `trackingType=containerNumber&number=<柜号>` 可直接打开官方查询页并返回事件表。
- SM Line: 必须先建立临时 `JSESSIONID`，且柜号首查 `f_cmd=122`；后续状态、船期、明细依次使用 123、124、125。
- Yang Ming: 公开 JSON 接口可直接按柜号调用；微运给出的旧页面路径需要修正。
- Evergreen: 官方中国站的公开页面可直接 `POST` 到 `TDB1_CargoTracking.do`。柜号查询参数为 `TYPE=CNTR`、`SEL=s_cntr`、`CNTR=<柜号>`、`NO=<柜号>`；页面返回柜型、最新动态和地点，无需验证码或登录。
- Maersk: 直接重放追踪接口会返回 401，但官网中国站 `tracking/<柜号>` 可在全新浏览器会话中返回页面自身请求的完整 JSON。应由 Playwright 等待 `/synergy/tracking/` 的 200 响应并读取响应体，不提取或伪造凭证。

## 访问限制分类

- 已确认可自动化：Yang Ming、SM Line、COSCO、ONE、Evergreen、Maersk。
- 需要人工验证码，当前不绕过：CMA CGM（DataDome）、OOCL（Cloudflare Turnstile）、ZIM 中国站（Cloudflare）、TS Lines（查询表单含验证码）、Hapag-Lloyd（Cloudflare）。
- 访问前置校验或 CDN 拒绝：Wan Hai（Incapsula/HTTP 412）、KMTC（Akamai HTTP 403）、MSC（Akamai HTTP 403）。
- 临时服务不可用：SeaLead 的表单可提交，但官网返回追踪页维护通知。
- 待在网络条件变化后复查：HMM。官方页面在当前环境发生 HTTP/2 协议错误或超时，尚不能据此认定为该船司不支持自动化。
- APL 目前入口返回 HTTP 403；其与 CMA CGM 同属集团，后续应优先通过 CMA CGM 正式 API 或人工可用会话复查，不把单次 403 解释为业务不支持。
