# 用户手册

## 项目简介

Trace 第一版是一个船司 API 探测工具。它从公司只读库读取船司和柜号，然后调用试点船司的 Track & Trace API，并在控制台打印原始返回。

当前试点船司：

- Maersk
- CMA CGM
- MSC

## 安装/准备

请在本机 Conda `py312` 环境中安装依赖：

```bash
pip install -r requirements.txt
```

根目录需要有本地配置文件：

```text
prod-db.yml
```

该文件只用于读取公司只读库连接信息，不应修改或提交。

## 启动/使用

从只读库取最近的 Maersk 柜号并调用 API：

```bash
python -m trace_api_probe --carrier MAERSK
```

从只读库取最近的 CMA CGM 柜号并调用 API：

```bash
python -m trace_api_probe --carrier CMA_CGM
```

从只读库取最近的 MSC 柜号并调用 API：

```bash
python -m trace_api_probe --carrier MSC
```

手动指定柜号，不读取数据库样本：

```bash
python -m trace_api_probe --carrier MAERSK --container MSKU1234567
```

## API 凭证

未配置 API 凭证时，程序会在调用 API 前停止并提示缺少的环境变量。

支持的环境变量：

```text
MAERSK_API_KEY
MAERSK_CLIENT_ID
MAERSK_BEARER_TOKEN
MAERSK_TRACK_TRACE_URL
CMA_CGM_API_KEY
CMA_CGM_BEARER_TOKEN
CMA_CGM_TRACK_TRACE_URL
MSC_API_KEY
MSC_BEARER_TOKEN
MSC_TRACK_TRACE_URL
```

## 常见问题

### 会写公司数据库吗？

不会。第一版只读取数据库，不写入任何表。

### 会爬船司网页吗？

不会。没有 API 凭证时程序会直接停止。

### 会保存 API 返回文件吗？

不会。第一版只在控制台打印原始 JSON。

### 没有 API 凭证能看到真实返回吗？

不能。没有凭证时只能验证读库、取柜号和缺凭证提示。

## 爬虫实验

维运网页面探测：

```bash
python crawler_lab/http_probe.py
```

抽取维运网前端接口线索：

```bash
python -m crawler_lab.endpoint_probe
```

调用维运网识别/跳转链接接口：

```bash
python -m crawler_lab.weiyun_api_probe --number CMAU4616180
python -m crawler_lab.weiyun_api_probe --number GVTU5148354 --carrier-code MSK
```

查看维运网船司来源表：

```bash
python -m crawler_lab.weiyun_carriers
```

当前维运网实验结论：它可以识别柜号格式、对部分柜号自动识别船司、返回船司来源表，并生成船司官网查询链接；它不是直接返回轨迹事件的数据源。使用优先级是自动识别优先，船司映射表兜底。

### 长荣官网查询

长荣支持直接按柜号查询，无需 API 凭证：

```bash
E:\miniconda\envs\py312\python.exe -m crawler_lab.evergreen_probe --container EGHU9204414
```

命令会打印官网结果表的表头和数据行。当前验证返回柜型、最新动态和地点。

### 马士基官网查询

马士基无需 API 凭证，可通过官网追踪页读取该页面返回的原始 JSON：

```bash
E:\miniconda\envs\py312\python.exe -m crawler_lab.maersk_probe --container GVTU5148354
```

输出包含始发地、目的地、集装箱事件、船名航次、状态和 ETA。该命令需要 Playwright Chromium，且不会保存 Cookie 或结果文件。

## 注意事项

- 不要提交 `prod-db.yml`。
- 不要把 API 凭证写入 `prod-db.yml`。
- 船司实际开通后的 API 地址或认证头可能不同，可通过环境变量覆盖默认地址。
