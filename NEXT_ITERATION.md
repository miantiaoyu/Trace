# 下一迭代计划

## 迭代目标

在保持低频、只读查询的前提下，将阳明、SM Line 的 JSON 查询和 COSCO、ONE 的 DOM 查询抽象为统一 Provider；继续验证 Maersk、MSC 的官方路径，并以本地船司映射作为微运跳转兜底。

基于维运网自动识别结果、船司来源表和官网跳转链接，选择 1-2 家船司继续验证官网页面自动化或官网背后接口抓取。

## 需求范围

- 优先用维运网 `recognitionCarrierNumber` / `recognitionCarrierByBLNo` 自动识别船司。
- 自动识别失败时，再用维运网 `getCarrierSource` 建立船司代码映射。
- 用维运网 `getCarrierSearchLink` 为真实柜号生成船司官网查询链接。
- 先选 Maersk 或 CMA CGM 做官网页面/接口二次探测。
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
4. 打开 Maersk 或 CMA CGM 官网查询链接，观察 Network。
5. 优先复现官网背后的 JSON 请求；如无法复现，再设计 Playwright 自动化脚本。

## 需要确认的问题

- 先选哪家船司做官网自动化试点？
- 是否允许使用可见浏览器窗口进行人工辅助调试？
- 后续是否需要把维运网船司映射与只读库船司字段自动匹配？
