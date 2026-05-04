# DDD 六边形架构技能

## Purpose

帮助 AI 编程助手具备完整的 DDD（领域驱动设计）六边形架构落地能力，涵盖项目创建、分层设计、代码规范到部署的完整工程生命周期。

**适用场景：**
- 创建新的 DDD 项目
- 设计领域模型（Entity、Aggregate、VO）
- 实现 Repository/Port-Adapter 模式
- 编排复杂业务（Case 层）
- 配置 Docker/Docker-Compose 部署

**适用工具：** QClaw、Claude Code、Cursor、Codex 等 AI 编程助手

## Prerequisities

- JDK 17+
- Maven 3.8.x
- MySQL 8.0+ (可选)
- Redis (可选)

## Key Concepts

### 架构分层

```
Trigger → API → Case → Domain ← Infrastructure
```

| 层级 | 职责 | 技术边界 |
|------|------|----------|
| Trigger | 入口：Controller、MQ Listener、Job | HTTP/RPC 调用 |
| API | 契约：DTO、接口定义、错误码 | 纯数据结构 |
| Case | 编排：跨域业务流、事务管理 | 协调服务 |
| Domain | 核心：业务规则、领域模型 | 纯 Java，无框架依赖 |
| Infrastructure | 实现：Repository、DAO、Gateway | MyBatis/Redis/HTTP |

### 核心原则

1. **Domain 纯净性**：Domain 层不依赖任何基础设施框架（MyBatis、JPA、Spring、Redis）
2. **依赖倒置**：Domain 定义接口，Infrastructure 实现接口
3. **聚合边界**：聚合内强一致性，聚合间最终一致性
4. **Case 编排**：跨域业务在 Case 层编排，不跨域直接调用 Repository

### 设计模式适用场景

| 业务特征 | 设计模式 | 示例 |
|---------|---------|------|
| 多种处理方式，根据条件选择 | 策略模式 | 多种审批能力 |
| 3+ 独立校验步骤 | 责任链模式 | 下单前多步校验 |
| 流程有明显分支，需要路由 | 决策树模式 | 营销流程节点 |
| 通用逻辑 + 差异化实现 | 模板方法 | 退款策略共用逻辑 |

## Application

### 1. 创建 DDD 项目

```bash
mvn archetype:generate \
  -DarchetypeGroupId=io.github.fuzhengwei \
  -DarchetypeArtifactId=ddd-scaffold-std-jdk17 \
  -DarchetypeVersion=1.8 \
  -DarchetypeRepository=https://maven.xiaofuge.cn/ \
  -DgroupId=cn.yourcompany \
  -DartifactId=your-project-name \
  -Dversion=1.0.0-SNAPSHOT \
  -Dpackage=cn.yourcompany.project \
  -B
```

### 2. 创建领域模型

```java
// 1. 创建实体
public class OrderEntity {
    private OrderStatus status;

    public void pay() {
        if (status != PENDING) throw new BusinessException("Invalid state");
        status = PAID;
    }
}

// 2. 创建聚合根
public class OrderAggregate {
    private OrderEntity order;
    private List<OrderItem> items;

    public void addItem(Product product, int quantity) {
        // 聚合内强一致性
    }
}

// 3. 创建值对象
public class MoneyVO {
    private final BigDecimal amount;
    private final String currency;

    public MoneyVO add(MoneyVO other) { ... }
}
```

### 3. 定义 Repository 接口（Domain 层）

```java
// Domain 层定义接口
public interface IOrderRepository {
    void save(OrderAggregate aggregate);
    OrderAggregate findById(Long orderId);
}

// Infrastructure 层实现
@Repository
public class OrderRepositoryImpl implements IOrderRepository {
    @Resource private OrderDao orderDao;

    @Override
    public void save(OrderAggregate aggregate) {
        orderDao.insert(toPO(aggregate));
    }
}
```

### 4. 创建领域服务

```java
// Domain 服务接口
public interface IOrderService {
    OrderAggregate create(CreateOrderCommand cmd);
    void pay(Long orderId);
}

// Domain 服务实现（纯业务逻辑）
@Service
public class OrderServiceImpl implements IOrderService {
    @Resource private IOrderRepository repository;

    @Override
    public OrderAggregate create(CreateOrderCommand cmd) {
        // 业务校验
        validateProduct(cmd.getProductId());
        // 创建聚合
        OrderAggregate aggregate = new OrderAggregate(...);
        // 持久化（通过接口，不直接依赖实现）
        repository.save(aggregate);
        return aggregate;
    }
}
```

### 5. Case 层编排（跨域业务）

```java
public interface IOrderCase {
    Result createAndPay(CreateOrderCommand cmd);
}

@Service
public class OrderCaseImpl implements IOrderCase {
    @Resource private IOrderService orderService;
    @Resource private IPaymentService paymentService;

    @Transactional
    public Result createAndPay(CreateOrderCommand cmd) {
        // 1. 创建订单
        OrderAggregate order = orderService.create(cmd);
        // 2. 调用支付（跨域编排）
        paymentService.process(order);
        return Result.success(order);
    }
}
```

## Examples

### 好的示例：策略模式处理多种审批

```java
// 策略接口（Domain 层）
public interface IApprovalStrategy {
    ApprovalResult execute(Map<String, String> config, Map<String, String> params);
    String type();
}

// 具体策略（Domain 层）
@Service("gitcode_approve")
public class GitCodeApprovalStrategy implements IApprovalStrategy {
    @Resource private IGitCodePort port;

    @Override
    public ApprovalResult execute(...) {
        return port.callGitCode(config, params);
    }

    @Override
    public String type() { return "gitcode"; }
}

// 策略工厂（Domain 层）
@Service
public class ApprovalStrategyFactory {
    @Resource
    private Map<String, IApprovalStrategy> strategyMap;

    public IApprovalStrategy get(String type) {
        return strategyMap.get(type);
    }
}
```

### 坏的示例：业务逻辑写在 Infrastructure

```java
// ❌ 错误：Executor 在 Infrastructure 层做业务判断
@Service
public class GitCodeScenarioExecutor implements IScenarioExecutor {
    @Override
    public Result execute(...) {
        // ❌ 业务校验不应在这里
        if (!paramValues.containsKey("username")) {
            return Result.fail("缺少用户名");
        }
        return gateway.call(...);
    }
}

// ✅ 正确：校验在 Domain 层过滤器
@Service
public class ParamValidateFilter implements IRuleFilter {
    @Override
    public FilterResult filter(Command cmd, Context ctx) {
        if (!cmd.getParams().containsKey("username")) {
            throw new AppException("缺少用户名");
        }
        return FilterResult.success();
    }
}
```

## Common Pitfalls

1. **Domain 层不纯净**：使用 @Resource 注入 MyBatis Mapper 或 Spring Service
2. **跨域依赖**：A 域的 Service 直接注入 B 域的 Repository
3. **业务逻辑外泄**：校验规则写在 Infrastructure 层
4. **聚合过大**：把所有实体放一个聚合，导致事务范围过大
5. **过早抽象**：业务简单却引入过多设计模式

## Directory Structure

```
{project}/
├── {project}-domain/           # Domain 层
│   └── cn/{company}/domain/
│       ├── {domain1}/
│       │   ├── adapter/
│       │   │   ├── port/       # Port 接口
│       │   │   └── repository/ # Repository 接口
│       │   ├── model/
│       │   │   ├── aggregate/ # 聚合根
│       │   │   ├── entity/    # 实体
│       │   │   └── valobj/    # 值对象
│       │   └── service/       # 领域服务
│       └── {domain2}/
├── {project}-infrastructure/   # Infrastructure 层
│   └── cn/{company}/infrastructure/
│       ├── adapter/
│       │   ├── port/          # Port 实现
│       │   └── repository/   # Repository 实现
│       ├── dao/              # MyBatis DAO
│       ├── gateway/          # HTTP/RPC 客户端
│       └── redis/            # Redis 配置
├── {project}-case/            # Case 层
├── {project}-api/             # API 层
├── {project}-trigger/         # Trigger 层
└── {project}-app/            # 启动入口
```

## References

- xfg-ddd-skills/references/architecture.md
- xfg-ddd-skills/references/entity.md
- xfg-ddd-skills/references/aggregate.md
- xfg-ddd-skills/references/domain-service.md
- xfg-ddd-skills/references/repository.md
- xfg-ddd-skills/references/case-layer.md
