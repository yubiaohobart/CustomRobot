"""
DeepSeek 大模型客户端 (DeepSeek LLM Client)
支持接入 deepseek-chat 与 deepseek-reasoner，提供严格以 FAQ 知识库为基准的专业智能客服答复
支持异步 API 调用与优雅降级
"""

import os
import time
from typing import List, Dict, Any, Optional
import httpx
from config import settings
from core.logger import cprint, LogColor

class DeepSeekLLMClient:
    def __init__(
        self,
        api_key: str = settings.DEEPSEEK_API_KEY,
        base_url: str = settings.DEEPSEEK_BASE_URL,
        model: str = settings.DEEPSEEK_MODEL
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = 45.0

    async def generate_response(
        self,
        user_message: str,
        retrieved_docs: List[Dict[str, Any]],
        summary_memory: str = "",
        user_profile: Optional[Dict[str, Any]] = None,
        business_facts: str = "",
        order_info: Optional[Dict[str, Any]] = None,
        order_summary: str = ""
    ) -> str:
        """
        调用 DeepSeek API 生成客服答复
        【方案1：通用业务事实槽位抽象】
        无论未来扩展订单、物流、发票、优惠券、积分或售后单，统一作为 business_facts 事实块注入，
        Prompt 模板一劳永逸，终身无需再因业务功能增减而重复修改！
        """
        user_profile = user_profile or {}
        vip_level = user_profile.get("vipLevel", "普通会员")
        customer_name = user_profile.get("name", "尊敬的客户")

        # 整理检索出的知识库参考信息
        context_blocks = []
        for idx, doc in enumerate(retrieved_docs, 1):
            title = doc.get("title", f"参考条款 {idx}")
            content = doc.get("content", "")
            context_blocks.append(f"【参考条款 {idx} - {title}】\n{content}")
        context_str = "\n\n".join(context_blocks) if context_blocks else "暂无直接匹配的知识库条款。"

        # 方案1：提取通用业务中台事实（优先使用 business_facts，兼容 order_summary / order_info）
        facts_text = (business_facts or order_summary).strip()
        if not facts_text and order_info:
            from services.order_service import order_service
            facts_text = order_service.format_order_summary_text(order_info)

        business_facts_block = facts_text if facts_text else "当前客户尚未触发或关联特定业务中台实体数据。"

        # 构建高标准、通用解耦客服 Prompt
        system_prompt = f"""你是一名【XX商城】的官方资深金牌智能客服主管。
你的职责是严谨、专业、礼貌、温和地解答客户咨询，并结合业务中台事实协助办理售后、订单、物流及相关权益。

【客户画像与特权】
- 称呼：{customer_name}
- 会员等级：{vip_level}
（提示：如果客户是【黄金会员】或以上，请务必主动提醒其享有“退货免运费”专属特权，退货运费由平台全额补贴！）

【动态业务实体事实 (Business Facts)】
{business_facts_block}

【XX商城官方售后与退换货政策参考 (2026版)】
{context_str}

【历史会话记忆摘要】
{summary_memory if summary_memory else "新用户接入，初次提问。"}

【回答纪律】：
1. 涉及具体业务实体（如订单、物流、商品、发票、权益、优惠券等）时，必须严格基于【动态业务实体事实】作答；
2. 商城政策、时效规定（7天退换、运费承担、特殊商品范围、48小时质检及到账、1年联保）严格遵循【XX商城官方售后与退换货政策参考】；
3. 事实与政策中未提及的信息如实告知，严禁凭空编造不存在的事实或服务；
4. 口吻温暖热情、换位思考，条理清晰；
5. 如客户表达强烈不满、催促或明确要求人工，表达理解并告知已为您做好加急人工转接准备。"""

        # 尝试调用真实 DeepSeek API
        if self.api_key:
            try:
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}"
                }
                payload = {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message}
                    ],
                    "temperature": settings.DEEPSEEK_TEMPERATURE,
                    "max_tokens": settings.DEEPSEEK_MAX_TOKENS
                }
                t_req = time.time()
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(
                        f"{self.base_url}/chat/completions",
                        json=payload,
                        headers=headers
                    )
                    latency = time.time() - t_req
                    if resp.status_code == 200:
                        data = resp.json()
                        reply = data["choices"][0]["message"]["content"].strip()
                        cprint.llm(self.model, len(system_prompt), latency, is_fallback=False)
                        return reply
                    else:
                        cprint.warning(f"DeepSeek API 响应异常 (HTTP {resp.status_code}): {resp.text[:100]}，切入兜底引擎")
            except Exception as e:
                cprint.error(f"DeepSeek 请求异常 ({e})，已优雅降级至内建政策引擎")

        # 兜底智能回答生成 (基于 XX商城官方 2026 政策规则准确回复)
        cprint.llm(f"{self.model}(规则兜底)", 0, 0.01, is_fallback=True)
        return self._generate_fallback_response(
            user_message,
            retrieved_docs,
            vip_level,
            customer_name,
            order_info=order_info
        )

    def _generate_fallback_response(
        self,
        user_message: str,
        retrieved_docs: List[Dict[str, Any]],
        vip_level: str,
        customer_name: str,
        order_info: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        无 API Key 或网络离线时的精准智能答复兜底，确保 100% 贴合 XX商城 2026 政策
        """
        msg = user_message.lower()
        is_gold_vip = "黄金" in vip_level or "钻石" in vip_level

        # 0. 优先处理订单与物流查询
        if order_info and any(k in msg for k in ["订单", "物流", "发货", "运单", "快递", "到哪了", "什么时候到", "送达", "签收", "ord-", "88992", "90412", "77310"]):
            items_text = "、".join([f"{it['title']} (x{it['quantity']})" for it in order_info.get("items", [])])
            express = order_info.get("express", {})
            timeline = express.get("timeline", [])
            latest_status = timeline[0].get("context", express.get("statusDescription", "暂无最新物流")) if timeline else express.get("statusDescription", "暂无最新物流")
            after_sales = order_info.get("afterSales", {})
            can_return = after_sales.get("canReturn7Days", False)
            signed_days = after_sales.get("signedDays", 0)
            remaining_days = after_sales.get("returnDaysRemaining", 0)

            reply = (
                f"{customer_name}您好！已为您成功查询到订单信息：\n\n"
                f"📦 **订单编号**：`{order_info.get('orderId')}`\n"
                f"🛍️ **购买商品**：{items_text}\n"
                f"💰 **实付金额**：¥{order_info.get('paidAmount', 0):.2f}\n"
                f"🏷️ **当前状态**：**【{order_info.get('statusText', '处理中')}】**\n\n"
                f"🚚 **物流承运**：{express.get('company', '顺丰速运')}（运单号：`{express.get('trackingNumber', '暂无')}`）\n"
                f"📍 **最新轨迹**：{latest_status}\n\n"
                f"📋 **售后政策与保障**：\n"
            )
            if can_return:
                reply += (
                    f"• **7天无理由退换**：当前商品已签收第 {signed_days} 天，**仍在无理由退换期内（剩余 {remaining_days} 天）**。\n"
                    f"• **退货运费权益**："
                )
                if is_gold_vip:
                    reply += f"检测到您是【{vip_level}】，享有**平台全额补贴的『退货免运费』特权**，申请退货无需承担寄回运费！\n"
                else:
                    reply += f"根据商城政策，个人原因退货需由买家承担寄回运费。\n"
            else:
                reply += f"• **退换提示**：{after_sales.get('returnPolicy', '非质量问题暂不支持7天无理由退换')}。\n"

            reply += f"• **保修条款**：{after_sales.get('warrantyPolicy', '全系电子产品享1年全国联保')}。\n\n"
            reply += "如需办理退换货申请或催促配送，请随时告诉我，智能管家随时为您服务！"
            return reply

        # 1. 运费与7天无理由退货
        if any(k in msg for k in ["运费", "谁出", "谁付", "退货运费", "包邮", "免运费"]):
            base_reply = (
                f"{customer_name}您好！关于XX商城的退货运费政策规定如下：\n"
                f"1. **质量问题退换**（如商品破损、错发、功能故障）：来回运费由我们公司全额承担；\n"
                f"2. **个人原因退换**（如不喜欢、拍错等七天无理由）：寄回运费需由买家自行承担。"
            )
            if is_gold_vip:
                base_reply += f"\n\n✨ **专属礼遇**：检测到您是【{vip_level}】，您享有专属的『退货免运费』特权，寄回运费将由平台全额为您补贴！"
            else:
                base_reply += f"\n\n💡 温馨提示：升级为黄金会员即可享有平台补贴的『退货免运费』专属权益哦！"
            return base_reply

        # 2. 7天无理由退换范围
        if any(k in msg for k in ["7天", "七天", "退货", "退换", "无理由", "怎么退"]):
            reply = (
                f"{customer_name}您好！XX商城支持『7天无理由退换货』服务：\n"
                f"• **时效范围**：自签收商品之日起 7 天内（含 7 天）；\n"
                f"• **商品状态**：商品完好、包装及配件齐全且不影响二次销售的前提下，均可在订单中心申请；\n"
                f"• **运费说明**：质量问题由公司承担往返运费；个人原因退货由买家承担寄回运费"
            )
            if is_gold_vip:
                reply += f"（您的【{vip_level}】享受平台退货免运费补贴）；"
            else:
                reply += "；"
            reply += "\n您只需进入订单详情页点击『申请退换货』即可。"
            return reply

        # 3. 特殊商品/不能退的商品
        if any(k in msg for k in ["特殊商品", "不能退", "不予退换", "生鲜", "定制", "内裤", "母婴", "激活码", "拆封"]):
            return (
                f"{customer_name}您好！根据XX商城政策，以下特殊商品一经售出（非质量问题）不支持7天无理由退换：\n"
                f"1. **个人定制类**：刻字、按需定制尺寸的工艺品；\n"
                f"2. **鲜活易腐类**：生鲜水果、鲜花等；\n"
                f"3. **数字化虚拟商品**：在线下载或已拆封的软件激活码、充值卡；\n"
                f"4. **贴身与母婴用品**：交付后拆封影响人身健康安全的内裤、泳裤及母婴用品。\n\n"
                f"若收到时已有破损等质量问题，依然享受售后全额包赔保障，请随时联系我们。"
            )

        # 4. 退款到账时间
        if any(k in msg for k in ["到账", "多久", "几天", "退款时间", "打款", "钱什么时候"]):
            return (
                f"{customer_name}您好！XX商城的退款到账时效如下：\n"
                f"1. **仓库质检**：仓库在收到退回商品后，会在 **48 小时内** 完成质检入库；\n"
                f"2. **原路退款**：质检合格后系统自动原路发起退款：\n"
                f"   • **微信 / 支付宝零钱**：即时到账；\n"
                f"   • **借记卡**：1 ~ 3 个工作日到账；\n"
                f"   • **信用卡**：3 ~ 5 个工作日到账。"
            )

        # 5. 保修与维修
        if any(k in msg for k in ["保修", "维修", "坏了", "换新", "质保", "联保", "摔坏", "进水"]):
            return (
                f"{customer_name}您好！关于XX商城电器的维修与保修条款说明如下：\n"
                f"1. **全国联保**：全系电子产品均享有 **1 年全国联保** 官方服务；\n"
                f"2. **15天换新**：签收超过 7 天但在 15 天内发生非人为损坏的硬件故障，可申请『免费换新机』；\n"
                f"3. **非保修范围**：因人为摔落、进水、私自拆修导致的损坏，不属于免费保修，仅收取配件成本费进行维修。"
            )

        # 默认结合 Top-1 知识库内容
        if retrieved_docs:
            top_content = retrieved_docs[0].get("content", "")
            return (
                f"{customer_name}您好！根据XX商城售后服务与退换货政策（2026版）：\n\n"
                f"{top_content}\n\n"
                f"请问还有什么我可以为您解答的吗？如需办理特殊加急，也可以随时告诉我！"
            )

        return (
            f"{customer_name}您好！我是XX商城智能客服。我们全系支持7天无理由退换、电子产品1年全国联保及48小时极速质检退款。"
            f"如需办理具体退换货或咨询运费规则，请随时向我提问！"
        )

# 全局单例 DeepSeek 客户端
deepseek_client = DeepSeekLLMClient()
