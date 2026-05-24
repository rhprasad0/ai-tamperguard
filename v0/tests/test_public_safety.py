from ai_tamperguard.public_safety import scan_paths


def reasons_for(paths):
    return [finding.reason for finding in scan_paths(paths)]


def test_blocks_private_generated_paths():
    reasons = reasons_for(["data/private/windows/foo.csv"])

    assert any("private generated path" in reason for reason in reasons)


def test_blocks_generated_model_and_data_extensions():
    reasons = reasons_for(["public-demo.onnx", "exports/windows.csv"])

    assert any("forbidden generated artifact extension" in reason for reason in reasons)


def test_allows_schema_files_with_model_like_suffix(tmp_path):
    path = tmp_path / "model_artifact_v0.schema.json"
    path.write_text("{}", encoding="utf-8")

    assert scan_paths([str(path)]) == []


def test_blocks_forbidden_claim_text(tmp_path):
    path = tmp_path / "README.md"
    path.write_text("This detects malicious activity", encoding="utf-8")

    reasons = reasons_for([str(path)])

    assert any("forbidden claim" in reason for reason in reasons)


def test_missing_explicit_path_is_a_finding():
    reasons = reasons_for(["does/not/exist.md"])

    assert any("missing path" in reason for reason in reasons)


def test_scans_directory_contents(tmp_path):
    (tmp_path / "nested").mkdir()
    leaked_model = tmp_path / "nested" / "leak.onnx"
    leaked_model.write_text("placeholder", encoding="utf-8")
    claim_doc = tmp_path / "nested" / "README.md"
    claim_doc.write_text("This detects tampering", encoding="utf-8")

    reasons = reasons_for([str(tmp_path)])

    assert any("forbidden generated artifact extension" in reason for reason in reasons)
    assert any("forbidden claim" in reason for reason in reasons)


def test_unreadable_text_file_returns_finding(tmp_path, monkeypatch):
    path = tmp_path / "README.md"
    path.write_text("placeholder", encoding="utf-8")

    def raise_permission_error(self, *args, **kwargs):
        if self == path:
            raise PermissionError("blocked")
        return original_read_text(self, *args, **kwargs)

    original_read_text = type(path).read_text
    monkeypatch.setattr(type(path), "read_text", raise_permission_error)

    reasons = reasons_for([str(path)])

    assert any("unreadable text file" in reason for reason in reasons)


def test_adversarial_spec_can_list_forbidden_phrases():
    findings = scan_paths(["docs/v0-model-pipeline-spec-adversarial.md"])

    assert not any("forbidden claim" in finding.reason for finding in findings)
