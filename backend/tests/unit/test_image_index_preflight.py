"""#89 input/audit pipeline với ảnh và encoder fixture, không dùng query benchmark."""

from copy import deepcopy
from contextlib import redirect_stdout
from io import StringIO
import shutil
import csv
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from PIL import Image
import pytest

from app.search.smoke import SmokeCheckError, digest
from scripts import verify_issue89_image_preflight as module


class FixtureProcessor:
    def to_dict(self):
        return {"size": {"width": 224, "height": 224}, "fixture": True}


class FixtureEncoder:
    revision = "b" * 40
    dimension = 3
    preprocessing_version = "fixture-rgb-l2-v1"
    processor = FixtureProcessor()
    def __init__(self, model):
        self.model_id = module.MODEL_IDS[model]
    def encode_images(self, images, *, batch_size):
        return [[1., 0., 0.] for _ in images]


def inputs(tmp_path, count=3):
    root=tmp_path/"received"
    root.mkdir()
    (root/"previews").mkdir()
    source,ready,candidates,previews=[],[],[],[]
    for i in range(count):
        row={"asset_id":f"asset-{i:03d}","formats":["glb"],"category":None,
             "license":"fixture-license","face_count":i}
        path=root/"previews"/f"{i}.png"
        with Image.new("RGB",(2,2),(i,1,2)) as image:
            image.save(path)
        checksum=digest(path)
        source.append(row)
        ready.append({"metadata":row,"image_path":f"previews/{i}.png","preview_sha256":checksum})
        candidates.append({"asset_id":row["asset_id"],"preview_sha256":checksum})
        previews.append({"asset_id":row["asset_id"],"sha256":checksum})
    # Received package may include extra assets; only the exact source set is copied.
    ready.append({"metadata":{"asset_id":"extra"},"image_path":"not-needed.png","preview_sha256":"0"*64})
    module.write_json(root/"assets_354.ready.json",ready)
    source_path=tmp_path/"source.json"
    module.write_json(source_path,source)
    candidates_path=tmp_path/"candidate_assets.csv"
    with candidates_path.open("w",encoding="utf-8",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=["asset_id","preview_sha256"])
        writer.writeheader(); writer.writerows(candidates)
    provenance_path=tmp_path/"provenance.json"
    module.write_json(provenance_path,{"snapshot":module.SNAPSHOT,
        "manifest_sha256":digest(source_path),"previews":previews})
    return SimpleNamespace(root=root,source=source_path,candidates=candidates_path,
        provenance=provenance_path,expected_count=count,expected_hash=digest(source_path))


def prepare(case, output):
    return module.prepare_inputs(case.source,case.candidates,case.provenance,case.root,output,
        expected_count=case.expected_count,expected_source_sha256=case.expected_hash)


def test_prepare_copies_exact_subset_and_rechecks_candidate_checksums(tmp_path):
    case=inputs(tmp_path)
    output=tmp_path/"package"
    receipt=prepare(case,output)
    metadata,checked=module.validate_package(output,expected_count=3,expected_source_sha256=case.expected_hash)
    assert receipt==checked and len(metadata)==3
    assert "extra" not in metadata
    assert len(list((output/"previews").iterdir()))==3
    assert (output/"source.json").read_bytes()==case.source.read_bytes()
    assert receipt["filters"]=={} and receipt["benchmark"] is False
    with pytest.raises(FileExistsError):
        prepare(case,output)


@pytest.mark.parametrize("change",["source-hash","candidate-id","candidate-duplicate",
    "candidate-checksum","provenance-snapshot","provenance-id","missing-preview",
    "corrupt-preview","metadata","received-duplicate","external-preview"])
def test_bad_input_rejected_before_package_creation(tmp_path,change):
    case=inputs(tmp_path)
    if change=="source-hash":
        case.source.write_text("[]")
    elif change.startswith("candidate-"):
        with case.candidates.open(newline="") as stream:
            rows=list(csv.DictReader(stream))
        if change=="candidate-id": rows[0]["asset_id"]="wrong"
        if change=="candidate-duplicate": rows[0]["asset_id"]=rows[1]["asset_id"]
        if change=="candidate-checksum": rows[0]["preview_sha256"]="0"*64
        with case.candidates.open("w",newline="") as stream:
            writer=csv.DictWriter(stream,fieldnames=["asset_id","preview_sha256"])
            writer.writeheader(); writer.writerows(rows)
    elif change.startswith("provenance-"):
        obj=module.read_json(case.provenance)
        if change=="provenance-snapshot": obj["snapshot"]="other"
        else: obj["previews"][0]["asset_id"]="wrong"
        case.provenance.write_text(json.dumps(obj))
    elif change=="missing-preview":
        (case.root/"previews/0.png").unlink()
    elif change=="corrupt-preview":
        (case.root/"previews/0.png").write_bytes(b"broken")
    else:
        path=case.root/"assets_354.ready.json"
        obj=module.read_json(path)
        if change=="metadata": obj[0]["metadata"]["category"]="invented"
        if change=="received-duplicate": obj.append(deepcopy(obj[0]))
        if change=="external-preview": obj[0]["image_path"]="../outside.png"
        path.write_text(json.dumps(obj))
    output=tmp_path/"rejected"
    with pytest.raises((SmokeCheckError,FileNotFoundError)):
        prepare(case,output)
    assert not output.exists()


def test_package_tampering_rejected(tmp_path):
    case=inputs(tmp_path); output=tmp_path/"package"
    prepare(case,output)
    (output/"candidate_assets.csv").write_text("changed")
    with pytest.raises(SmokeCheckError,match="input_receipt_hash_mismatch"):
        module.validate_package(output,expected_count=3,expected_source_sha256=case.expected_hash)


@pytest.fixture(scope="module")
def built_reports(tmp_path_factory):
    tmp_path=tmp_path_factory.mktemp("issue89-pipeline")
    case=inputs(tmp_path,count=200); package=tmp_path/"package"
    prepare(case,package)
    validate=module.validate_package
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(module,"validate_package",lambda root: validate(root,expected_source_sha256=case.expected_hash))
        patch.setattr(module,"SOURCE_SHA256",case.expected_hash)
        patch.setattr(module,"load_encoder",lambda model:FixtureEncoder(model))
        paths={}
        for model in ("clip","siglip2"):
            args=SimpleNamespace(model=model,input_root=package,candidate_limit=10,
                reference_manifest=None if model=="clip" else paths["clip"].parent/"index-manifest.json")
            output=StringIO()
            with redirect_stdout(output):
                assert module.run_build(args,output_root=tmp_path/"runs")==0
            result=json.loads(output.getvalue().strip().splitlines()[-1])
            paths[model]=Path(result["report"])
        yield paths


def test_two_models_build_audit_read_only_smoke_and_compare(built_reports):
    result=module.compare_reports(built_reports["clip"],built_reports["siglip2"])
    assert result["preflight_ready"] and result["candidate_count"]==200
    assert result["filters"]=={} and result["benchmark"] is False
    assert result["models"]["clip"]["index_config"]["index_version"].startswith("issue89-")
    for path in built_reports.values():
        report=module.read_json(path)
        assert report["build"]["summary"]=={"embedded":200,"failed":0,"skipped":0}
        assert len(report["queries"])==3 and all(row["filters"]=={} for row in report["queries"])
        assert report["audit_before"]==report["audit_reopened"]
        manifest=module.load_image_index_manifest(path.parent/"index-manifest.json")
        assert manifest.collection=="issue89_image_previews"
        assert "scripts/verify_issue89_image_preflight.py" in manifest.module_sha256


@pytest.mark.parametrize("change",["not-ready","filters","wrong-count","wrong-hash","query","audit"])
def test_compare_rejects_mixed_or_incomplete_reports(built_reports,change,tmp_path):
    path=tmp_path/"report.json"
    shutil.copyfile(built_reports["siglip2"],path)
    shutil.copyfile(built_reports["siglip2"].parent/"index-manifest.json",tmp_path/"index-manifest.json")
    report=module.read_json(path)
    if change=="not-ready": report["preflight_ready"]=False
    if change=="filters": report["filters"]={"category":"chair"}
    if change=="wrong-count": report["input"]["asset_count"]=354
    if change=="wrong-hash": report["input"]["source_manifest_sha256"]="0"*64
    if change=="query": report["queries"][0]["query_sha256"]="0"*64
    if change=="audit": report["audit_reopened"]["unique_asset_ids"]=199
    path.write_text(json.dumps(report))
    with pytest.raises(SmokeCheckError):
        module.compare_reports(built_reports["clip"],path)


def test_wrong_reference_rejected_before_encoder(tmp_path,monkeypatch,built_reports):
    clip=built_reports["clip"]
    root=Path(module.read_json(clip)["input_root"])
    loader=Mock(side_effect=AssertionError("must not load model"))
    monkeypatch.setattr(module,"load_encoder",loader)
    args=SimpleNamespace(model="siglip2",input_root=root,candidate_limit=5,
                         reference_manifest=clip.parent/"index-manifest.json")
    with pytest.raises(SmokeCheckError,match="reference_inputs_mismatch"):
        module.run_build(args,output_root=tmp_path/"rejected")
    loader.assert_not_called()
    assert not (tmp_path/"rejected").exists()
