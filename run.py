from src.runner import ExperimentRunner

runner = ExperimentRunner("configs/experiments/baseline_3agent.yaml")
result = runner.run()

print(f"\n=== 实验完成 ===")
print(f"病例数: {len(result.case_results)}")
print(f"总 token: {result.total_token_usage.total_tokens}")
for cr in result.case_results:
    print(f"\n--- {cr.case_id} ---")
    print(cr.final_output[:300])  # 只打印前 300 字符