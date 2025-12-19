from src.agent.low_signal_classifier import LowSignalClassifier


class StubLLM:
    def __init__(self, label: str):
        self.label = label

    def invoke(self, _messages):
        class Response:
            def __init__(self, content: str):
                self.content = content

        return Response(self.label)


def test_classifier_skips_when_disabled():
    classifier = LowSignalClassifier(config={"fallbacks": {"enable_low_signal_classifier": False}})
    assert not classifier.should_classify("cancel")
    assert classifier.classify("cancel") == "actionable"


def test_classifier_maps_control_label():
    config = {
        "fallbacks": {
            "enable_low_signal_classifier": True,
            "llm_classifier": {"max_chars": 50},
        }
    }
    classifier = LowSignalClassifier(config=config, llm_client=StubLLM("CONTROL"))
    assert classifier.should_classify("cancel now")
    assert classifier.classify("cancel now") == "control"


def test_classifier_maps_noise_label():
    config = {
        "fallbacks": {
            "enable_low_signal_classifier": True,
            "llm_classifier": {"max_chars": 50},
        }
    }
    classifier = LowSignalClassifier(config=config, llm_client=StubLLM("NOISE"))
    assert classifier.classify("...") == "noise"

