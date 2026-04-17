"""手动测试 case_analyst agent

用法：
    # 使用内置示例文本
    python scripts/test_case_analyst.py

    # 从文件读取

    python scripts/test_case_analyst.py --file tempfile/test_input/case_chinese_01.txt

    # 从终端粘贴（输入后按 Ctrl+D 结束）
    python scripts/test_case_analyst.py --stdin

结果保存到 tempfile/casefile/ 目录下。
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# 确保项目根目录在 sys.path 中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

from src.agents.case_analyst import CaseAnalystAgent
from src.agents.base import AgentContext
from src.llm.client import LLMClient
from src.llm.cache import LLMCache


# ── 内置测试文本 ────────────────────────────────────────────

SAMPLE_CASE_TEXT = """\
Patient ID: TEST_001
A 58-year-old male, former smoker (20 pack-years, quit 10 years ago), retired construction worker \
with history of asbestos exposure. He presents with progressive exertional dyspnea over the past \
18 months and a persistent dry cough for 1 year. He denies hemoptysis, fever, weight loss, joint \
pain, or skin rash. No Raynaud phenomenon.

Physical examination reveals bilateral fine inspiratory crackles at the lung bases. No clubbing. \
No joint swelling or skin abnormalities.

Lab results: CBC within normal limits. ESR 22 mm/hr. CRP 3.8 mg/L. ANA negative. RF negative. \
ANCA negative. Anti-CCP negative.

Pulmonary function tests: FVC 72% predicted, DLCO 58% predicted, FEV1/FVC ratio normal.

HRCT chest: Bilateral, predominantly basal and subpleural ground-glass opacities with fine \
reticulation. No honeycombing. Mild traction bronchiectasis. Scattered areas of consolidation \
in the lower lobes. No mosaic attenuation. Small bilateral pleural effusions.

BAL: Lymphocyte 28%, Neutrophil 12%. No malignant cells.

The patient was started on prednisone 40mg daily 3 months ago with mild improvement in symptoms. \
Currently on prednisone 20mg daily with mycophenolate mofetil 1g BID added 1 month ago.
"""


def main():
    parser = argparse.ArgumentParser(description="测试 case_analyst agent")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--file", type=str, help="从文件读取病例文本")
    group.add_argument("--stdin", action="store_true", help="从标准输入读取（Ctrl+D 结束）")
    parser.add_argument("--model", type=str, default=None, help="覆盖默认模型")
    args = parser.parse_args()

    # 获取输入文本
    if args.file:
        case_text = Path(args.file).read_text("utf-8")
        print(f"[INFO] 从文件读取: {args.file}")
    elif args.stdin:
        print("[INFO] 请粘贴病例文本，按 Ctrl+D 结束输入：")
        case_text = sys.stdin.read()
    else:
        case_text = SAMPLE_CASE_TEXT
        print("[INFO] 使用内置示例病例文本")

    if not case_text.strip():
        print("[ERROR] 输入文本为空")
        sys.exit(1)

    print(f"[INFO] 输入文本长度: {len(case_text)} 字符")
    print("-" * 60)

    # 初始化 LLM 客户端
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY", "")
    base_url = os.getenv("OPENAI_BASE_URL")

    if not api_key:
        print("[ERROR] 未找到 OPENAI_API_KEY，请检查 .env 文件")
        sys.exit(1)

    cache = LLMCache()
    llm_client = LLMClient(api_key=api_key, base_url=base_url, cache=cache)

    # 创建 agent 和 context
    config_override = {}
    if args.model:
        config_override["model"] = args.model

    agent = CaseAnalystAgent(agent_id="case_analyst", config=config_override or None)
    context = AgentContext(llm_client=llm_client)

    # 执行
    print("[INFO] 正在调用 LLM...")
    input_data = {"case_text": case_text, "case_id": "test_input"}

    try:
        output = agent.execute(input_data, context)
    except Exception as e:
        print(f"[ERROR] Agent 执行失败: {e}")
        sys.exit(1)

    # 输出结果
    print("[INFO] 解析成功！")
    print(f"[INFO] 模型: {output.metadata.get('model')}")
    print(f"[INFO] 缓存命中: {output.metadata.get('cached')}")
    print(f"[INFO] Case ID: {output.metadata.get('parsed_case_id')}")
    print("-" * 60)
    print(output.content)
    print("-" * 60)

    # 保存到 tempfile/casefile/
    out_dir = Path("tempfile/casefile")
    out_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    case_id = output.metadata.get("parsed_case_id", "unknown")
    out_path = out_dir / f"{case_id}_{timestamp}.json"

    # 保存美化的 JSON
    parsed = json.loads(output.content)
    out_path.write_text(
        json.dumps(parsed, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"[INFO] 结果已保存到: {out_path}")


if __name__ == "__main__":
    main()
