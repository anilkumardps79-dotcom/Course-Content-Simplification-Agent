"""
main_flow.py
Programmatic test script for the Course Content Simplification Flow.

Usage:
    export PYTHONPATH=/path/to/adk/src:/path/to/adk
    python3 main_flow.py
"""
import asyncio
from pathlib import Path

from course_simplification_agent.tools.simplification_flow import (
    build_course_simplification_flow,
)


async def main() -> None:
    generated_folder = Path(__file__).resolve().parent / "generated"
    generated_folder.mkdir(exist_ok=True)

    print("Compiling and deploying Course Content Simplification Flow...")
    flow_def = await build_course_simplification_flow().compile_deploy()
    flow_def.dump_spec(str(generated_folder / "course_simplification_flow.json"))
    print(f"Flow spec saved to {generated_folder}/course_simplification_flow.json")

    print("\nInvoking flow with a test input...")
    result = await flow_def.invoke(
        {
            "course_content": (
                "A neural network is a machine learning model loosely inspired by "
                "the human brain. It consists of layers of interconnected nodes "
                "(neurons) that transform input data through weighted sums and "
                "non-linear activation functions to produce predictions."
            ),
            "learning_level": "beginner",
            "subject_area": "Artificial Intelligence",
        },
        debug=True,
    )
    print("\n=== Flow Result ===")
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
