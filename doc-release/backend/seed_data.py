"""示例仓库 order-center 的提交序列与文件内容（纯数据，无副作用）。

SEED_SEQUENCE 按时间顺序包含 commit 与 tag 两类步骤；
commit.files 中 relpath -> 内容，内容为空串表示删除该文件。
"""

SEED_SEQUENCE: list[dict] = [
    {
        "kind": "commit",
        "date": "2026-08-20 10:00:00 +0800",
        "message": "chore: 初始化 order-center 示例仓库",
        "files": {
            "README.md": """# order-center

电商订单中心（示例仓库，由释文 DocRelease 种子脚本生成）。

## 目录结构

- src/report/export     报表导出
- src/order             订单域（优惠券、状态机）
- src/checkout          结算页
- src/aftersale         售后政策
- src/member            会员权益
- src/goods             商品详情
- src/pay               支付
- src/seckill           秒杀库存
- src/auth              登录鉴权
- api/order             订单接口
- api/report            报表接口
- api/legacy            历史遗留接口
""",
            "package.json": """{
  "name": "order-center",
  "version": "2.13.3",
  "private": true,
  "scripts": { "test": "vitest run" }
}
""",
            "go.mod": """module order-center

go 1.23
""",
            "src/report/export/index.ts": """import { chunkToText } from "./writer";
import { loadAllOrders } from "../orders";

export async function exportOrders(query: ExportQuery): Promise<ExportResult> {
  const all = await loadAllOrders(query);
  const text = chunkToText(all);
  await writeFileSafe(text);
  return { rows: all.length };
}
""",
            "src/report/export/writer.ts": """export function chunkToText(rows: OrderRow[]): string {
  return rows.map((r) => r.join(",")).join("\\n");
}

export async function writeFileSafe(text: string): Promise<void> {
  await fs.writeFile(OUTPUT_PATH, text, "utf-8");
}
""",
            "api/report/export.go": """package report

// ExportRequest 报表导出请求
type ExportRequest struct {
	Query string `json:"query"`
}

// ExportResponse 报表导出响应
type ExportResponse struct {
	Rows int `json:"rows"`
}

// MaxExportRows 单次导出行数上限
const MaxExportRows = 50000

// HandleExport 处理导出请求：一次性装载全部行后写出
func HandleExport(req ExportRequest, w Writer) error {
	rows, err := LoadRows(req.Query)
	if err != nil {
		return err
	}
	return w.WriteAll(rows)
}
""",
            "src/order/coupon/stack.ts": """export interface Coupon {
  id: string;
  amount: number;
}

// pickBestCoupon 从单张券中挑选可用券
export function pickBestCoupon(coupon: Coupon, amount: number): Coupon {
  return coupon.amount <= amount ? coupon : { id: "", amount: 0 };
}
""",
            "src/checkout/summary.tsx": """import type { Coupon } from "../order/coupon/stack";

export function CheckoutSummary(props: { coupon: Coupon; total: number }) {
  return (
    <div className="summary">
      <div>商品总额：{props.total}</div>
      <div>优惠券抵扣：{props.coupon.amount}</div>
    </div>
  );
}
""",
            "src/aftersale/policy.ts": """// REFUND_WINDOW_DAYS 无理由退款窗口（天）
export const REFUND_WINDOW_DAYS = 7;

export function canRefund(daysSincePay: number): boolean {
  return daysSincePay <= REFUND_WINDOW_DAYS;
}
""",
            "api/order/list.go": """package order

// ListResponse 订单列表响应
type ListResponse struct {
	Items []Order `json:"items"`
	Total int     `json:"total"`
}

// HandleList 返回用户订单列表
func HandleList(uid string, page int) (*ListResponse, error) {
	items, total, err := queryOrders(uid, page)
	if err != nil {
		return nil, err
	}
	return &ListResponse{Items: items, Total: total}, nil
}
""",
            "src/member/benefit/verify.ts": """import { cache } from "../cache";
import { checkLevel } from "./level";

// verifyCached 基于本地缓存的会员等级校验
export function verifyCached(uid: string, order: Order): BenefitCheck {
  const profile = cache.get(uid);
  return checkLevel(profile.level, order.totalAmount, order.items);
}
""",
            "src/goods/detail/price.tsx": """export function PriceBlock(props: { price: number }) {
  return (
    <div className="price">
      <span className="symbol">¥</span>
      <span className="value">{props.price.toFixed(2)}</span>
    </div>
  );
}
""",
            "src/order/state/machine.ts": """export type Status = "created" | "paid" | "shipped" | "done" | "closed";
export type Action = "pay" | "ship" | "finish" | "close";

const TABLE: Record<Status, Partial<Record<Action, Status>>> = {
  created: { pay: "paid", close: "closed" },
  paid: { ship: "shipped", close: "closed" },
  shipped: { finish: "done" },
  done: {},
  closed: {},
};

// transition 同步计算状态迁移
export function transition(from: Status, action: Action): Status {
  return TABLE[from][action] ?? from;
}
""",
            "api/legacy/order.go": """package legacy

// CreateOrderV1 老版下单接口（POST /v1/order/create），仅兼容存量客户端
func CreateOrderV1(req CreateReq) (*CreateResp, error) {
	return createOrder(req, "v1")
}
""",
            "src/pay/callback/verify.ts": """import { md5 } from "../crypto";

// verifyCallback 校验支付回调签名（MD5）
export function verifyCallback(payload: PayPayload, sign: string): boolean {
  const raw = `${payload.orderId}${payload.amount}${payload.tradeNo}${SECRET}`;
  return md5(raw) === sign;
}
""",
            "src/seckill/stock/deduct.ts": """// deductStock 扣减秒杀库存：先读再写
export async function deductStock(skuId: string, count: number): Promise<boolean> {
  const stock = Number(await redis.get(`seckill:stock:${skuId}`));
  if (stock < count) {
    return false;
  }
  await redis.set(`seckill:stock:${skuId}`, String(stock - count));
  return true;
}
""",
            "src/auth/sms.ts": """// loginBySms 短信验证码登录
export async function loginBySms(phone: string, code: string): Promise<LoginResult> {
  const cached = await store.get(`sms:${phone}`);
  if (cached !== code) {
    return { ok: false };
  }
  return issueToken(phone);
}
""",
        },
    },
    {"kind": "tag", "name": "v2.13.3"},
    {
        "kind": "commit",
        "date": "2026-09-10 14:20:00 +0800",
        "message": "feat(report): 导出支持分片流式写出",
        "files": {
            "src/report/export/stream.ts": """// CHUNK_SIZE 单次写出分片大小（行）
export const CHUNK_SIZE = 2000;

// streamWrite 分片流式写出，避免一次性载入全部行
export async function streamWrite(query: ExportQuery, sink: LineSink): Promise<number> {
  let cursor = "";
  let written = 0;
  while (true) {
    const page = await fetchPage(query, cursor, CHUNK_SIZE);
    if (page.rows.length === 0) {
      break;
    }
    for (const row of page.rows) {
      await sink.write(row);
      written += 1;
    }
    cursor = page.nextCursor;
  }
  return written;
}
""",
        },
    },
    {
        "kind": "commit",
        "date": "2026-09-11 11:05:00 +0800",
        "message": "feat(report): 导出网络请求增加指数退避重试",
        "files": {
            "src/report/export/retry.ts": """// MAX_RETRIES 网络抖动重试次数
export const MAX_RETRIES = 3;

// withRetry 指数退避重试包装
export async function withRetry<T>(fn: () => Promise<T>, retries = MAX_RETRIES): Promise<T> {
  let lastError: unknown;
  for (let i = 0; i <= retries; i += 1) {
    try {
      return await fn();
    } catch (err) {
      lastError = err;
      await sleep(200 * 2 ** i);
    }
  }
  throw lastError;
}
""",
        },
    },
    {
        "kind": "commit",
        "date": "2026-09-12 16:40:00 +0800",
        "message": "refactor(report): 导出接口按游标分页并走流式写出",
        "files": {
            "src/report/export/index.ts": """import { streamWrite } from "./stream";
import { withRetry } from "./retry";
import { loadAllOrders } from "../orders";

// 小数据量走内存导出，大数据量走分片流式写出
export async function exportOrders(query: ExportQuery): Promise<ExportResult> {
  const estimated = await estimateRows(query);
  if (estimated <= MEMORY_THRESHOLD) {
    const all = await withRetry(() => loadAllOrders(query));
    await writeFileSafe(chunkToText(all));
    return { rows: all.length };
  }
  const written = await withRetry(() => streamWrite(query, fileSink(OUTPUT_PATH)));
  return { rows: written };
}
""",
            "api/report/export.go": """package report

// ExportRequest 报表导出请求
type ExportRequest struct {
	Query  string `json:"query"`
	Cursor string `json:"cursor"`
}

// ExportResponse 报表导出响应
type ExportResponse struct {
	Rows       int    `json:"rows"`
	NextCursor string `json:"nextCursor"`
}

// PageSize 单页行数
const PageSize = 2000

// HandleExport 处理导出请求：按游标分片返回
func HandleExport(req ExportRequest, w Writer) error {
	page, err := LoadPage(req.Query, req.Cursor, PageSize)
	if err != nil {
		return err
	}
	return w.WritePage(page)
}
""",
        },
    },
    {"kind": "tag", "name": "v2.13.4"},
    {
        "kind": "commit",
        "date": "2026-09-24 10:30:00 +0800",
        "message": "feat(coupon): 支持优惠券叠加并求组合最优解",
        "files": {
            "src/order/coupon/stack.ts": """export interface Coupon {
  id: string;
  amount: number;
  stackable: boolean;
}

// MAX_SEARCH_COUNT 券数量上限，超过则退化为贪心
const MAX_SEARCH_COUNT = 12;

// resolveBestCombination 求券组合最优解（可叠加场景）
export function resolveBestCombination(coupons: Coupon[], amount: number): Coupon[] {
  const usable = coupons.filter((c) => c.amount <= amount);
  const single = usable.filter((c) => !c.stackable);
  const stackable = usable.filter((c) => c.stackable);
  let best = pickBestSingle(single);
  if (stackable.length <= MAX_SEARCH_COUNT) {
    const combo = searchMaxSubset(stackable, amount);
    if (sum(combo) > best.amount) {
      best = { id: "combo", amount: sum(combo), stackable: true };
    }
  } else {
    const greedy = greedyMax(stackable, amount);
    if (greedy.amount > best.amount) {
      best = greedy;
    }
  }
  return best.id ? [best] : [];
}

// pickBestCoupon 保留旧接口：仅支持单券
export function pickBestCoupon(coupon: Coupon, amount: number): Coupon {
  return coupon.amount <= amount ? coupon : { id: "", amount: 0, stackable: false };
}
""",
            "src/checkout/summary.tsx": """import type { Coupon } from "../order/coupon/stack";

export function CheckoutSummary(props: { coupons: Coupon[]; total: number }) {
  const discount = props.coupons.reduce((sum, c) => sum + c.amount, 0);
  return (
    <div className="summary">
      <div>商品总额：{props.total}</div>
      {props.coupons.map((c) => (
        <div key={c.id}>优惠券抵扣：{c.amount}</div>
      ))}
      <div className="payable">应付：{Math.max(props.total - discount, 0)}</div>
    </div>
  );
}
""",
        },
    },
    {
        "kind": "commit",
        "date": "2026-09-28 09:15:00 +0800",
        "message": "feat(aftersale): 无理由退款窗口由 7 天调整为 15 天",
        "files": {
            "src/aftersale/policy.ts": """// REFUND_WINDOW_DAYS 无理由退款窗口（天），v3 前调整为 15 天
export const REFUND_WINDOW_DAYS = 15;

// MAX_REFUND_AMOUNT 单笔最大退款金额（元）
export const MAX_REFUND_AMOUNT = 20000;

export function canRefund(daysSincePay: number): boolean {
  return daysSincePay <= REFUND_WINDOW_DAYS;
}
""",
        },
    },
    {
        "kind": "commit",
        "date": "2026-10-02 15:50:00 +0800",
        "message": "feat(order): 订单列表返回时可叠加券标记",
        "files": {
            "api/order/list.go": """package order

// ListResponse 订单列表响应
type ListResponse struct {
	Items           []Order `json:"items"`
	Total           int     `json:"total"`
	CouponStackable bool    `json:"couponStackable"`
}

// HandleList 返回用户订单列表
func HandleList(uid string, page int) (*ListResponse, error) {
	items, total, err := queryOrders(uid, page)
	if err != nil {
		return nil, err
	}
	return &ListResponse{Items: items, Total: total, CouponStackable: featureOn("coupon_stack")}, nil
}
""",
        },
    },
    {
        "kind": "commit",
        "date": "2026-10-08 17:25:00 +0800",
        "message": "feat(member): 会员权益改为实时校验，移除本地缓存校验",
        "files": {
            "src/member/benefit/verify.ts": """import { fetchProfile } from "../remote";
import { checkLevel } from "./level";
import { PROFILE_TTL_MS } from "./cache-policy";

// verifyRealtime 实时拉取会员档案校验权益，避免缓存过期导致误判
export async function verifyRealtime(uid: string, order: Order): Promise<BenefitCheck> {
  const profile = await fetchProfile(uid, PROFILE_TTL_MS);
  return checkLevel(profile.level, order.totalAmount, order.items);
}
""",
            "src/goods/detail/price.tsx": """import { calcAfterPromotion } from "../promotion";

export function PriceBlock(props: { price: number; couponAmount: number }) {
  const final = calcAfterPromotion(props.price, props.couponAmount);
  return (
    <div className="price">
      <span className="label">预计到手价</span>
      <span className="symbol">¥</span>
      <span className="value">{final.toFixed(2)}</span>
    </div>
  );
}
""",
        },
    },
    {"kind": "tag", "name": "v2.14.0"},
    {
        "kind": "commit",
        "date": "2026-10-09 10:05:00 +0800",
        "message": "feat(legacy)!: 下线 v1 下单接口",
        "files": {
            "api/legacy/order.go": """package legacy

// v1 下单接口已于 3.0 下线：POST /v1/order/create 不再受理流量。
// 存量客户端请迁移至 POST /v2/orders（由 order 包提供）。
// 保留本文件记录迁移说明，确认无调用后可删除。

// GoneHandler 对旧路径统一返回 410
func GoneHandler(w http.ResponseWriter, r *http.Request) {
	http.Error(w, "v1 order api removed, use POST /v2/orders", http.StatusGone)
}
""",
        },
    },
    {
        "kind": "commit",
        "date": "2026-10-10 16:30:00 +0800",
        "message": "refactor(order)!: 状态机改为事件溯源，新增多仓库存分配",
        "files": {
            "src/order/state/machine.ts": """export type Status = "created" | "paid" | "shipped" | "done" | "closed";
export type Action = "pay" | "ship" | "finish" | "close";

export interface OrderEvent {
  action: Action;
  at: number;
  operator: string;
}

const TABLE: Record<Status, Partial<Record<Action, Status>>> = {
  created: { pay: "paid", close: "closed" },
  paid: { ship: "shipped", close: "closed" },
  shipped: { finish: "done" },
  done: {},
  closed: {},
};

// project 依据事件序列重放得出当前状态（事件溯源）
export function project(events: OrderEvent[]): Status {
  let state: Status = "created";
  for (const e of events) {
    state = TABLE[state][e.action] ?? state;
  }
  return state;
}
""",
            "src/inventory/multi-warehouse.ts": """// 多仓库存分配：从小仓优先填满
interface Allocation {
  warehouseId: string;
  count: number;
}

// allocateAcross 跨多仓分配库存：从小仓优先填满
export async function allocateAcross(skuId: string, count: number): Promise<Allocation[]> {
  const warehouses = await listWarehouses(skuId);
  warehouses.sort((a, b) => a.available - b.available);
  const plan: Allocation[] = [];
  let remain = count;
  for (const wh of warehouses) {
    if (remain <= 0) {
      break;
    }
    const take = Math.min(wh.available, remain);
    plan.push({ warehouseId: wh.id, count: take });
    remain -= take;
  }
  if (remain > 0) {
    throw new StockShortageError(skuId, remain);
  }
  return plan;
}
""",
        },
    },
    {
        "kind": "commit",
        "date": "2026-10-12 11:45:00 +0800",
        "message": "feat(pay)!: 支付回调签名升级为 HMAC-SHA256；秒杀扣减改 Lua 原子脚本",
        "files": {
            "src/pay/callback/verify.ts": """import { hmacSha256 } from "../crypto";

// verifyCallback 校验支付回调签名（HMAC-SHA256，替代 MD5）
export function verifyCallback(payload: PayPayload, sign: string): boolean {
  const raw = `${payload.orderId}${payload.amount}${payload.tradeNo}`;
  const expected = hmacSha256(raw, SIGN_KEY);
  return timingSafeEqual(expected, sign);
}
""",
            "src/seckill/stock/deduct.ts": """const LUA_DEDUCT = `
local stock = tonumber(redis.call("get", KEYS[1]) or "-1")
if stock < tonumber(ARGV[1]) then
  return 0
end
redis.call("decrby", KEYS[1], ARGV[1])
return 1
`;

// deductStock 扣减秒杀库存：Lua 脚本原子执行，避免并发超卖
export async function deductStock(skuId: string, count: number): Promise<boolean> {
  const result = await redis.eval(LUA_DEDUCT, 1, `seckill:stock:${skuId}`, String(count));
  return result === 1;
}
""",
        },
    },
    {
        "kind": "commit",
        "date": "2026-10-13 09:30:00 +0800",
        "message": "feat(aftersale): 支持按明细部分退款",
        "files": {
            "src/aftersale/partial-refund.ts": """// refundPartial 按明细发起部分退款，支持多次退至总额上限
export async function refundPartial(orderNo: string, items: RefundItem[]): Promise<RefundResult> {
  const refunded = await sumRefunded(orderNo);
  const request = sumItems(items);
  if (refunded + request > MAX_REFUND_AMOUNT) {
    throw new RefundLimitError(orderNo);
  }
  return createRefund(orderNo, items);
}
""",
        },
    },
    {
        "kind": "commit",
        "date": "2026-10-14 15:10:00 +0800",
        "message": "chore(auth)!: 短信登录迁移至统一鉴权中心",
        "files": {
            "src/auth/sms.ts": """// 短信登录已于 3.0 迁移至统一鉴权中心（auth-center），本文件仅保留迁移说明。
// 新接入方式见 https://auth-center.internal/docs/sms-login
export {};
""",
        },
    },
    {"kind": "tag", "name": "v3.0.0"},
]

SCENARIOS: list[dict] = [
    {
        "id": "patch",
        "name": "补丁修复",
        "short": "hotfix",
        "version": "v2.13.4",
        "base": "v2.13.3",
        "head": "v2.13.4",
        "description": "报表导出超时与网络抖动问题的修复版本，变更集中在报表导出模块。",
    },
    {
        "id": "feature",
        "name": "功能迭代",
        "short": "feature",
        "version": "v2.14.0",
        "base": "v2.13.3",
        "head": "v2.14.0",
        "description": "优惠券叠加、退款窗口调整、会员权益实时校验等功能特性版本。",
    },
    {
        "id": "major",
        "name": "大版本升级",
        "short": "major",
        "version": "v3.0.0",
        "base": "v2.14.0",
        "head": "v3.0.0",
        "description": "含破坏性变更的大版本：v1 接口下线、状态机事件化、签名升级与登录迁移。",
    },
]
