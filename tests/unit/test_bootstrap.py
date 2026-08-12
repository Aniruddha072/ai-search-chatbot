from src.bootstrap import build_chat_pipeline, build_demo_pipeline
from src.infrastructure.evaluation.null_evaluator import NullEvaluator
from src.infrastructure.evaluation.ragas_evaluator import RagasEvaluator


def test_build_chat_pipeline_constructs_successfully():
    pipeline = build_chat_pipeline()

    assert pipeline is not None


def test_query_planner_and_answer_generator_share_one_groq_client():
    pipeline = build_chat_pipeline()

    query_planner_llm = pipeline._query_planner._llm_provider
    answer_generator_llm = pipeline._answer_generator._llm_provider

    assert query_planner_llm is answer_generator_llm


def test_build_chat_pipeline_uses_a_real_ragas_evaluator():
    pipeline = build_chat_pipeline()

    evaluator = pipeline._evaluation_service._evaluator

    assert isinstance(evaluator, RagasEvaluator)


def test_build_demo_pipeline_constructs_successfully():
    pipeline = build_demo_pipeline()

    assert pipeline is not None


def test_build_demo_pipeline_uses_a_null_evaluator():
    pipeline = build_demo_pipeline()

    evaluator = pipeline._evaluation_service._evaluator

    assert isinstance(evaluator, NullEvaluator)


def test_build_demo_pipeline_still_shares_one_groq_client():
    pipeline = build_demo_pipeline()

    query_planner_llm = pipeline._query_planner._llm_provider
    answer_generator_llm = pipeline._answer_generator._llm_provider

    assert query_planner_llm is answer_generator_llm
