# StockData - 统一股票数据获取类

## 概述

StockData是一个基于akshare的统一股票数据获取类，整合了所有常用的金融数据API，提供简洁易用的接口。

**文件位置**: `tools_agent/stock_data.py`

## 特性

- 🎯 **统一接口**: 通过`stock_data.方法名()`统一获取各种金融数据
- 📊 **功能模块化**: 按业务功能分组，包含8大模块
- 📝 **完整日志**: 所有操作都有详细的日志记录
- 🛡️ **异常处理**: 完善的错误处理和异常捕获
- 📖 **详细文档**: 每个方法都有完整的参数说明

## 快速开始

### 1. 安装依赖

```bash
pip install akshare pandas
```

### 2. 基本使用

```python
from tools_agent.stock_data import StockData

# 创建实例
stock_data = StockData()

# 获取平安银行基本信息
info = stock_data.get_stock_info_em("000001")
print(info)

# 获取历史行情
hist = stock_data.get_stock_hist("000001", start_date="20250101", end_date="20250128")
print(hist.head())
```

## 功能模块

### 1. 市场总览模块

| 方法名 | 功能 | 参数 |
|--------|------|------|
| `get_sse_summary()` | 获取上交所总览 | 无 |
| `get_szse_summary()` | 获取深交所总览 | 无 |
| `get_szse_sector_summary()` | 获取深交所行业成交 | symbol, date |

**使用示例**:
```python
# 获取市场总览
sse_data = stock_data.get_sse_summary()
szse_data = stock_data.get_szse_summary()
```

### 2. 个股信息模块

| 方法名 | 功能 | 参数 |
|--------|------|------|
| `get_stock_info_em(symbol)` | 获取个股信息-东财 | 股票代码 |
| `get_stock_info_xq(symbol)` | 获取个股信息-雪球 | 股票代码 |
| `get_stock_profile_cninfo(symbol)` | 获取公司概况-巨潮 | 股票代码 |

**使用示例**:
```python
# 获取个股基本信息
info = stock_data.get_stock_info_em("000001")
profile = stock_data.get_stock_profile_cninfo("000001")
```

### 3. 股价行情模块

| 方法名 | 功能 | 参数 |
|--------|------|------|
| `get_stock_hist()` | 获取历史行情 | symbol, period, start_date, end_date, adjust |

**使用示例**:
```python
# 获取历史行情
hist = stock_data.get_stock_hist(
    symbol="000001",
    start_date="20250101",
    end_date="20250128",
    adjust="qfq"  # 前复权
)
```

### 4. 公司业务模块

| 方法名 | 功能 | 参数 |
|--------|------|------|
| `get_main_business_ths(symbol)` | 获取主营介绍-同花顺 | 股票代码 |
| `get_main_composition_em(symbol)` | 获取主营构成-东财 | 股票代码 |

### 5. 机构调研模块

| 方法名 | 功能 | 参数 |
|--------|------|------|
| `get_institutional_research(date)` | 获取机构调研统计 | 日期 |
| `get_institutional_holding(symbol)` | 获取机构持股 | 期间代码 |

### 6. 质押信息模块

| 方法名 | 功能 | 参数 |
|--------|------|------|
| `get_pledge_ratio(date)` | 获取质押比例 | 日期 |

### 7. 新闻资讯模块

| 方法名 | 功能 | 参数 |
|--------|------|------|
| `get_stock_news(symbol)` | 获取个股新闻 | 股票代码 |
| `get_financial_news()` | 获取财经新闻 | 无 |
| `get_morning_news()` | 获取财经早餐 | 无 |

**使用示例**:
```python
# 获取新闻资讯
news = stock_data.get_stock_news("000001")
financial_news = stock_data.get_financial_news()
```

### 8. 财务报表模块

| 方法名 | 功能 | 参数 |
|--------|------|------|
| `get_performance_report(date)` | 获取业绩报表 | 报告期 |
| `get_performance_express(date)` | 获取业绩快报 | 报告期 |
| `get_balance_sheet(date)` | 获取资产负债表 | 报告期 |
| `get_income_statement(date)` | 获取利润表 | 报告期 |
| `get_cash_flow(date)` | 获取现金流量表 | 报告期 |
| `get_financial_debt_ths()` | 获取财务报表-同花顺 | symbol, indicator |
| `get_financial_abstract_ths()` | 获取关键指标-同花顺 | symbol, indicator |
| `get_financial_analysis_indicator()` | 获取财务指标分析 | symbol, start_year |

**使用示例**:
```python
# 获取财务数据
performance = stock_data.get_performance_report("20240930")
balance_sheet = stock_data.get_balance_sheet("20240930")
financial_indicator = stock_data.get_financial_analysis_indicator("000001", "2023")
```

### 9. 股东信息模块

| 方法名 | 功能 | 参数 |
|--------|------|------|
| `get_top_10_free_holders()` | 获取十大流通股东 | symbol, date |
| `get_top_10_holders()` | 获取十大股东 | symbol, date |
| `get_shareholder_count(symbol)` | 获取股东户数 | 报告期 |

### 10. 行业板块模块

| 方法名 | 功能 | 参数 |
|--------|------|------|
| `get_sector_spot(indicator)` | 获取板块行情 | 板块类型 |

### 11. 股票列表模块

| 方法名 | 功能 | 参数 |
|--------|------|------|
| `get_a_stock_list()` | 获取A股列表 | 无 |
| `get_sh_stock_list(symbol)` | 获取上证列表 | 板块类型 |
| `get_sz_stock_list(symbol)` | 获取深证列表 | 板块类型 |

## 高级用法

### 1. 综合分析示例

```python
def analyze_stock(stock_code):
    stock_data = StockData()
    
    # 获取基本信息
    basic_info = stock_data.get_stock_info_em(stock_code)
    
    # 获取历史行情
    hist_data = stock_data.get_stock_hist(stock_code, start_date="20250101")
    
    # 获取财务指标
    financial_data = stock_data.get_financial_analysis_indicator(stock_code, "2023")
    
    # 获取最新新闻
    news_data = stock_data.get_stock_news(stock_code)
    
    return {
        'basic_info': basic_info,
        'price_data': hist_data,
        'financial_data': financial_data,
        'news_data': news_data
    }

# 使用
result = analyze_stock("000001")
```

### 2. 批量处理示例

```python
def batch_analysis(stock_codes):
    stock_data = StockData()
    results = []
    
    for code in stock_codes:
        try:
            info = stock_data.get_stock_info_em(code)
            hist = stock_data.get_stock_hist(code, start_date="20250125")
            
            results.append({
                'code': code,
                'name': info.iloc[0]['value'] if not info.empty else '未知',
                'latest_price': hist.iloc[-1]['收盘'] if not hist.empty else 0
            })
        except Exception as e:
            print(f"处理{code}失败: {e}")
            continue
    
    return pd.DataFrame(results)

# 使用
codes = ["000001", "000002", "600036"]
batch_result = batch_analysis(codes)
```

## 日期格式说明

- **日期格式**: YYYYMMDD (如: "20250128")
- **年月格式**: YYYYMM (如: "202501")
- **年份格式**: YYYY (如: "2025")

## 常见股票代码格式

- **A股代码**: "000001", "600036" 等
- **带前缀**: "SH600036", "SZ000001" 等
- **小写前缀**: "sh600036", "sz000001" 等

## 错误处理

所有方法都包含完整的异常处理：

```python
try:
    data = stock_data.get_stock_info_em("000001")
    print(data)
except Exception as e:
    print(f"获取数据失败: {e}")
```

## 日志功能

StockData会自动记录所有操作日志：

```
2025-01-28 10:30:15 - StockData - INFO - StockData类初始化完成
2025-01-28 10:30:16 - StockData - INFO - 执行操作: 获取个股信息(东财), 参数: symbol=000001
```

## 运行示例

查看完整的使用示例：

```bash
python tools_agent/stock_data_example.py
```

## 注意事项

1. **网络连接**: 需要稳定的网络连接访问数据源
2. **数据延迟**: 部分数据可能有延迟，请以官方数据为准
3. **请求频率**: 避免过于频繁的请求，以免被限制访问
4. **数据准确性**: 本工具仅供参考，投资决策请以官方数据为准

## 更新日志

- **v1.0.0** (2025-01-28): 初始版本，整合所有akshare API 