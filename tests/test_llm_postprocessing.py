from __future__ import annotations

import json
from typing import Any

import httpx
import importlib.util
import sys
import types
from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parents[1] / "src" / "pdf_convert"

if "pdf_convert" not in sys.modules:
    pdf_module = types.ModuleType("pdf_convert")
    pdf_module.__path__ = [str(MODULE_DIR.parent)]
    sys.modules["pdf_convert"] = pdf_module


def load_module(module_name: str):
    spec = importlib.util.spec_from_file_location(
        f"pdf_convert.{module_name}", MODULE_DIR / f"{module_name}.py"
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load module {module_name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ocr_module = load_module("ocr")
llm_postprocessing = load_module("llm_postprocessing")
postprocessing_module = load_module("postprocessing")

LLMPostProcessor = llm_postprocessing.LLMPostProcessor
LLMPostProcessorConfig = llm_postprocessing.LLMPostProcessorConfig
LLMResponse = llm_postprocessing.LLMResponse
OllamaProvider = llm_postprocessing.OllamaProvider
OCRResult = ocr_module.OCRResult
OCRPostProcessor = postprocessing_module.OCRPostProcessor
PostProcessingConfig = postprocessing_module.PostProcessingConfig
SpellCheckConfig = postprocessing_module.SpellCheckConfig


def test_ollama_prompt_and_cache():
    calls: dict[str, Any] = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        payload = json.loads(request.content.decode())
        assert "Bạn là một trợ lý" in payload["prompt"]
        return httpx.Response(200, json={"response": "đã chỉnh sửa"})

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    provider = OllamaProvider(client=client)
    processor = LLMPostProcessor(LLMPostProcessorConfig(providers=[provider]))

    ocr_result = OCRResult(text="Văn ban goc", confidence=0.4)
    response_first = processor.enrich(ocr_result, {"page": 1}, page_hash="hash", model="test")
    response_second = processor.enrich(ocr_result, {"page": 1}, page_hash="hash", model="test")

    assert response_first is response_second
    assert calls["count"] == 1
    assert response_first.text == "đã chỉnh sửa"


def test_fallback_ordering():
    class FailingProvider:
        name = "primary"

        def __init__(self) -> None:
            self.calls = 0

        def generate(self, request):  # pragma: no cover - invoked indirectly
            self.calls += 1
            raise RuntimeError("primary down")

    class SucceedingProvider:
        name = "secondary"

        def generate(self, request):
            return LLMResponse(text="ok", raw={"provider": "secondary"}, provider=self.name)

    failing = FailingProvider()
    processor = LLMPostProcessor(
        LLMPostProcessorConfig(providers=[failing, SucceedingProvider()])
    )

    ocr_result = OCRResult(text="test", confidence=0.9)
    response = processor.enrich(ocr_result)

    assert response.text == "ok"
    assert response.provider == "secondary"
    assert failing.calls == 1


def test_postprocessor_merges_outputs():
    class DummyProvider:
        name = "dummy"

        def __init__(self):
            self.called = False

        def generate(self, request):
            self.called = True
            return LLMResponse(text="van bản chuẩn", raw={}, provider=self.name)

    provider = DummyProvider()
    llm_config = LLMPostProcessorConfig(providers=[provider])
    config = PostProcessingConfig(
        spell_check=SpellCheckConfig(use_languagetool=False, use_pyvi=False),
        confidence_threshold=0.95,
        enable_llm=True,
        llm=llm_config,
        custom_dictionary={"ban": "bản"},
    )
    postprocessor = OCRPostProcessor(config)

    ocr_result = OCRResult(text="van ban", confidence=0.5)
    layout_metadata = {"tables": []}
    result = postprocessor.process_page(ocr_result, layout_metadata, page_hash="hash")

    assert provider.called is True
    assert result.spell_checked_text == "van bản"
    assert result.llm_text == "van bản chuẩn"
    assert result.final_text == "van bản chuẩn"
    assert result.provider == "dummy"

