from app.services.rag_service import rag_service


if __name__ == "__main__":
    result = rag_service.rebuild()
    print(result.model_dump_json(indent=2))
