# Architecture Notes

iRecommend uses Supabase as the system of record, LangChain for LLM calls and output parsing, LangGraph for workflows, and pgvector as the first vector store target. Business logic lives under `src/`; API and UI layers will call services instead of embedding domain logic directly.
