from src.bootstrap import build_chat_pipeline


def test_build_chat_pipeline_constructs_successfully():
    pipeline = build_chat_pipeline()

    assert pipeline is not None


def test_query_planner_and_answer_generator_share_one_groq_client():
    pipeline = build_chat_pipeline()

    query_planner_llm = pipeline._query_planner._llm_provider
    answer_generator_llm = pipeline._answer_generator._llm_provider

    assert query_planner_llm is answer_generator_llm
