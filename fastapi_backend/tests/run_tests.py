#!/usr/bin/env python3
"""
一键单元测试运行脚本 (Test Runner)
用法：
  python tests/run_tests.py
支持：
  1. 自动检测 pytest，若已安装则使用 pytest 运行丰富测试报告
  2. 若未安装 pytest，自动无缝降级使用内置测试驱动执行全部用例并输出彩色列印报告
"""

import sys
import os
import time

# 确保项目主目录与 tests 目录进入 Python 导包路径
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(TESTS_DIR)
for p in [BACKEND_DIR, TESTS_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

def run_with_pytest():
    """尝试使用 pytest 运行测试"""
    try:
        import pytest
        print("\n" + "=" * 65)
        print("🚀 使用 Pytest 运行 IntelliServe FastAPI 全量单元测试...")
        print("=" * 65 + "\n")
        exit_code = pytest.main([
            TESTS_DIR,
            "-v",
            "--tb=short"
        ])
        return exit_code
    except ImportError:
        return None

def run_standalone_test_suite():
    """
    内置轻量测试驱动器：无需外部 pytest 依赖，直接执行所有测试函数
    保证在任何极简 Python 环境下都能 100% 运行并通过全部单元测试
    """
    from fastapi.testclient import TestClient
    from app import app
    from services.memory_service import memory_service
    from core.qdrant_store import qdrant_store

    import test_health_and_root
    import test_knowledge_search
    import test_sessions_and_human
    import test_chat_pipeline

    print("\n" + "=" * 70)
    print("🚀 IntelliServe 智能客服后端 API 接口单元测试驱动")
    print("📌 测试范围：根路由 / 健康探活 / Qdrant知识检索 / 会话记忆 / 人机转接 / LangGraph问答")
    print("=" * 70 + "\n")

    # 初始化 Qdrant 内存知识库
    qdrant_store.init_collection_with_faq()

    test_modules = [
        ("系统状态与自检 (Health & Diagnostics)", test_health_and_root),
        ("知识库切片与检索 (Knowledge & Search)", test_knowledge_search),
        ("会话记忆与人机转接 (Sessions & Human)", test_sessions_and_human),
        ("智能问答状态机链路 (Chat Pipeline)", test_chat_pipeline),
    ]

    total_count = 0
    passed_count = 0
    failed_count = 0
    failures = []

    # 预备通用夹具数据
    vip_profile = {
        "userId": "vip_user_888",
        "userName": "王女士",
        "tier": "GOLD",
        "benefits": ["退货免运费", "专属客服", "闪电退款"]
    }
    chat_req = {
        "sessionId": "test_standalone_runner_001",
        "message": "黄金会员退货免运费怎么申请？",
        "userProfile": vip_profile
    }

    t_all_start = time.time()

    with TestClient(app) as client:
        for group_name, module in test_modules:
            print(f"\n📂 【{group_name}】")
            
            # 找到模块中所有以 test_ 开头的测试函数
            funcs = [
                getattr(module, name)
                for name in dir(module)
                if name.startswith("test_") and callable(getattr(module, name))
            ]

            for func in funcs:
                total_count += 1
                func_name = func.__name__
                doc = (func.__doc__ or "").strip().split("\n")[0]
                
                # 重置会话与转接状态保证独立
                memory_service.sessions.clear()
                memory_service.transfer_logs.clear()

                t0 = time.time()
                try:
                    # 根据函数参数自动注入 client 或 sample_chat_request
                    code_args = func.__code__.co_varnames[:func.__code__.co_argcount]
                    kwargs = {}
                    if "client" in code_args:
                        kwargs["client"] = client
                    if "sample_chat_request" in code_args:
                        kwargs["sample_chat_request"] = chat_req.copy()
                    if "sample_vip_profile" in code_args:
                        kwargs["sample_vip_profile"] = vip_profile.copy()

                    func(**kwargs)
                    elapsed = (time.time() - t0) * 1000
                    passed_count += 1
                    print(f"  ✅ [PASS] {func_name:<42} ({elapsed:.1f}ms) - {doc}")
                except Exception as e:
                    elapsed = (time.time() - t0) * 1000
                    failed_count += 1
                    failures.append((func_name, str(e)))
                    print(f"  ❌ [FAIL] {func_name:<42} ({elapsed:.1f}ms) -> {e}")

    total_time = (time.time() - t_all_start) * 1000
    print("\n" + "=" * 70)
    print(f"📊 单元测试执行总结报告:")
    print(f"   总用例数 (Total):  {total_count}")
    print(f"   通过用例 (Passed): {passed_count}")
    print(f"   失败用例 (Failed): {failed_count}")
    print(f"   总耗时间 (Time):   {total_time:.1f} ms")
    print("=" * 70)

    if failures:
        print("\n❌ 失败用例详情清单:")
        for name, err in failures:
            print(f"  • {name}: {err}")
        return 1
    else:
        print("\n🎉 全部接口单元测试 100% 顺利通过！")
        return 0

if __name__ == "__main__":
    code = run_with_pytest()
    if code is None:
        code = run_standalone_test_suite()
    sys.exit(code)
