import api_server


def test_extracts_final_result_payload():
    final = {"type": "reply", "message": "done"}
    result = {"final_result": final}

    extracted = api_server._extract_result_payload(result)

    assert extracted is final


def test_extracts_youtube_summary_payload():
    youtube_result = {
        "type": "youtube_summary",
        "message": "Video summary text",
        "data": {"video": {"title": "Demo"}},
    }

    extracted = api_server._extract_result_payload(youtube_result)

    assert extracted is youtube_result

