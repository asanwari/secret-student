from __future__ import annotations

from scripts.preload_space_models import parse_args


def test_preload_model_selection_uses_environment(monkeypatch):
    monkeypatch.setattr("sys.argv", ["preload_space_models.py"])
    monkeypatch.setenv("TEXT_MODEL_REPO", "example/text")
    monkeypatch.setenv("TEXT_MODEL_FILE", "text.gguf")
    monkeypatch.setenv("TEXT_MODEL_DESTINATION", "text/text.gguf")
    monkeypatch.setenv("VISION_MODEL_REPO", "example/vision")
    monkeypatch.setenv("VISION_MODEL_FILE", "vision.gguf")
    monkeypatch.setenv("VISION_MODEL_DESTINATION", "vision/vision.gguf")
    monkeypatch.setenv("VISION_MMPROJ_FILE", "projector.gguf")
    monkeypatch.setenv("VISION_MMPROJ_DESTINATION", "vision/projector.gguf")

    args = parse_args()

    assert args.text_repo == "example/text"
    assert args.text_file == "text.gguf"
    assert args.text_destination == "text/text.gguf"
    assert args.vision_repo == "example/vision"
    assert args.vision_file == "vision.gguf"
    assert args.vision_destination == "vision/vision.gguf"
    assert args.mmproj_file == "projector.gguf"
    assert args.mmproj_destination == "vision/projector.gguf"
