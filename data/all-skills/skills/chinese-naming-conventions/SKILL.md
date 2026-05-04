---
name: chinese-naming-conventions
description: >
  中文变量命名规范检查。中国特色命名场景：拼音缩写、拼音英文混合、
  中文单位（万/亿）、特殊业务术语等。
applicable-regions: [CN]
user-invocable: true
---

# Chinese Naming Conventions - 中文命名规范

检查和规范化中国特色场景下的变量命名。

## 中国特色命名场景

### 1. 拼音缩写规范

**正确示例**:
```typescript
// 推荐: 使用完整拼音或常用缩写
const ysxm = "用户姓名";      // ✅ 姓名
const dz = "地址";            // ✅ 地址 (常用缩写)
const sjhm = "手机号码";      // ✅ 手机号码
const yhkh = "银行卡号";      // ✅ 银行账号

// ✅ 企业相关
const gsmc = "公司名称";      // 公司名称
const nsrsbh = "纳税人识别号"; // 纳税人识别号
const zzjgdm = "组织机构代码"; // 组织机构代码
```

**错误示例**:
```typescript
// ❌ 不推荐: 生僻缩写
const xyxx = "信用信息";       // 难以理解

// ❌ ❌ 禁用: 中英混排
const userName = "用户名";     // 风格混乱
const zhanghao = "账号";      // 拼音混用
```

### 2. 数字单位规范

```typescript
// ✅ 中国特色单位
const amountInWan = 100;        // 单位: 万
const populationInYi = 14;      // 单位: 亿
const priceInJiao = 55;         // 单位: 角
const lengthInChi = 30;          // 单位: 尺

// ✅ 带单位的金额
interface Money {
  value: number;      // 数值
  unit: '元' | '万' | '亿';
}

// ✅ 大数字分段 (中国人习惯四位分节)
const phoneNumber = "138-0000-0000";  // 手机号
const idCard = "110101-1990-01-01-0000"; // 身份证
```

### 3. 日期时间规范

```typescript
// ✅ 中国日期格式
const chineseDate = "2024年01月15日";
const chineseDatetime = "2024年01月15日 14时30分";

// ✅ 农历相关
interface LunarDate {
  year: string;     // 农历年
  month: string;    // 农历月
  day: string;      // 农历日
}

// ✅ 二十四节气
const solarTerms = [
  "立春", "雨水", "惊蛰", "春分",
  "清明", "谷雨", "立夏", "小满",
  "芒种", "夏至", "小暑", "大暑",
  "立秋", "处暑", "白露", "秋分",
  "寒露", "霜降", "立冬", "小雪",
  "大雪", "冬至", "小寒", "大寒"
];
```

### 4. 地址规范

```typescript
// ✅ 中国地址层级
interface ChineseAddress {
  province: string;    // 省
  city: string;       // 市
  district: string;   // 区/县
  street: string;     // 街道
  community: string;  // 小区
  building: string;   // 楼栋
  unit: string;       // 单元
  room: string;       // 房间号
}

// ✅ 行政区划代码
interface AdministrativeCode {
  provinceCode: string;  // 省级代码 (2位)
  cityCode: string;      // 市级代码 (4位)
  districtCode: string;  // 区级代码 (6位)
}
```

### 5. 特殊业务术语

```typescript
// ✅ 中国特色业务术语
const terminology = {
  // 政务
  "sxg": "事项",              // 行政审批事项
  "slfw": "受理范围",          // 受理范围
  "bljd": "办理进度",          // 办理进度

  // 金融
  "nkzh": "NK账号",           // 内控账号
  "djk": "东jk信用卡",         // 东方信用卡
  "zfdk": "政府贷款",          // 政府贷款

  // 企业
  "nsr": "纳税人",             // 纳税人
  "shxd": "社会信用代码",       // 社会信用代码
  "frdb": "法定代表人",         // 法定代表人
};

// ✅ 职位规范
const positions = {
  "CEO": "首席执行官",
  "CFO": "首席财务官",
  "CTO": "首席技术官",
  "COO": "首席运营官",
  "GM": "总经理",
  "Director": "总监",
  "Manager": "经理",
  "Supervisor": "主管",
};
```

## 检查清单

| 检查项 | 规则 | 违规示例 |
|--------|------|----------|
| 拼音长度 | 至少2个字符 | `x: "姓名"` |
| 缩写可识别 | 非行业通用缩写需注释 | `xyk: "信用开"` |
| 单位标注 | 大额数字需标注单位 | `amt: 10000000` |
| 风格统一 | 全项目统一命名风格 | `userName` vs `yonghu` |

## 代码检查规则

```javascript
// ESLint 规则示例
const rules = {
  // 禁止拼音变量名超过3个字符无注释
  "no-undocumented-pinyin": {
    pattern: /^[a-z]{4,}$/,
    message: "拼音变量超过3个字符需要添加注释"
  },

  // 禁止中英混用
  "no-mixed-chinese": {
    pattern: /[a-z][\u4e00-\u9fa5]|[a-z]{2,}[A-Z]/,
    message: "禁止中英混合命名"
  },

  // 大数字必须带单位
  "money-require-unit": {
    pattern: /amount|money|price|count/,
    requireUnit: true
  }
};
```

## 自动化检查

```bash
# 使用 lint 检查拼音命名
npx eslint --rule 'pinyin: error' src/

# 使用 prettier 格式化中文
npx prettier --write "**/*.{ts,js}" --parser typescript
```

## 最佳实践

1. **优先使用完整拼音**: `yonghu` 而非 `yh`
2. **添加类型注释**: `// yonghu: 用户名`
3. **统一命名风格**: 整个项目保持一致
4. **使用业务术语表**: 团队维护统一术语表
