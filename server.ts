import express from "express";
import http from "http";
import path from "path";
import { WebSocketServer, WebSocket } from "ws";
import { createServer as createViteServer } from "vite";
import dotenv from "dotenv";

dotenv.config();

const PORT = 3000;

// ==================== 初始种子数据与持久化内存存储 ====================

interface OrderItem {
  skuId: string;
  title: string;
  category: string;
  spec: string;
  price: number;
  quantity: number;
  imageUrl: string;
  isSpecialProduct: boolean;
  isCustomized: boolean;
}

interface ExpressData {
  company: string;
  companyCode: string;
  trackingNumber: string;
  status: string;
  statusDescription: string;
  timeline: Array<{ time: string; status: string; context: string }>;
}

interface AfterSalesData {
  canReturn7Days: boolean;
  returnDaysRemaining: number;
  signedDays: number;
  returnPolicy: string;
  shippingSubsidy: string;
  warrantyStatus: string;
  warrantyExpiredDate: string;
  warrantyPolicy: string;
  refundStatus?: string;
  refundAmount?: number;
  refundReason?: string;
  requiresHumanAudit?: boolean;
  auditOperator?: string;
  auditTime?: string;
  auditNote?: string;
}

interface OrderData {
  orderId: string;
  orderSn: string;
  userId: string;
  userName: string;
  userPhone: string;
  vipLevel: string;
  status: string;
  statusText: string;
  statusCode: number;
  createTime: string;
  payTime: string;
  shipTime: string;
  deliveryTime?: string | null;
  items: OrderItem[];
  totalAmount: number;
  paidAmount: number;
  shippingFee: number;
  express: ExpressData;
  receiver: { name: string; phone: string; address: string };
  afterSales: AfterSalesData;
  updatedAt: string;
}

interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system" | "human_agent";
  content: string;
  confidenceScore?: number;
  agentName?: string;
  agentId?: string;
  references?: Array<{ id: string; title: string; score: number; snippet: string }>;
  stepTrace?: Array<{ node: string; description: string; durationMs: number; status: string }>;
  queriedOrder?: OrderData;
  refundConfirmationPending?: boolean;
  pendingRefundOrder?: OrderData;
  timestamp: string;
}

interface CustomerProfile {
  name: string;
  phone: string;
  vipLevel: string;
  sentiment: string;
  urgency: string;
  intent: string;
  tags: string[];
  orderId: string;
}

interface ConversationSession {
  id: string;
  userName: string;
  status: "AI_HANDLING" | "NEEDS_INTERVENTION" | "HUMAN_INTERVENED" | "TRANSFERRED";
  assignedAgent: string | null;
  assignedAgentId: string | null;
  customerProfile: CustomerProfile;
  summaryMemory: string;
  messages: ChatMessage[];
  metrics: {
    totalTurns: number;
    avgLatencyMs: number;
    avgConfidence: number;
    escalatedAt: string | null;
  };
  contextSnapshot: any;
  latestTransfer: any;
  unreadForAgent: boolean;
  createdAt: string;
  updatedAt: string;
}

// 订单库
const initialOrders: Record<string, OrderData> = {
  "ORD-2026-88992": {
    orderId: "ORD-2026-88992",
    orderSn: "202603258899201",
    userId: "user_001",
    userName: "王女士",
    userPhone: "138****6699",
    vipLevel: "黄金会员",
    status: "DELIVERED",
    statusText: "已签收",
    statusCode: 4,
    createTime: "2026-03-22 14:20:10",
    payTime: "2026-03-22 14:21:05",
    shipTime: "2026-03-23 09:30:00",
    deliveryTime: "2026-03-25 11:24:36",
    items: [
      {
        skuId: "SKU-ROBOT-001",
        title: "XX智能全自动扫地机器人 Pro (双向避障激光导航版)",
        category: "生活电器",
        spec: "曜石黑 / 双盘旋转擦地 / 自动集尘基站",
        price: 2999.0,
        quantity: 1,
        imageUrl: "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=160&q=80",
        isSpecialProduct: false,
        isCustomized: false,
      },
    ],
    totalAmount: 2999.0,
    paidAmount: 2999.0,
    shippingFee: 0.0,
    express: {
      company: "顺丰速运",
      companyCode: "SF",
      trackingNumber: "SF1882049281",
      status: "DELIVERED",
      statusDescription: "买家已在自提柜完成签收",
      timeline: [
        { time: "2026-03-25 11:24:36", status: "已签收", context: "【已签收】您的快件已由本人在 [北京市朝阳区自提柜] 签收。" },
        { time: "2026-03-25 08:15:20", status: "派送中", context: "【派送中】顺丰速运 派件员 张师傅正在派送。" },
      ],
    },
    receiver: { name: "王女士", phone: "138****6699", address: "北京市朝阳区亮马桥路88号XX花园3号楼1202室" },
    afterSales: {
      canReturn7Days: true,
      returnDaysRemaining: 4,
      signedDays: 3,
      returnPolicy: "支持7天无理由退货（商品完好未受损、配件齐全）",
      shippingSubsidy: "黄金会员享有平台免运费退货补贴",
      warrantyStatus: "生效中",
      warrantyExpiredDate: "2027-03-25",
      warrantyPolicy: "1年全国联保，15天内硬件质量故障免费换新机",
      refundStatus: "NONE",
      refundAmount: 0.0,
      refundReason: "",
      requiresHumanAudit: false,
    },
    updatedAt: "2026-03-25 11:25:00",
  },
  "ORD-2026-90412": {
    orderId: "ORD-2026-90412",
    orderSn: "202603279041202",
    userId: "user_002",
    userName: "张先生",
    userPhone: "139****1122",
    vipLevel: "普通会员",
    status: "IN_TRANSIT",
    statusText: "运输中",
    statusCode: 3,
    createTime: "2026-03-26 10:15:00",
    payTime: "2026-03-26 10:16:30",
    shipTime: "2026-03-27 08:45:00",
    deliveryTime: null,
    items: [
      {
        skuId: "SKU-TEA-002",
        title: "纯手工定制刻字紫砂壶 (大师编号收藏版)",
        category: "工艺礼品",
        spec: "底款刻字：『宁静致远』 / 280ml 原矿紫泥",
        price: 880.0,
        quantity: 1,
        imageUrl: "https://images.unsplash.com/photo-1576092768241-dec231879fc3?auto=format&fit=crop&w=160&q=80",
        isSpecialProduct: true,
        isCustomized: true,
      },
    ],
    totalAmount: 880.0,
    paidAmount: 880.0,
    shippingFee: 0.0,
    express: {
      company: "京东快递",
      companyCode: "JD",
      trackingNumber: "JD0092817263",
      status: "IN_TRANSIT",
      statusDescription: "快件正在高速运输中，预计次日送达",
      timeline: [{ time: "2026-03-27 16:30:00", status: "运输中", context: "【运输中】快件已到达杭州萧山转运中心。" }],
    },
    receiver: { name: "张先生", phone: "139****1122", address: "浙江省杭州市西湖区文三路398号" },
    afterSales: {
      canReturn7Days: false,
      returnDaysRemaining: 0,
      signedDays: 0,
      returnPolicy: "此商品为个人定制专属刻字工艺品，非质量问题不支持7天无理由退货",
      shippingSubsidy: "普通会员个人退货需自行承担运费",
      warrantyStatus: "破损包赔",
      warrantyExpiredDate: "2026-04-26",
      warrantyPolicy: "运输碎裂破损支持极速拍照补发或先行赔付",
    },
    updatedAt: "2026-03-27 16:30:00",
  },
  "ORD-2026-00100": {
    orderId: "ORD-2026-00100",
    orderSn: "202603280010003",
    userId: "user_001",
    userName: "王女士",
    userPhone: "138****6699",
    vipLevel: "黄金会员",
    status: "DELIVERED",
    statusText: "已签收",
    statusCode: 4,
    createTime: "2026-03-27 10:00:00",
    payTime: "2026-03-27 10:00:15",
    shipTime: "2026-03-27 14:00:00",
    deliveryTime: "2026-03-28 09:30:00",
    items: [
      {
        skuId: "SKU-CABLE-005",
        title: "便携多功能柔性理线器/清洁湿巾 (3包装)",
        category: "数码配件",
        spec: "黑色 3包装 / 简易收纳",
        price: 2.5,
        quantity: 1,
        imageUrl: "https://images.unsplash.com/photo-1583863788434-e58a36330cf0?auto=format&fit=crop&w=160&q=80",
        isSpecialProduct: false,
        isCustomized: false,
      },
    ],
    totalAmount: 2.5,
    paidAmount: 2.5,
    shippingFee: 0.0,
    express: {
      company: "中通快递",
      companyCode: "ZTO",
      trackingNumber: "ZT771029381",
      status: "DELIVERED",
      statusDescription: "买家已于菜鸟驿站完成签收",
      timeline: [{ time: "2026-03-28 09:30:00", status: "已签收", context: "【已签收】您的快件已在自提柜完成签收。" }],
    },
    receiver: { name: "王女士", phone: "138****6699", address: "北京市朝阳区亮马桥路88号XX花园" },
    afterSales: {
      canReturn7Days: true,
      returnDaysRemaining: 6,
      signedDays: 1,
      returnPolicy: "支持7天无理由退货（商品未拆封）",
      shippingSubsidy: "黄金会员享极速小额免审核退款特权",
      warrantyStatus: "生效中",
      warrantyExpiredDate: "2026-04-28",
      warrantyPolicy: "质量问题直接换新",
      refundStatus: "NONE",
      refundAmount: 0.0,
      refundReason: "",
      requiresHumanAudit: false,
    },
    updatedAt: "2026-03-28 09:30:00",
  },
};

const orders: Record<string, OrderData> = JSON.parse(JSON.stringify(initialOrders));

const agents = [
  {
    id: "agent_101",
    name: "张小雅",
    title: "金牌专属坐席",
    department: "VIP客户体验保障中心",
    status: "BUSY",
    currentWorkload: 1,
    maxWorkload: 5,
    rating: 4.98,
    specialties: ["退换货争议调解", "黄金会员运费补贴", "高情绪安抚"],
    recommendedFor: ["退运费", "到账时间", "情绪安抚", "会员特权"],
    avatar: "https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=120&q=80",
    phone: "分机 8011",
    email: "zhangxiaoya@xx-mall.com",
  },
  {
    id: "agent_102",
    name: "李雪",
    title: "退换货与物流主管",
    department: "售后争议调解组",
    status: "IDLE",
    currentWorkload: 0,
    maxWorkload: 5,
    rating: 4.95,
    specialties: ["特殊商品退货政策", "定制品纠纷", "物流丢件理赔"],
    recommendedFor: ["定制商品", "刻字不退", "物流延误", "顺丰拦截"],
    avatar: "https://images.unsplash.com/photo-1517841905240-472988babdf9?auto=format&fit=crop&w=120&q=80",
    phone: "分机 8012",
    email: "lixue@xx-mall.com",
  },
  {
    id: "agent_105",
    name: "赵林",
    title: "财务与专票专员",
    department: "商城财务税务组",
    status: "IDLE",
    currentWorkload: 0,
    maxWorkload: 4,
    rating: 4.93,
    specialties: ["增值税专票开具", "发票红冲与重开", "企业对公打款核验"],
    recommendedFor: ["发票", "税号", "对公转账"],
    avatar: "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?auto=format&fit=crop&w=120&q=80",
    phone: "分机 8019",
    email: "zhaolin@xx-mall.com",
  },
  {
    id: "agent_108",
    name: "陈主管",
    title: "客户体验总监",
    department: "VIP客户关系管理部",
    status: "IDLE",
    currentWorkload: 0,
    maxWorkload: 3,
    rating: 4.99,
    specialties: ["大客户特批退款", "消协工单处理", "全链路体验督办"],
    recommendedFor: ["主管接入", "消协投诉", "特批"],
    avatar: "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?auto=format&fit=crop&w=120&q=80",
    phone: "分机 8888",
    email: "chenzhu@xx-mall.com",
  },
];

// 会话库
const sessions: Record<string, ConversationSession> = {
  "session_user_001": {
    id: "session_user_001",
    userName: "王女士",
    status: "AI_HANDLING",
    assignedAgent: null,
    assignedAgentId: null,
    customerProfile: {
      name: "王女士",
      phone: "138****6699",
      vipLevel: "黄金会员",
      sentiment: "frustrated",
      urgency: "高",
      intent: "7天无理由退货运费与到账时间",
      tags: ["黄金会员", "免运费特权", "急躁", "签收第3天"],
      orderId: "ORD-2026-88992",
    },
    summaryMemory: "客户王女士（黄金会员，订单 ORD-2026-88992）签收扫地机器人3天，因尺寸不合适想申请7天无理由退货，咨询退货运费是否需要自己出以及退款多久到账。系统已确认黄金会员享免运费补贴。",
    messages: [
      {
        id: "m1",
        role: "user",
        content: "我3天前买的扫地机器人，包装完好没拆过封，想退货的话运费谁承担？",
        timestamp: "10:14:20",
      },
      {
        id: "m2",
        role: "assistant",
        content: "王女士您好！根据XX商城政策：签收7天内商品完好支持7天无理由退换。虽然个人原因退换通常由买家承担运费，但检测到您是【黄金会员】，享有平台全额补贴的『退货免运费』专属权益，您无需承担任何寄回运费！",
        confidenceScore: 0.96,
        timestamp: "10:14:24",
      },
      {
        id: "m3",
        role: "user",
        content: "那我退回去之后，钱大概几天能退回我的支付宝？",
        timestamp: "10:15:02",
      },
      {
        id: "m4",
        role: "assistant",
        content: "关于退款到账时效，供您参考：\n• 仓库收到退回商品后 **48小时内** 完成质检入库；\n• 质检合格后系统自动原路发起退款：\n  - 支付宝 / 微信零钱：即时原路到账；\n  - 银行借记卡：1~3个工作日到账；\n  - 信用卡：3~5个工作日到账。\n\n如需正式提交退款，随时告诉我或输入「退款」即可！",
        confidenceScore: 0.95,
        timestamp: "10:15:06",
      },
    ],
    metrics: {
      totalTurns: 4,
      avgLatencyMs: 320,
      avgConfidence: 0.96,
      escalatedAt: null,
    },
    contextSnapshot: null,
    latestTransfer: null,
    unreadForAgent: false,
    createdAt: "2026-03-28 10:14:00",
    updatedAt: "2026-03-28 10:15:06",
  },
  "session_user_002": {
    id: "session_user_002",
    userName: "张先生",
    status: "AI_HANDLING",
    assignedAgent: null,
    assignedAgentId: null,
    customerProfile: {
      name: "张先生",
      phone: "139****1122",
      vipLevel: "普通会员",
      sentiment: "neutral",
      urgency: "中",
      intent: "个人定制刻字紫砂壶退货咨询",
      tags: ["普通会员", "定制工艺品", "运输中"],
      orderId: "ORD-2026-90412",
    },
    summaryMemory: "客户张先生定制刻字紫砂壶，快件运输中，咨询是否支持7天无理由退货。",
    messages: [
      {
        id: "m201",
        role: "user",
        content: "我前天买的定制刻字紫砂壶还在路上，现在不想要了，能拒收退货吗？",
        timestamp: "11:20:00",
      },
      {
        id: "m202",
        role: "assistant",
        content: "张先生您好！订单【ORD-2026-90412】包含个人定制专属刻字商品（底款『宁静致远』），根据《消费者权益保护法》与商城售后政策，此类定制商品非质量破损问题不支持7天无理由退换货。若快件在运输中出现碎裂破损，商城提供全额包赔与极速拍照补发保障！",
        confidenceScore: 0.94,
        timestamp: "11:20:04",
      },
    ],
    metrics: {
      totalTurns: 2,
      avgLatencyMs: 340,
      avgConfidence: 0.94,
      escalatedAt: null,
    },
    contextSnapshot: null,
    latestTransfer: null,
    unreadForAgent: false,
    createdAt: "2026-03-28 11:20:00",
    updatedAt: "2026-03-28 11:20:04",
  },
  "session_user_003": {
    id: "session_user_003",
    userName: "刘总",
    status: "AI_HANDLING",
    assignedAgent: null,
    assignedAgentId: null,
    customerProfile: {
      name: "刘总",
      phone: "136****8888",
      vipLevel: "钻石VIP",
      sentiment: "neutral",
      urgency: "高",
      intent: "大宗加急专配与增值税专票",
      tags: ["钻石VIP", "对公专票", "大宗采购"],
      orderId: "ORD-2026-77310",
    },
    summaryMemory: "刘总为钻石VIP，咨询大宗办公投影设备专票与售后加急专配。",
    messages: [],
    metrics: { totalTurns: 0, avgLatencyMs: 350, avgConfidence: 0.98, escalatedAt: null },
    contextSnapshot: null,
    latestTransfer: null,
    unreadForAgent: false,
    createdAt: "2026-03-28 14:00:00",
    updatedAt: "2026-03-28 14:00:00",
  },
  "session_guest_new": {
    id: "session_guest_new",
    userName: "新访客",
    status: "AI_HANDLING",
    assignedAgent: null,
    assignedAgentId: null,
    customerProfile: {
      name: "新访客",
      phone: "",
      vipLevel: "普通会员",
      sentiment: "neutral",
      urgency: "中",
      intent: "常规售后咨询",
      tags: ["新会话"],
      orderId: "ORD-2026-88992",
    },
    summaryMemory: "新访客体验会话，欢迎咨询任何售后、退款或物流政策。",
    messages: [],
    metrics: { totalTurns: 0, avgLatencyMs: 300, avgConfidence: 0.95, escalatedAt: null },
    contextSnapshot: null,
    latestTransfer: null,
    unreadForAgent: false,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  },
};

// ==================== 主服务启动与 WebSocket 管理 ====================

async function startServer() {
  const app = express();
  app.use(express.json());

  // 全局 CORS 支持
  app.use((req, res, next) => {
    res.header("Access-Control-Allow-Origin", "*");
    res.header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS");
    res.header("Access-Control-Allow-Headers", "Origin, X-Requested-With, Content-Type, Accept, Authorization");
    if (req.method === "OPTIONS") return res.sendStatus(200);
    next();
  });

  // WebSocket 客户端池
  const activeSockets = new Map<WebSocket, { sessionId: string; role: string; name: string }>();

  const broadcastToSession = (sessionId: string, payload: any) => {
    const dataStr = JSON.stringify(payload);
    for (const [ws, info] of activeSockets.entries()) {
      if (ws.readyState === WebSocket.OPEN && info.sessionId === sessionId) {
        try {
          ws.send(dataStr);
        } catch (e) {}
      }
    }
  };

  const broadcastAll = (payload: any) => {
    const dataStr = JSON.stringify(payload);
    for (const [ws] of activeSockets.entries()) {
      if (ws.readyState === WebSocket.OPEN) {
        try {
          ws.send(dataStr);
        } catch (e) {}
      }
    }
  };

  // ==================== REST API 业务路由 ====================

  app.get("/api/gateway/status", (req, res) => {
    res.json({
      gateway: "IntelliServe Smart Gateway",
      architecture: "Full-Stack Node.js + FastAPI Hybrid",
      pythonConnected: true,
      pythonBackendUrl: "http://127.0.0.1:3000",
      pythonWsUrl: "ws://127.0.0.1:3000/ws",
    });
  });

  app.get("/api/sessions", (req, res) => {
    res.json({ sessions: Object.values(sessions) });
  });

  app.get("/api/sessions/:id", (req, res) => {
    const s = sessions[req.params.id];
    if (!s) return res.status(404).json({ error: "Session not found" });
    res.json({ session: s });
  });

  app.post("/api/sessions/:id/clear", (req, res) => {
    const s = sessions[req.params.id];
    if (s) {
      s.messages = [];
      s.updatedAt = new Date().toISOString();
      broadcastToSession(s.id, { type: "session:update", sessionId: s.id, session: s });
    }
    res.json({ success: true, session: s });
  });

  app.get("/api/agents", (req, res) => {
    res.json({ agents });
  });

  app.get("/api/orders", (req, res) => {
    res.json({ orders: Object.values(orders) });
  });

  app.get("/api/orders/:id", (req, res) => {
    const o = orders[req.params.id];
    if (!o) return res.status(404).json({ error: "Order not found" });
    res.json({ order: o });
  });

  app.post("/api/orders/:id/reset", (req, res) => {
    const oid = req.params.id;
    if (initialOrders[oid]) {
      orders[oid] = JSON.parse(JSON.stringify(initialOrders[oid]));
    } else if (orders[oid]) {
      orders[oid].status = "DELIVERED";
      orders[oid].statusText = "已签收";
      if (orders[oid].afterSales) {
        orders[oid].afterSales.refundStatus = "NONE";
        orders[oid].afterSales.refundAmount = 0.0;
        orders[oid].afterSales.requiresHumanAudit = false;
      }
    }
    const updated = orders[oid] || null;
    broadcastAll({ type: "order:update", orderId: oid, order: updated });
    res.json({ success: true, message: `订单 ${oid} 状态已重置为正常签收`, order: updated });
  });

  app.post("/api/sessions/:id/transfer", (req, res) => {
    const { targetAgentId, reason, triggerType, operatorNote } = req.body;
    const s = sessions[req.params.id];
    if (!s) return res.status(404).json({ error: "Session not found" });

    const agent = agents.find((a) => a.id === targetAgentId) || agents[0];
    s.status = "HUMAN_INTERVENED";
    s.assignedAgent = agent.name;
    s.assignedAgentId = agent.id;
    s.updatedAt = new Date().toISOString();

    const transferLog = {
      id: `t_${Date.now()}`,
      assignedAgentId: agent.id,
      assignedAgentName: agent.name,
      assignedDepartment: agent.department,
      triggerType: triggerType || "user_requested",
      reason: reason || "转人工客服服务",
      operatorNote: operatorNote || "",
      transferredAt: new Date().toLocaleTimeString("zh-CN", { hour12: false }),
    };
    s.latestTransfer = transferLog;

    const noticeMsg: ChatMessage = {
      id: `sys_${Date.now()}`,
      role: "system",
      content: `已成功将当前会话完整转接给【${agent.department} · ${agent.name}】（工号: ${agent.id}），问答记录与订单快照已完整移交。`,
      timestamp: new Date().toLocaleTimeString("zh-CN", { hour12: false }),
    };
    s.messages.push(noticeMsg);

    broadcastToSession(s.id, { type: "message:new", sessionId: s.id, message: noticeMsg, session: s });
    broadcastAll({ type: "session:update", sessionId: s.id, session: s, transferLog });
    res.json({ success: true, session: s, transferLog });
  });

  app.post("/api/sessions/:id/intervene", (req, res) => {
    const { action, agentName, agentId } = req.body;
    const s = sessions[req.params.id];
    if (!s) return res.status(404).json({ error: "Session not found" });

    if (action === "takeover") {
      s.status = "HUMAN_INTERVENED";
      s.assignedAgent = agentName || "张小雅 (金牌坐席)";
      s.assignedAgentId = agentId || "agent_101";
      const notice: ChatMessage = {
        id: `sys_${Date.now()}`,
        role: "system",
        content: `人工坐席【${s.assignedAgent}】已主动接入并接管会话。`,
        timestamp: new Date().toLocaleTimeString("zh-CN", { hour12: false }),
      };
      s.messages.push(notice);
      broadcastToSession(s.id, { type: "message:new", sessionId: s.id, message: notice, session: s });
    } else {
      s.status = "AI_HANDLING";
      s.assignedAgent = null;
      s.assignedAgentId = null;
      const notice: ChatMessage = {
        id: `sys_${Date.now()}`,
        role: "system",
        content: "人工坐席已结束会话接待，会话已平滑交还给 AI 智能客服托管。",
        timestamp: new Date().toLocaleTimeString("zh-CN", { hour12: false }),
      };
      s.messages.push(notice);
      broadcastToSession(s.id, { type: "message:new", sessionId: s.id, message: notice, session: s });
    }
    s.updatedAt = new Date().toISOString();
    broadcastAll({ type: "session:update", sessionId: s.id, session: s });
    res.json({ success: true, session: s });
  });

  app.post("/api/sessions/:id/human-message", (req, res) => {
    const { content, agentName, agentId } = req.body;
    const s = sessions[req.params.id];
    if (!s) return res.status(404).json({ error: "Session not found" });

    const msg: ChatMessage = {
      id: `m_${Date.now()}_${s.messages.length}`,
      role: "human_agent",
      content,
      agentName: agentName || s.assignedAgent || "张小雅",
      agentId: agentId || s.assignedAgentId || "agent_101",
      timestamp: new Date().toLocaleTimeString("zh-CN", { hour12: false }),
    };
    s.messages.push(msg);
    s.updatedAt = new Date().toISOString();

    broadcastToSession(s.id, { type: "message:new", sessionId: s.id, message: msg, session: s });
    broadcastAll({ type: "session:update", sessionId: s.id, session: s });
    res.json({ success: true, message: msg, session: s });
  });

  app.post("/api/generate-suggestion", (req, res) => {
    const { sessionId } = req.body;
    const s = sessions[sessionId];
    const orderId = s?.customerProfile?.orderId || "ORD-2026-88992";
    const ord = orders[orderId];
    const suggestion = ord && ord.paidAmount >= 3.0
      ? `王女士您好！已为您核验退款申请：订单【${orderId}】实付金额 ¥${ord.paidAmount.toFixed(2)} 元（≥ 3.00 元），按资金安全审核标准，我已为您加急提交人工干涉工单，请您稍候片刻！`
      : `您好！针对您咨询的问题，仓库收到商品质检合格后48小时内退款原路到账，黄金会员享免运费补贴特权，已为您优先登记处理！`;
    res.json({ suggestion });
  });

  // 智能客服问答主入口
  app.post("/api/chat", async (req, res) => {
    const { sessionId, message, refundConfirmationAction } = req.body;
    let s = sessions[sessionId];
    if (!s) {
      s = {
        id: sessionId,
        userName: "客户",
        status: "AI_HANDLING",
        assignedAgent: null,
        assignedAgentId: null,
        customerProfile: {
          name: "客户",
          phone: "138****0000",
          vipLevel: "黄金会员",
          sentiment: "neutral",
          urgency: "中",
          intent: "售后咨询",
          tags: ["黄金会员"],
          orderId: "ORD-2026-88992",
        },
        summaryMemory: "客户建立会话连接。",
        messages: [],
        metrics: { totalTurns: 0, avgLatencyMs: 320, avgConfidence: 0.95, escalatedAt: null },
        contextSnapshot: null,
        latestTransfer: null,
        unreadForAgent: false,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      };
      sessions[sessionId] = s;
    }

    const nowStr = new Date().toLocaleTimeString("zh-CN", { hour12: false });
    const userMsg: ChatMessage = {
      id: `m_${Date.now()}_${s.messages.length}`,
      role: "user",
      content: message,
      timestamp: nowStr,
    };
    s.messages.push(userMsg);
    s.updatedAt = new Date().toISOString();

    // 实时推送用户消息
    broadcastToSession(sessionId, { type: "message:new", sessionId, message: userMsg, session: s });
    broadcastAll({ type: "session:update", sessionId, session: s });

    // 若会话已由人工接管
    if (s.status === "HUMAN_INTERVENED" || s.status === "TRANSFERRED") {
      return res.json({
        sessionId,
        reply: "您的消息已送达人工专员，坐席正在与您实时沟通中...",
        confidenceScore: 1.0,
        sentiment: "neutral",
        intent: "人工客服协同对话",
        escalatedToHuman: true,
        escalationReason: "会话处于人工坐席服务中",
        references: [],
        queriedOrder: null,
        latencyMs: 15,
        session: s,
      });
    }

    // 匹配关联订单
    const orderId = s.customerProfile?.orderId || "ORD-2026-88992";
    let targetOrder = orders[orderId] || orders["ORD-2026-88992"];

    // 检查文本是否提到特定订单号
    for (const [oid, ord] of Object.entries(orders)) {
      if (message.includes(oid) || message.includes(oid.replace("ORD-2026-", ""))) {
        targetOrder = ord;
        break;
      }
    }

    let reply = "";
    let refundPending = false;
    let pendingRefundOrder: OrderData | null = null;
    let queriedOrder: OrderData | null = null;
    let escalatedToHuman = false;
    let escalationReason: string | null = null;

    const lowerMsg = message.toLowerCase();
    const isRefundIntent = ["退款", "退货", "申请退款", "要退", "退钱", "退回"].some((k) => lowerMsg.includes(k));

    // 1. 处理退款二次确认按钮点击事件
    if (refundConfirmationAction === "confirm") {
      const amt = targetOrder.paidAmount;
      if (amt < 3.0) {
        targetOrder.status = "REFUNDED";
        targetOrder.statusText = "已退款(秒级到账)";
        targetOrder.afterSales.refundStatus = "AUTO_REFUNDED";
        targetOrder.afterSales.refundAmount = amt;
        targetOrder.afterSales.requiresHumanAudit = false;
        reply = `【智能客服秒退成功】您已二次确认！订单【${targetOrder.orderId}】实付金额为 ¥${amt.toFixed(2)} 元 (< 3.00 元)，智能客服已为您直接原路退回解冻，请查收！`;
      } else {
        targetOrder.status = "REFUND_PENDING_AUDIT";
        targetOrder.statusText = "退款待人工审核";
        targetOrder.afterSales.refundStatus = "PENDING_HUMAN_AUDIT";
        targetOrder.afterSales.refundAmount = amt;
        targetOrder.afterSales.requiresHumanAudit = true;
        s.status = "NEEDS_INTERVENTION";
        escalatedToHuman = true;
        escalationReason = `订单 ${targetOrder.orderId} 申请退款金额 ¥${amt.toFixed(2)} 元 (>= 3.00 元)，涉及资金安全，已通过二次确认提交至人工干涉与审核队列`;
        reply = `【退款审核工单已提交】您已二次确认！订单【${targetOrder.orderId}】实付金额为 ¥${amt.toFixed(2)} 元 (>= 3.00 元)，涉及商城资金安全，系统已自动为您提交工单并接入人工客服加急干涉与核验！`;
      }
      pendingRefundOrder = targetOrder;
      queriedOrder = targetOrder;
    } else if (refundConfirmationAction === "cancel") {
      reply = `已为您取消退款申请，订单【${targetOrder.orderId}】将保持正常签收状态。如需其他帮助，随时联系我！`;
      queriedOrder = targetOrder;
    } else if (isRefundIntent) {
      // 2. 触发退款前交互确认卡片 (Customer Confirmation Gate)
      const amt = targetOrder.paidAmount;
      refundPending = true;
      pendingRefundOrder = targetOrder;
      queriedOrder = targetOrder;
      const ruleText = amt < 3.0 ? "金额 < 3.00 元，确认后将由智能客服直接秒退" : "金额 >= 3.00 元，确认后将提交人工干涉与资金安全审核";
      reply = `收到您针对订单【${targetOrder.orderId}】（实付 ¥${amt.toFixed(2)} 元）的退款申请。\n根据商城退款规则（${ruleText}），在正式提交前，请您确认以下权益调整：\n• 订单对应的黄金/钻石会员积分及专属运费补贴将同步收回；\n• 退款将通过原支付渠道（支付宝/微信/银行卡）解冻退回。\n\n请在下方卡片中点击【确认提交退款】或【取消 / 我再想想】：`;
    } else if (["转人工", "人工", "找人工", "投诉", "人工客服", "客服专员"].some((k) => lowerMsg.includes(k))) {
      s.status = "NEEDS_INTERVENTION";
      escalatedToHuman = true;
      escalationReason = "客户主动要求转人工客服服务";
      reply = "【智能管家温馨提示】收到您的需求，正在为您无缝转接 XX商城 官方售后值班专员。系统已保留您的完整对话快照与订单记录，请稍候片刻...";
    } else if (["查订单", "物流", "快递", "运单", "到哪了", "顺丰", "发货"].some((k) => lowerMsg.includes(k))) {
      queriedOrder = targetOrder;
      reply = `已为您查询到订单【${targetOrder.orderId}】（${targetOrder.items[0]?.title || "商品"}）的最新物流轨迹：\n承运快递：${targetOrder.express.company}（运单号: ${targetOrder.express.trackingNumber}）\n当前状态：${targetOrder.express.statusDescription}\n最新节点：${targetOrder.express.timeline[0]?.context || "运输中"}`;
    } else if (["运费", "谁出", "谁付", "包邮", "免运费"].some((k) => lowerMsg.includes(k))) {
      reply = `王女士您好！根据XX商城政策：签收7天内商品完好支持7天无理由退换。虽然个人原因退换通常由买家承担运费，但检测到您是【黄金会员】，享有平台全额补贴的专属“退货免运费”特权，您无需承担任何寄回运费！`;
    } else {
      reply = `您好，王女士！我是XX商城智能客服主管，很高兴为您服务！\n我们已连接商城售后政策知识库与订单中台，您可以向我咨询订单查询、7天无理由退换货、运费补贴、退款到账时效或输入「转人工」接入人工坐席！`;
    }

    const assistantMsg: ChatMessage = {
      id: `m_${Date.now()}_${s.messages.length}`,
      role: "assistant",
      content: reply,
      confidenceScore: 0.95,
      queriedOrder: queriedOrder || undefined,
      refundConfirmationPending: refundPending,
      pendingRefundOrder: pendingRefundOrder || undefined,
      timestamp: new Date().toLocaleTimeString("zh-CN", { hour12: false }),
    };
    s.messages.push(assistantMsg);
    s.updatedAt = new Date().toISOString();

    // 实时推送助手消息
    broadcastToSession(sessionId, { type: "message:new", sessionId, message: assistantMsg, session: s });
    broadcastAll({ type: "session:update", sessionId, session: s });

    res.json({
      sessionId,
      reply,
      confidenceScore: 0.95,
      sentiment: "neutral",
      intent: isRefundIntent ? "退款申请" : "售后咨询",
      escalatedToHuman,
      escalationReason,
      references: [
        {
          id: "doc_1",
          title: "XX商城7天无理由退换货与运费承担规范",
          score: 0.95,
          snippet: "普通会员退换货运费自理；黄金/钻石VIP会员享全免运费补贴特权...",
        },
      ],
      queriedOrder,
      refundConfirmationPending: refundPending,
      pendingRefundOrder,
      latencyMs: 80,
      stepTrace: [
        { node: "analyze_query", description: "意图分类与情绪识别完成", durationMs: 12, status: "success" },
        { node: "order_query", description: `查询并关联目标订单 [${targetOrder.orderId}]`, durationMs: 25, status: "success" },
        { node: "order_refund", description: `退款意图与二次确认门槛状态: ${refundPending}`, durationMs: 18, status: "success" },
      ],
      session: s,
    });
  });

  // ==================== VITE 前端托管 ====================

  if (process.env.NODE_ENV !== "production") {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: "spa",
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), "dist");
    app.use(express.static(distPath));
    app.get("*", (req, res) => {
      res.sendFile(path.join(distPath, "index.html"));
    });
  }

  // ==================== 原生全双工 WEBSOCKET 服务 ====================

  const server = http.createServer(app);
  const wss = new WebSocketServer({ noServer: true });

  server.on("upgrade", (request, socket, head) => {
    const pathname = request.url ? new URL(request.url, `http://${request.headers.host}`).pathname : "";
    if (pathname.startsWith("/ws")) {
      wss.handleUpgrade(request, socket, head, (clientWs) => {
        clientWs.on("message", (raw) => {
          try {
            const data = JSON.parse(raw.toString());
            if (data.type === "join") {
              activeSockets.set(clientWs, {
                sessionId: data.sessionId || "session_user_001",
                role: data.role || "observer",
                name: data.name || "访客",
              });
            } else if (data.type === "typing") {
              // 转发输入状态
              const info = activeSockets.get(clientWs);
              const targetSession = data.sessionId || info?.sessionId;
              if (targetSession) {
                broadcastToSession(targetSession, {
                  type: "typing",
                  sessionId: targetSession,
                  sender: data.sender,
                  name: data.name,
                  isTyping: !!data.isTyping,
                });
              }
            }
          } catch (e) {}
        });

        clientWs.on("close", () => {
          activeSockets.delete(clientWs);
        });

        clientWs.on("error", () => {
          activeSockets.delete(clientWs);
        });
      });
    } else {
      socket.destroy();
    }
  });

  server.listen(PORT, "0.0.0.0", () => {
    console.log(`[IntelliServe Server] Running on http://localhost:${PORT}`);
  });
}

startServer();
