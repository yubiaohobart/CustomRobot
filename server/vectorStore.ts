import { getGenAI } from "./gemini.js";

export interface KnowledgeDoc {
  id: string;
  title: string;
  category: "售后政策" | "账单发票" | "配送物流" | "账户安全" | "产品使用" | "VIP服务";
  content: string;
  embedding?: number[];
  tags: string[];
  updatedAt: string;
}

export interface SearchResult {
  doc: KnowledgeDoc;
  score: number;
  snippet: string;
}

// Deterministic fallback embedding generation (128-dimension semantic hash vector)
// Guarantees fast, robust local vector similarity even if API key is not yet set or during network hiccups
function generateLocalFallbackEmbedding(text: string, dim: number = 128): number[] {
  const vec = new Array(dim).fill(0);
  const normalized = text.toLowerCase().trim();
  
  // Character n-grams and token hashing
  for (let i = 0; i < normalized.length; i++) {
    const charCode = normalized.charCodeAt(i);
    const idx1 = (charCode * 31 + i * 17) % dim;
    const idx2 = (charCode * 43 + i * 19) % dim;
    vec[idx1] += 1;
    vec[idx2] += 0.5;
  }
  
  // Word/term level weighting
  const words = normalized.split(/[\s,，.。!！?？、:：;；]+/);
  for (let w = 0; w < words.length; w++) {
    const word = words[w];
    if (!word) continue;
    let hash = 0;
    for (let c = 0; c < word.length; c++) {
      hash = (hash * 37 + word.charCodeAt(c)) % 2147483647;
    }
    const idx = Math.abs(hash) % dim;
    vec[idx] += 2.0;
  }

  // L2 Normalization
  let norm = 0;
  for (let i = 0; i < dim; i++) {
    norm += vec[i] * vec[i];
  }
  norm = Math.sqrt(norm);
  if (norm > 0) {
    for (let i = 0; i < dim; i++) {
      vec[i] /= norm;
    }
  }
  return vec;
}

export function cosineSimilarity(vecA: number[], vecB: number[]): number {
  if (!vecA || !vecB || vecA.length === 0 || vecB.length === 0) return 0;
  const len = Math.min(vecA.length, vecB.length);
  let dotProduct = 0;
  let normA = 0;
  let normB = 0;
  for (let i = 0; i < len; i++) {
    dotProduct += vecA[i] * vecB[i];
    normA += vecA[i] * vecA[i];
    normB += vecB[i] * vecB[i];
  }
  if (normA === 0 || normB === 0) return 0;
  const sim = dotProduct / (Math.sqrt(normA) * Math.sqrt(normB));
  return Math.max(0, Math.min(1, sim));
}

// Initial Enterprise Knowledge Base for Customer Service
const INITIAL_DOCS: Omit<KnowledgeDoc, "embedding">[] = [
  {
    id: "kb-001",
    title: "7天无理由退货与退款办理细则",
    category: "售后政策",
    content: "自用户签收商品之日起7日内（含7日），在商品完好、配件齐全、包装未经损坏的前提下，支持申请7天无理由退货。退货运费由买家承担，若购买了运费险可由保险赔付。申请审核通过后，仓库收件质检无误在48小时内原路退款至原支付渠道（支付宝、微信、银行卡）。生鲜、虚拟商品及定制商品不参与7天无理由退换。",
    tags: ["退款", "退货", "7天无理由", "时效", "运费险"],
    updatedAt: "2026-09-10 10:00:00",
  },
  {
    id: "kb-002",
    title: "电子发票与增值税专用发票申请指南",
    category: "账单发票",
    content: "订单确认收货后，可在【我的订单】-【申请开票】中选择开具电子普通发票或增值税专用发票。电子普票一般在申请提交后1-2小时内开具并发送至登记邮箱；企业增值税专票需提交纳税人识别号、开户行与账号，审核通过后3个工作日内顺丰寄出。发票抬头一旦生成不可随意变更，如需重开请联系人工客服登记作废重开流程。",
    tags: ["发票", "专票", "开票", "报销", "税号"],
    updatedAt: "2026-09-12 14:30:00",
  },
  {
    id: "kb-003",
    title: "物流延迟与配送时效赔偿机制",
    category: "配送物流",
    content: "普通快递默认顺丰或京东快递承运，国内主要城市48小时送达，偏远地区3-5天。若因不可抗力或物流转运异常导致超过承诺交付时间超48小时，系统将自动派发15元无门槛无期体验优惠券。若包裹发生破损或丢件，客服核实后将在24小时内启动先行补发流程或全额赔偿。",
    tags: ["物流", "发货", "快递延误", "顺丰", "丢件赔偿"],
    updatedAt: "2026-09-14 09:15:00",
  },
  {
    id: "kb-004",
    title: "账户安全与登录异常验证流程",
    category: "账户安全",
    content: "若您无法登录账户，请优先使用绑定手机号码获取短信验证码进行重置密码。如手机号码已停用或遗失，请点击【申诉找回账号】，提交注册时实名认证的身份证正反面及人脸比对。安全中心将在工作时间（9:00-18:00）2小时内完成人工复核。如怀疑账号被盗或异常扣款，可回复【紧急冻结】或联系人工客服立即挂起账户交易功能。",
    tags: ["密码找回", "手机换绑", "账号被盗", "安全中心", "冻结"],
    updatedAt: "2026-09-15 11:20:00",
  },
  {
    id: "kb-005",
    title: "VIP黄金与钻石会员专享特权说明",
    category: "VIP服务",
    content: "年累计消费满3000元自动晋升黄金会员，满8000元晋升钻石会员。钻石会员尊享专属人工客服直连（免排队通道）、退换货上门免费取件、专属生日礼包以及每月2张免运费券。VIP专属客服热线支持7×24小时全天候响应，并配备专属客户成功经理（CSM）全程跟踪重大业务需求。",
    tags: ["VIP", "钻石会员", "优先客服", "专属特权", "积分兑换"],
    updatedAt: "2026-09-16 16:00:00",
  },
  {
    id: "kb-006",
    title: "智能客服转接人工坐席规则与SLA承诺",
    category: "产品使用",
    content: "当用户表达复杂诉求、多次重复问题、情绪负面（如不满、投诉、愤怒）或主动输入【转人工】、【人工客服】、【投诉】时，系统将立即评估并进入人工介入队列。工作日白天人工坐席平均接入等待时长小于20秒，夜间非工作时段（22:00-次日8:00）提供智能坐席兜底，紧急工单承诺在次日上午9:30前优先回拨跟进。",
    tags: ["转人工", "人工坐席", "投诉", "服务时间", "响应时效"],
    updatedAt: "2026-09-17 08:30:00",
  },
  {
    id: "kb-007",
    title: "产品质量问题换货与寄修售后政策",
    category: "售后政策",
    content: "商品自签收起15天内出现非人为硬件或做工质量缺陷，支持免费换新或申请官方原厂维修。我们提供顺丰双向免运费取送件服务。用户需在售后工单上传故障外观或功能视频照片，技术工程师将在收到检测件后24小时内出具检测报告并寄送全新机器。",
    tags: ["质量问题", "换货", "返修", "质检报告", "免费上门"],
    updatedAt: "2026-09-17 12:00:00",
  }
];

class VectorStore {
  private docs: KnowledgeDoc[] = [];
  private isInitialized = false;

  constructor() {
    this.init();
  }

  private async init() {
    // Populate docs with initial data and embeddings
    this.docs = INITIAL_DOCS.map((d) => ({
      ...d,
      embedding: generateLocalFallbackEmbedding(d.title + " " + d.content + " " + d.tags.join(" ")),
    }));

    this.isInitialized = true;
    console.log(`[VectorStore] Initialized with ${this.docs.length} enterprise knowledge chunks.`);
  }

  public async getEmbedding(text: string): Promise<number[]> {
    try {
      if (process.env.GEMINI_API_KEY) {
        const ai = getGenAI();
        const response: any = await ai.models.embedContent({
          model: "gemini-embedding-2-preview",
          contents: text,
        });
        const values = response?.embedding?.values || response?.embeddings?.[0]?.values;
        if (values && values.length > 0) {
          return values;
        }
      }
    } catch (err) {
      // Fallback gracefully to high-dimensional local semantic embedding
      // console.warn("[VectorStore] API embedding failed or no key, using robust local semantic embedding.");
    }
    return generateLocalFallbackEmbedding(text);
  }

  public getAllDocs(): KnowledgeDoc[] {
    return this.docs.map(d => ({
      ...d,
      // Don't send huge raw vector array to frontend unless requested
      embedding: undefined,
    }));
  }

  public getDocById(id: string): KnowledgeDoc | undefined {
    return this.docs.find(d => d.id === id);
  }

  public async addDoc(doc: Omit<KnowledgeDoc, "id" | "updatedAt" | "embedding">): Promise<KnowledgeDoc> {
    const id = `kb-${String(this.docs.length + 1).padStart(3, "0")}`;
    const updatedAt = new Date().toISOString().replace("T", " ").substring(0, 19);
    const embedding = await this.getEmbedding(doc.title + " " + doc.content + " " + doc.tags.join(" "));
    
    const newDoc: KnowledgeDoc = {
      ...doc,
      id,
      updatedAt,
      embedding,
    };
    this.docs.unshift(newDoc);
    return newDoc;
  }

  public deleteDoc(id: string): boolean {
    const index = this.docs.findIndex(d => d.id === id);
    if (index !== -1) {
      this.docs.splice(index, 1);
      return true;
    }
    return false;
  }

  public async search(query: string, topK: number = 3, minScore: number = 0.35): Promise<SearchResult[]> {
    if (!query || !query.trim()) return [];
    
    const queryEmbedding = await this.getEmbedding(query);
    const queryLower = query.toLowerCase();

    const scoredDocs: SearchResult[] = this.docs.map(doc => {
      let score = 0;
      if (doc.embedding && doc.embedding.length > 0) {
        score = cosineSimilarity(queryEmbedding, doc.embedding);
      } else {
        const docEmb = generateLocalFallbackEmbedding(doc.title + " " + doc.content);
        score = cosineSimilarity(queryEmbedding, docEmb);
      }

      // Keyword boost for high-accuracy intent matching (Hybrid Search: Vector + BM25/Keyword boost)
      let keywordBoost = 0;
      for (const tag of doc.tags) {
        if (queryLower.includes(tag.toLowerCase())) {
          keywordBoost += 0.15;
        }
      }
      if (queryLower.includes(doc.title.toLowerCase()) || doc.title.toLowerCase().includes(queryLower)) {
        keywordBoost += 0.25;
      }
      
      const finalScore = Math.min(0.99, Number((score * 0.7 + keywordBoost * 0.3).toFixed(4)));

      // Generate relevant snippet
      let snippet = doc.content;
      if (snippet.length > 120) {
        snippet = snippet.substring(0, 120) + "...";
      }

      return {
        doc: {
          ...doc,
          embedding: undefined,
        },
        score: finalScore,
        snippet,
      };
    });

    // Sort by finalScore descending
    scoredDocs.sort((a, b) => b.score - a.score);

    return scoredDocs.filter(s => s.score >= minScore).slice(0, topK);
  }
}

export const vectorStore = new VectorStore();
