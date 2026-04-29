"""
urlparser 测试框架

分层测试策略:
    P0: 纯函数单元测试 (无网络, 毫秒级)
    P1: 模型/配置属性测试 (Hypothesis 属性基测试)
    P2: 访问限制/质量检测测试 (规则引擎验证)
    P3: 接口一致性测试 (API/CLI/SKILL 交叉验证, 需网络)
    P4: 回归快照测试 (结构指纹对比, 需网络)
    P5: 跨接口内容等价性测试 (深度内容对比, 需网络)

运行:
    pytest tests/framework/ -m "not integration"   # 快速测试 (P0-P2)
    pytest tests/framework/ -m integration          # 集成测试 (P3-P5)
    pytest tests/framework/                         # 全部
    pytest tests/framework/ --snapshot-update       # 更新快照基准
"""
