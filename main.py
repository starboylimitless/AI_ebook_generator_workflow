import argparse
import os
from pathlib import Path

from ebook_generator_workflow.workflows.workflow_controller import WorkflowController
from ebook_generator_workflow.utils.pdf_utils import ensure_directories


def main() -> None:
    parser = argparse.ArgumentParser(description="Chess Academy AI Workflow")
    parser.add_argument(
        "--safe-mode", "-s", action="store_true", help="Enable Safe Credit Mode to skip LLM calls if output exists"
    )
    
    args = parser.parse_args()

    if args.safe_mode:
        os.environ["SAFE_CREDIT_MODE"] = "1"
        print("🛡️  Safe Credit Mode ENABLED")

    paths = ensure_directories()
    controller = WorkflowController()
    result = controller.run()

    status = "completed" if getattr(result, "success", True) else "completed with structural issues"
    print(f"Workflow {status} after {getattr(result, 'verification_attempts', 1)} attempt(s).")
    print("Final ebook PDF:", result.final_pdf)
    print("Final metadata:", result.final_metadata)


if __name__ == "__main__":
    main()

