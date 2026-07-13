# 下一迭代计划

## 迭代目标

在保持低频、只读查询的前提下，将阳明、SM Line、Evergreen、Maersk、MSC、Wan Hai 的直接查询和 COSCO、ONE 的 DOM 查询抽象为统一 Provider；继续在不同网络条件下复查 HMM，并对需要人工验证码或临时维护的船司保留明确的降级状态。

基于维运网自动识别结果、船司来源表和官网跳转链接，选择 1-2 家船司继续验证官网页面自动化或官网背后接口抓取。

## 需求范围

- 优先用维运网 `recognitionCarrierNumber` / `recognitionCarrierByBLNo` 自动识别船司。
- 自动识别失败时，再用维运网 `getCarrierSource` 建立船司代码映射。
- 用维运网 `getCarrierSearchLink` 为真实柜号生成船司官网查询链接。
- 将 Evergreen 探针纳入统一 Provider 的输入和输出模型。
- 将 Maersk 的浏览器响应捕获纳入统一 Provider，并建立合理的超时和低频限制。
- 将 MSC 的表单提交流程和 `TrackingInfo` 响应捕获纳入统一 Provider，并为 Cookie 弹窗和按钮选择器建立容错。
- 将 Wan Hai 的“会话预热 + ViewState 表单 POST + Booking 摘要二次查询”流程纳入统一 Provider；Booking/BL 弹窗 redirect 页暂不作为稳定数据源。
- 在不绕过人机验证的前提下，定义 CMA CGM、OOCL、ZIM、TS Lines 的人工辅助降级结果。
- 在不同网络条件下复查 HMM 的 HTTP/2 兼容性。
- 判断目标船司官网是否能通过纯 HTTP 调用背后 JSON 接口。
- 如果纯 HTTP 不可行，再尝试 Playwright 网页自动化。

## 不在本轮范围

- 不写公司数据库。
- 不保存本地 JSON 文件。
- 不绕验证码、不破解加密参数、不绕过登录或访问控制。
- 不做可视化界面。
- 不做高频批量请求。

## 验收标准

- 能用真实柜号从维运网拿到对应船司官网跳转链接。
- 能明确判断目标船司官网是否存在可直接调用的公开 JSON 请求。
- 如果必须使用浏览器自动化，能记录触发查询所需的输入、按钮和结果区域。
- `prod-db.yml` 不被修改、不被提交。
- 公司数据库只发生读取，不发生写入。

## 建议实现步骤

1. 运行 `python -m crawler_lab.weiyun_api_probe --number CMAU4616180`，验证自动识别优先路径。
2. 自动识别失败时，运行 `python -m crawler_lab.weiyun_carriers`，确认维运网船司代码。
3. 使用 `--carrier-code` 为真实柜号生成官网链接。
4. 优先将 Evergreen 的 HTTP 页面查询和现有 JSON/DOM 查询统一为 Provider。
5. 对 HMM 复测网络兼容性；对需人工验证码的页面只记录降级状态，不尝试绕过。

## 需要确认的问题

- 先选哪家船司做官网自动化试点？
- 是否允许使用可见浏览器窗口进行人工辅助调试？
- 后续是否需要把维运网船司映射与只读库船司字段自动匹配？
