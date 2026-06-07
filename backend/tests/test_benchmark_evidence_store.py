from benchmark.evidence_store import BenchmarkEvidenceRecord, BenchmarkEvidenceStore, build_launch_gate_report


def test_benchmark_launch_gate_fails_without_enough_real_samples() -> None:
    report = build_launch_gate_report(
        records=[
            BenchmarkEvidenceRecord(
                niche="beauty",
                runtime_class="short",
                output_url="https://cdn.example.com/output.mp4",
                qa_score=92,
                human_score=9,
                verdict="usable",
            )
        ],
        min_samples=3,
    )

    assert report.status == "fail"
    assert "benchmark_insufficient_sample_count" in report.blockers


def test_benchmark_launch_gate_passes_when_sample_quality_is_high() -> None:
    records = [
        BenchmarkEvidenceRecord(niche="beauty", runtime_class="short", qa_score=92, human_score=9, verdict="usable"),
        BenchmarkEvidenceRecord(niche="beauty", runtime_class="short", qa_score=88, human_score=8, verdict="usable"),
        BenchmarkEvidenceRecord(niche="beauty", runtime_class="short", qa_score=91, human_score=9, verdict="usable"),
    ]

    report = build_launch_gate_report(records=records, min_samples=3, min_usable_rate=0.80, max_hard_fail_rate=0.20)

    assert report.status == "pass"
    assert report.usable_count == 3
    assert report.usable_rate == 1.0
    assert report.average_qa_score == 90.33


def test_benchmark_evidence_store_round_trips_jsonl(tmp_path) -> None:
    store = BenchmarkEvidenceStore(tmp_path / "evidence.jsonl")
    record = BenchmarkEvidenceRecord(
        niche="ugc_review",
        runtime_class="short",
        target_platform="tiktok",
        output_url="https://cdn.example.com/ugc.mp4",
        cost_usd=0.42,
        latency_s=45.0,
        qa_status="pass",
        qa_score=90.0,
        human_score=8.5,
        verdict="usable",
    )

    store.append(record)
    loaded = store.load_all()

    assert len(loaded) == 1
    assert loaded[0].evidence_id == record.evidence_id
    assert loaded[0].output_url == record.output_url
