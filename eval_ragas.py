from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision
from datasets import Dataset
import sys

# Tiny example dataset; expand with your own eval cases
data = Dataset.from_list([
    {
        "question": "How are secrets handled in this project?",
        "contexts": [
            "Secrets are stored in Azure Key Vault and injected into the Container App via managed identity."
        ],
        "answer": "Secrets are kept in Azure Key Vault and injected via managed identity into the Container App.",
        "ground_truth": "Secrets are stored in Azure Key Vault and consumed at runtime through managed identity."
    }
])

report = evaluate(
    data,
    metrics=[faithfulness, answer_relevancy, context_precision]
)

print(report)

# Fail CI if below thresholds
try:
    f = float(report["faithfulness"])
    a = float(report["answer_relevancy"])
    c = float(report["context_precision"])
except Exception:
    sys.exit(1)

if f < 0.70 or a < 0.70 or c < 0.60:
    print("Ragas thresholds not met. Failing build.")
    sys.exit(1)
