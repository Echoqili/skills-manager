---
name: payment-sdk-guide
description: >
  支付宝/微信支付 SDK 集成向导。包含企业账户配置、签名验证、
  异步回调处理、对账文件生成等企业级支付集成要点。
applicable-regions: [CN]
user-invocable: true
---

# Payment SDK Guide - 支付 SDK 集成

支付宝/微信支付的完整集成指南。

## 支持的支付方式

| 支付方式 | 支付宝 | 微信支付 |
|----------|--------|----------|
| 扫码支付 | ✅ | ✅ |
| APP 支付 | ✅ | ✅ |
| JSAPI 支付 | ✅ | ✅ |
| H5 支付 | ✅ | ✅ |
| 小程序支付 | ❌ | ✅ |
| 刷脸支付 | ✅ | ✅ |

## 环境配置

### 支付宝

```typescript
// 支付宝配置
interface AlipayConfig {
  appId: string;           // 应用 ID
  privateKey: string;      // 应用私钥 (RSA2)
  alipayPublicKey: string; // 支付宝公钥
  gateway: string;         // 网关地址
  signType: 'RSA2';        // 签名类型
}

// 生产环境
const alipayConfig: AlipayConfig = {
  appId: process.env.ALIPAY_APP_ID,
  privateKey: process.env.ALIPAY_PRIVATE_KEY,
  alipayPublicKey: process.env.ALIPAY_PUBLIC_KEY,
  gateway: 'https://openapi.alipay.com/gateway.do',
  signType: 'RSA2',
};

// 沙箱环境
const alipaySandbox: AlipayConfig = {
  ...alipayConfig,
  gateway: 'https://openapi-sandbox.dl.alipaydev.com/gateway.do',
};
```

### 微信支付

```typescript
// 微信支付配置
interface WechatPayConfig {
  appId: string;           // 应用 ID
  mchId: string;           // 商户号
  serialNo: string;         // 证书序列号
  privateKey: string;       // 商户私钥 (PKCS8)
  wechatpayCert: string;    // 微信支付公钥
  passphrase: string;        // 私钥密码
  gateway: string;          // 网关地址
}

const wechatConfig: WechatPayConfig = {
  appId: process.env.WECHAT_APP_ID,
  mchId: process.env.WECHAT_MCH_ID,
  serialNo: process.env.WECHAT_SERIAL_NO,
  privateKey: process.env.WECHAT_PRIVATE_KEY,
  wechatpayCert: process.env.WECHAT_PAY_CERT,
  passphrase: '',
  gateway: 'https://api.mch.weixin.qq.com',
};
```

## 统一收单支付

### 支付宝 - 手机网站支付

```typescript
interface AlipayTradePagePayRequest {
  outTradeNo: string;      // 商户订单号
  totalAmount: number;      // 订单金额 (元)
  subject: string;         // 订单标题
  productCode: string;     // 产品码 (FAST_INSTANT_TRADE)
  body?: string;           // 订单描述
  timeExpire?: string;     // 过期时间 (ISO8601)
  extendParams?: {
    sysServiceProviderId?: string; // 服务商 ID
    hbFqNum?: string;              // 花呗分期期数
    hbFqSellerPercent?: string;    // 卖家承担手续费
  };
}

async function createAlipayPagePay(params: AlipayTradePagePayRequest) {
  const bizContent = {
    out_trade_no: params.outTradeNo,
    total_amount: params.totalAmount,
    subject: params.subject,
    product_code: params.productCode,
    body: params.body,
    time_expire: params.timeExpire,
    extend_params: params.extendParams,
  };

  // 签名并返回支付表单
  const form = await alipaySdk.pageExecute({
    method: 'GET',
    bizContent,
    return_url: 'https://your-domain.com/payment/return',
  });

  return form; // 返回 HTML 表单
}
```

### 微信支付 - JSAPI

```typescript
interface WechatJsApiPayRequest {
  outTradeNo: string;      // 商户订单号
  description: string;      // 订单描述
  amount: {
    total: number;          // 金额 (分)
    currency: 'CNY';
  };
  payer: {
    openid: string;         // 用户 openid
  };
  notifyUrl: string;        // 回调地址
}

async function createWechatJsApiPay(params: WechatJsApiPayRequest) {
  // 获取调用凭证
  const accessToken = await getAccessToken();

  // 统一下单
  const response = await fetch(`${wechatConfig.gateway}/v3/pay/transactions/jsapi`, {
    method: 'POST',
    headers: {
      'Authorization': `WECHATPAY2-SHA256withRSA ${getAuthHeader()}`,
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      'Wechatpay-Serial': wechatConfig.serialNo,
    },
    body: JSON.stringify({
      appid: wechatConfig.appId,
      mchid: wechatConfig.mchId,
      out_trade_no: params.outTradeNo,
      description: params.description,
      amount: params.amount,
      payer: params.payer,
      notify_url: params.notifyUrl,
    }),
  });

  const { prepay_id } = await response.json();

  // 生成签名
  const signType = 'RSA';
  const timestamp = Math.floor(Date.now() / 1000).toString();
  const nonceStr = generateNonceStr();
  const message = `${wechatConfig.appId}\n${timestamp}\n${nonceStr}\n${prepay_id}\n`;
  const signature = sign(message, wechatConfig.privateKey);

  // 返回微信 JS 调起参数
  return {
    appId: wechatConfig.appId,
    timestamp,
    nonceStr,
    package: `prepay_id=${prepay_id}`,
    signType,
    paySign: signature,
  };
}
```

## 异步回调处理

### 支付宝回调

```typescript
async function handleAlipayCallback(ctx) {
  const params = ctx.request.body;

  // 验证签名
  const signVerified = alipaySdk.verify({
    sign: params.sign,
    signType: params.signType,
    content: JSON.stringify(params),
    publicKey: alipayConfig.alipayPublicKey,
  });

  if (!signVerified) {
    ctx.body = { code: 'FAIL', message: '签名验证失败' };
    return;
  }

  // 处理通知
  const tradeStatus = params.trade_status;

  switch (tradeStatus) {
    case 'TRADE_SUCCESS':
    case 'TRADE_FINISHED':
      // 支付成功，更新订单状态
      await updateOrderStatus(params.out_trade_no, 'PAID');
      await sendInvoice(params.out_trade_no);
      break;

    case 'WAIT_BUYER_PAY':
      // 交易创建，等待支付
      break;

    case 'TRADE_CLOSED':
      // 交易关闭
      await updateOrderStatus(params.out_trade_no, 'CLOSED');
      break;
  }

  ctx.body = 'success';
}
```

### 微信回调

```typescript
async function handleWechatCallback(ctx) {
  const body = ctx.request.rawBody;

  // 解析通知
  const notification = JSON.parse(body);
  const { transaction_id, out_trade_no, trade_state, amount } = notification;

  // 验证签名
  const wechatpayCert = await loadWechatpayCert();
  const verified = verifyWechatSign(body, notification.sign, wechatpayCert);

  if (!verified) {
    ctx.body = { code: 'FAIL', message: '签名验证失败' };
    return;
  }

  // 处理通知
  if (trade_state === 'SUCCESS') {
    await updateOrderStatus(out_trade_no, 'PAID');
    await reconciliationCallback(out_trade_no, transaction_id);
  }

  ctx.body = { code: 'SUCCESS', message: '成功' };
}
```

## 对账文件处理

### 支付宝对账

```typescript
interface AlipayReconciliationRecord {
  tradeNo: string;          // 支付宝交易号
  merchantOrderNo: string;   // 商户订单号
  merchantFee: number;        // 商户手续费
  receiveAmount: number;      // 实收金额
  payAmount: number;         // 付款金额
  totalAmount: number;       // 订单金额
  tradeStatus: string;       // 交易状态
}

async function reconcileAlipay(filePath: string) {
  const records: AlipayReconciliationRecord[] = [];

  // 下载并解析对账文件 (CSV/GZIP)
  const decompressed = await decompressGzip(filePath);
  const lines = decompressed.split('\n');

  for (const line of lines.slice(1, -1)) { // 跳过表头和末尾
    const [
      , , , merchantOrderNo, , tradeNo, , ,
      tradeStatus, , , , payAmount, ,
      merchantFee, , receiveAmount, ,
    ] = line.split(',');

    records.push({
      tradeNo: tradeNo.trim(),
      merchantOrderNo: merchantOrderNo.trim(),
      merchantFee: parseFloat(merchantFee.trim()),
      receiveAmount: parseFloat(receiveAmount.trim()),
      payAmount: parseFloat(payAmount.trim()),
      tradeStatus: tradeStatus.trim(),
    });
  }

  // 对账逻辑
  for (const record of records) {
    const order = await getOrderByMerchantNo(record.merchantOrderNo);

    if (record.tradeStatus === 'TRADE_SUCCESS') {
      if (order.status !== 'PAID') {
        // 差异: 支付成功但订单未更新
        await fixOrderStatus(order.id, 'PAID');
        await logReconcileDiff(order.id, 'MISSING_PAYMENT', record);
      }

      if (order.amount !== record.payAmount) {
        // 差异: 金额不匹配
        await logReconcileDiff(order.id, 'AMOUNT_MISMATCH', record);
      }
    }
  }
}
```

## 安全检查清单

- [ ] 私钥不硬编码在代码中
- [ ] 回调地址使用 HTTPS
- [ ] 签名验证必须执行
- [ ] 订单金额在服务端计算
- [ ] 同一订单不可重复支付
- [ ] 对账文件定期下载和校验
- [ ] 敏感信息加密存储

## 错误码参考

| 支付宝 | 微信支付 | 说明 |
|--------|----------|------|
| ACQ.SUCCESS | SUCCESS | 成功 |
| ACQ.TRADE_NOT_EXIST | ORDERNOTEXIST | 订单不存在 |
| ACQ.TRADE_HAS_FINISHED | ORDERPAID | 订单已支付 |
| ACQ.BUYER_BALANCE_NOT_ENOUGH | NOTENOUGH | 余额不足 |
| ACQ.SYSTEM_ERROR | SYSTEMERROR | 系统错误 |

## 禁忌

- ❌ 不在客户端计算金额
- ❌ 不跳过签名验证
- ❌ 不明文存储私钥
- ❌ 不依赖同步回调更新订单
