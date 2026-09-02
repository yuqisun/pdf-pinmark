def make_tools(session):
    def search(scope, terms=None, top_k=10, highlight="sentence", query=""):
        return session.search(scope, terms or [], top_k, highlight, query)

    def cite(doc_id, quote, page_hint=None):
        m = session.cite(doc_id, quote, page_hint)
        if not m:
            return {"error": {"code": "quote_not_found",
                              "message": "引文未匹配到原文",
                              "hint": "请核对引文字符，或改用 read_pages 定位"}}
        return {"matches": m}

    def get_more(doc_id, page, offset_start, offset_end, context_chars_before=600, context_chars_after=600):
        return session.get_more(doc_id, page, offset_start, offset_end,
                                context_chars_before, context_chars_after)

    def read_pages(doc_id, from_page, to_page, max_chars=None):
        return {"pages": session.read_pages(doc_id, from_page, to_page, max_chars)}

    def list_documents(path, recursive=True):
        return {"documents": session.list_documents(path, recursive)}

    def download_annotated(doc_id, spans):
        return session.download_annotated(doc_id, spans)

    return {"search": search, "cite": cite, "get_more": get_more,
            "read_pages": read_pages, "list_documents": list_documents,
            "download_annotated": download_annotated}
