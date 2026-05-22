from langchain_core.output_parsers import JsonOutputParser


def get_json_parser() -> JsonOutputParser:
    return JsonOutputParser()
