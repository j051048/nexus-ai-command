# 国内支付集成方案（微信支付 + 支付宝）

> Item 55: 与已实现的 Stripe 网关统一的国内支付集成设计文档

## 1. 概述

本文档描述如何在 Nexus AI Command 平台中集成微信支付和支付宝，与已有的 Stripe 支付网关形成统一的多渠道支付体系。

### 1.1 目标

- 统一支付接口：前端通过同一套 API 发起支付，后端自动路由到对应渠道
- 支持场景：PC 端扫码支付、H5 支付、JSAPI 支付（微信内）
- 统一回调处理：所有渠道的 Webhook 回调走统一处理流程
- 自动对账：每日自动拉取各渠道账单进行核对

### 1.2 当前状态

| 渠道 | 状态 | 路由 |
|------|------|------|
| Stripe | 已实现 | `/api/payments/stripe/*`, `/api/stripe-webhooks` |
| 微信支付 | 待实现 | 本文档设计 |
| 支付宝 | 待实现 | 本文档设计 |

---

## 2. 统一支付接口设计（PaymentGatewayInterface）

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum


class PaymentChannel(StrEnum):
    STRIPE = "stripe"
    WECHAT = "wechat"
    ALIPAY = "alipay"


class PaymentMethod(StrEnum):
    # Stripe
    STRIPE_CARD = "stripe_card"
    STRIPE_LINK = "stripe_link"
    # 微信支付
    WECHAT_NATIVE = "wechat_native"       # PC 扫码
    WECHAT_JSAPI = "wechat_jsapi"         # 微信内 H5
    WECHAT_H5 = "wechat_h5"              # 非微信 H5
    # 支付宝
    ALIPAY_PC = "alipay_pc"              # PC 网页支付
    ALIPAY_FACE_TO_FACE = "alipay_f2f"   # 当面付（扫码）
    ALIPAY_WAP = "alipay_wap"            # 手机网页支付


@dataclass
class PaymentRequest:
    """统一支付请求"""
    order_id: str
    amount_cents: int          # 金额（分）
    currency: str = "CNY"      # 币种
    channel: PaymentChannel = PaymentChannel.WECHAT
    method: PaymentMethod = PaymentMethod.WECHAT_NATIVE
    subject: str = ""          # 商品描述
    user_id: str = ""
    org_id: str = ""
    metadata: dict = None      # 附加信息
    notify_url: str = ""       # 异步回调地址
    return_url: str = ""       # 前端跳转地址


@dataclass
class PaymentResult:
    """统一支付结果"""
    success: bool
    order_id: str
    channel: PaymentChannel
    channel_order_id: str = ""  # 渠道方订单号
    qr_code_url: str = ""       # 二维码链接（扫码支付）
    pay_url: str = ""           # 支付跳转链接
    prepay_id: str = ""         # 微信 prepay_id（JSAPI 用）
    error_message: str = ""


class PaymentGatewayInterface(ABC):
    """支付网关统一接口"""

    @abstractmethod
    async def create_payment(self, request: PaymentRequest) -> PaymentResult:
        """创建支付订单"""
        ...

    @abstractmethod
    async def query_payment(self, order_id: str) -> dict:
        """查询支付状态"""
        ...

    @abstractmethod
    async def refund(self, order_id: str, amount_cents: int, reason: str = "") -> dict:
        """发起退款"""
        ...

    @abstractmethod
    async def verify_webhook(self, headers: dict, body: bytes) -> dict:
        """验证并解析 Webhook 回调"""
        ...

    @abstractmethod
    async def download_bill(self, bill_date: str) -> list[dict]:
        """下载对账单"""
        ...
```

### 2.1 网关路由逻辑

```python
class PaymentGatewayRouter:
    """根据 channel 自动路由到对应网关实现"""

    def __init__(self):
        self._gateways: dict[PaymentChannel, PaymentGatewayInterface] = {}

    def register(self, channel: PaymentChannel, gateway: PaymentGatewayInterface):
        self._gateways[channel] = gateway

    def get_gateway(self, channel: PaymentChannel) -> PaymentGatewayInterface:
        gw = self._gateways.get(channel)
        if not gw:
            raise ValueError(f"Payment channel not configured: {channel}")
        return gw

# 初始化
gateway_router = PaymentGatewayRouter()
# gateway_router.register(PaymentChannel.STRIPE, StripeGateway())
# gateway_router.register(PaymentChannel.WECHAT, WechatPayGateway())
# gateway_router.register(PaymentChannel.ALIPAY, AlipayGateway())
```

---

## 3. 微信支付集成

### 3.1 接入准备

| 项目 | 说明 |
|------|------|
| 商户号 (mch_id) | 微信支付商户平台申请 |
| AppID | 微信公众号/小程序的 AppID |
| API v3 密钥 | 商户平台设置 |
| 商户 API 证书 | 用于签名验证 (.pem) |
| 推荐 SDK | `wechatpayv3` (Python) |

### 3.2 Native 支付流程（PC 扫码）

```
用户选择微信支付 → 后端创建预付单 → 返回 code_url
    → 前端生成二维码 → 用户扫码支付
    → 微信回调 notify_url → 后端验签更新订单状态
```

**关键 API：**
- `POST /v3/pay/transactions/native` — 创建预付单，返回 `code_url`
- 回调：微信 POST 到 `notify_url`，包含加密的支付结果

### 3.3 JSAPI 支付流程（微信内 H5）

```
用户在微信内打开 → 后端获取 openid（OAuth2）
    → 创建预付单获取 prepay_id → 返回前端
    → 前端调用 wx.chooseWXPay → 用户确认支付
    → 微信回调 notify_url
```

**关键 API：**
- `POST /v3/pay/transactions/jsapi` — 需要 `payer.openid`
- 前端需引入微信 JS-SDK 并调用 `wx.chooseWXPay`

### 3.4 回调验签

```python
async def verify_wechat_webhook(headers: dict, body: bytes) -> dict:
    """
    微信支付 v3 回调验签流程：
    1. 从 headers 获取 Wechatpay-Serial, Wechatpay-Signature, Wechatpay-Timestamp, Wechatpay-Nonce
    2. 构造验签串: timestamp + "\n" + nonce + "\n" + body + "\n"
    3. 使用微信平台证书公钥 RSA-SHA256 验签
    4. 解密 resource 字段（AES-256-GCM）获取支付结果
    """
    ...
```

---

## 4. 支付宝集成

### 4.1 接入准备

| 项目 | 说明 |
|------|------|
| AppID | 支付宝开放平台创建的应用 |
| 应用私钥 | RSA2 密钥对中的私钥 |
| 支付宝公钥 | 用于验签 |
| 推荐 SDK | `alipay-sdk-python` 或自行封装 |

### 4.2 当面付流程（扫码支付）

```
用户选择支付宝 → 后端调用 alipay.trade.precreate
    → 返回 qr_code → 前端生成二维码
    → 用户扫码支付 → 支付宝回调 notify_url
    → 后端验签更新订单
```

**关键 API：**
- `alipay.trade.precreate` — 预创建订单，返回二维码链接

### 4.3 PC 网页支付流程

```
用户选择支付宝 → 后端调用 alipay.trade.page.pay
    → 返回支付表单 HTML → 前端重定向到支付宝
    → 用户在支付宝页面完成支付
    → 支付宝同步跳转 return_url + 异步回调 notify_url
```

**关键 API：**
- `alipay.trade.page.pay` — 返回 form HTML（自动提交到支付宝）

### 4.4 回调验签

```python
async def verify_alipay_webhook(params: dict) -> dict:
    """
    支付宝回调验签流程：
    1. 从回调参数中提取 sign 和 sign_type
    2. 将其余参数按 key 字母序排列，拼接为待签名串
    3. 使用支付宝公钥 RSA2-SHA256 验签
    4. 验签通过后返回 trade_status 等字段
    """
    ...
```

---

## 5. 数据库表设计

### 5.1 payment_transactions（支付交易表）

```sql
CREATE TABLE IF NOT EXISTS payment_transactions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id uuid NOT NULL REFERENCES organizations(id),
    user_id uuid NOT NULL,
    order_id text UNIQUE NOT NULL,           -- 平台内部订单号
    channel text NOT NULL,                    -- stripe / wechat / alipay
    method text NOT NULL,                     -- wechat_native / alipay_pc / ...
    amount_cents integer NOT NULL,            -- 金额（分）
    currency text NOT NULL DEFAULT 'CNY',
    subject text DEFAULT '',                  -- 商品描述
    status text NOT NULL DEFAULT 'pending',   -- pending / paid / refunded / failed / closed
    channel_order_id text,                    -- 渠道方订单号
    channel_response jsonb DEFAULT '{}',      -- 渠道原始响应
    paid_at timestamptz,
    refund_amount_cents integer DEFAULT 0,
    refunded_at timestamptz,
    metadata jsonb DEFAULT '{}',
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

-- 索引
CREATE INDEX idx_payment_transactions_org ON payment_transactions(org_id);
CREATE INDEX idx_payment_transactions_user ON payment_transactions(user_id);
CREATE INDEX idx_payment_transactions_status ON payment_transactions(status);
CREATE INDEX idx_payment_transactions_channel ON payment_transactions(channel);
CREATE INDEX idx_payment_transactions_created ON payment_transactions(created_at DESC);

-- RLS
ALTER TABLE payment_transactions ENABLE ROW LEVEL SECURITY;
CREATE POLICY payment_transactions_org_isolation ON payment_transactions
    USING (org_id = current_setting('app.current_org_id', true)::uuid);
```

### 5.2 payment_channels（支付渠道配置表）

```sql
CREATE TABLE IF NOT EXISTS payment_channels (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id uuid NOT NULL REFERENCES organizations(id),
    channel text NOT NULL,                    -- stripe / wechat / alipay
    display_name text NOT NULL,
    enabled boolean DEFAULT false,
    config_encrypted jsonb DEFAULT '{}',      -- 加密存储的密钥配置
    supported_methods text[] DEFAULT '{}',    -- 支持的支付方式
    notify_url text,                          -- 回调地址
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),
    UNIQUE(org_id, channel)
);

ALTER TABLE payment_channels ENABLE ROW LEVEL SECURITY;
CREATE POLICY payment_channels_org_isolation ON payment_channels
    USING (org_id = current_setting('app.current_org_id', true)::uuid);
```

---

## 6. Webhook 回调统一处理方案

### 6.1 统一回调入口

```
POST /api/payments/webhook/wechat   → WechatPayGateway.verify_webhook()
POST /api/payments/webhook/alipay   → AlipayGateway.verify_webhook()
POST /api/stripe-webhooks           → StripeGateway.verify_webhook()  (已实现)
```

### 6.2 回调处理流程

```
1. 接收回调请求
2. 验签（各渠道独立验签逻辑）
3. 幂等性检查（order_id + channel_order_id 去重）
4. 更新 payment_transactions 状态
5. 触发业务事件（EventBus）：
   - payment.success → 开通服务/发货/更新订阅
   - payment.refund  → 关闭服务/库存回滚
6. 返回渠道要求的响应格式
   - 微信: {"code": "SUCCESS", "message": "OK"}
   - 支付宝: 返回纯文本 "success"
```

### 6.3 幂等性保障

- 每笔回调以 `channel + channel_order_id` 为幂等键
- 使用 Redis `SET NX EX 300` 防止并发重复处理
- 数据库层面 `order_id UNIQUE` 约束兜底

---

## 7. 对账流程设计

### 7.1 每日自动对账

```
每日 T+1 凌晨 02:00 (Celery Beat / Scheduled Task):

1. 拉取前一日各渠道账单：
   - 微信: POST /v3/bill/tradebill (下载交易账单)
   - 支付宝: alipay.data.dataservice.bill.downloadurl.query
   - Stripe: stripe.BalanceTransaction.list(created={gte, lt})

2. 与本地 payment_transactions 逐笔比对：
   - 金额一致性检查
   - 状态一致性检查
   - 发现差异记入 reconciliation_log 表

3. 差异处理：
   - 本地有、渠道无 → 标记为"待核实"
   - 渠道有、本地无 → 标记为"遗漏订单"
   - 金额不一致 → 标记为"金额差异"

4. 生成对账报告 → 发送通知给财务管理员
```

### 7.2 reconciliation_log 表

```sql
CREATE TABLE IF NOT EXISTS reconciliation_log (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id uuid NOT NULL,
    bill_date date NOT NULL,
    channel text NOT NULL,
    total_orders integer DEFAULT 0,
    matched_orders integer DEFAULT 0,
    discrepancy_count integer DEFAULT 0,
    discrepancies jsonb DEFAULT '[]',
    status text DEFAULT 'pending',  -- pending / reviewed / resolved
    reviewed_by uuid,
    created_at timestamptz DEFAULT now()
);
```

---

## 8. 安全考量

1. **密钥存储**: 所有渠道密钥通过 `config_encrypted` 字段加密存储，运行时解密
2. **回调验签**: 严格验证每一笔回调的签名，拒绝伪造请求
3. **HTTPS Only**: 所有回调地址必须使用 HTTPS
4. **日志脱敏**: 支付相关日志自动脱敏（卡号、金额等敏感字段）
5. **操作审计**: 退款、配置修改等敏感操作记录到 audit_logs 表

---

## 9. 实施计划

| 阶段 | 内容 | 预估工期 |
|------|------|----------|
| Phase 1 | 统一接口 + 数据库表 + 微信 Native 支付 | 1 周 |
| Phase 2 | 支付宝当面付 + PC 支付 | 1 周 |
| Phase 3 | 回调统一处理 + 幂等性 | 3 天 |
| Phase 4 | 对账系统 | 3 天 |
| Phase 5 | 微信 JSAPI + 前端集成 | 1 周 |
| Phase 6 | 测试 + 上线 | 1 周 |

---

## 10. 环境变量

```env
# 微信支付
WECHAT_PAY_MCH_ID=1234567890
WECHAT_PAY_APP_ID=wx1234567890abcdef
WECHAT_PAY_API_V3_KEY=your-api-v3-key
WECHAT_PAY_CERT_SERIAL=your-cert-serial
WECHAT_PAY_PRIVATE_KEY_PATH=/path/to/apiclient_key.pem
WECHAT_PAY_NOTIFY_URL=https://api.example.com/api/payments/webhook/wechat

# 支付宝
ALIPAY_APP_ID=2021000000000000
ALIPAY_PRIVATE_KEY_PATH=/path/to/app_private_key.pem
ALIPAY_PUBLIC_KEY_PATH=/path/to/alipay_public_key.pem
ALIPAY_NOTIFY_URL=https://api.example.com/api/payments/webhook/alipay
ALIPAY_RETURN_URL=https://www.example.com/payment/result
```
