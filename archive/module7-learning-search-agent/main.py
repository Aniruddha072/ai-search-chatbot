"""
Entry point. Wires agent.py and evaluator.py into one pipeline and
exposes a simple command-line loop.

Full pipeline, mapped to the Module 7 architecture:

  User -> LLM -> Reasoning -> Search Tool -> Retrieve   (create_agent's loop, agent.py)
       -> Evaluate                                       (evaluator.py)
       -> Summarize / Answer                              (formatted output, below)
"""
import sys

from agent import build_agent
from evaluator import evaluate_faithfulness


def extract_sources_text(agent_result: dict) -> str:
    """Pull the raw search-tool output out of the agent's message history
    so the evaluator has something concrete to check the answer against."""
    chunks = []
    for msg in agent_result["messages"]:
        if getattr(msg, "type", None) == "tool":
            chunks.append(str(msg.content))
    return "\n\n".join(chunks)


def ask(agent, question: str, verify: bool = True) -> str:
    """Run one question through the agent, optionally run the faithfulness
    check, and return a final formatted answer string."""
    result = agent.invoke({"messages": [{"role": "user", "content": question}]})
    # .text (not .content) -- .content is the provider's raw format, which is
    # a plain string for some providers (Claude) but a list of typed content
    # blocks for others (Gemini, especially with thinking-capable models).
    # .text normalizes both to a plain string.
    answer = result["messages"][-1].text

    if not verify:
        return answer

    sources_text = extract_sources_text(result)
    check = evaluate_faithfulness(question, answer, sources_text)

    if not check.is_faithful:
        warning = "\n\n⚠️  Faithfulness check flagged possible unsupported claims:\n" + "\n".join(
            f"  - {c}" for c in check.unsupported_claims
        )
        return answer + warning

    return answer


def main():
    print("Search Agent (Module 7 build). Type 'exit' to quit.\n")

    try:
        agent = build_agent()
    except EnvironmentError as e:
        print(f"Setup error: {e}")
        sys.exit(1)

    while True:
        try:
            question = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            sys.exit(0)

        if question.lower() in {"exit", "quit"}:
            print("Goodbye.")
            break
        if not question:
            continue

        print("\nAgent: thinking...\n")
        try:
            answer = ask(agent, question)
        except Exception as e:
            answer = f"Something went wrong: {e}"
        print(f"Agent: {answer}\n")


if __name__ == "__main__":
    main()
