"""Reproduce issue 92 category reports using committed snapshot metadata only."""
import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


def write_csv(path, headers, rows):
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(headers)
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path('.'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    folder = args.repo / 'data/manifests/home-interior-354-v1'
    load = lambda name: json.loads((folder / name).read_text(encoding='utf-8-sig'))
    curation = load('assets_354.curation.json')
    assets = curation['assets']
    records = load('assets_354.json')
    baseline = json.loads((args.repo / 'data/manifests/objaverse_200.json').read_text(encoding='utf-8-sig'))
    by_id = {x['asset_id']: x for x in records}
    ids = [x['asset_id'] for x in assets]
    if len(records) != 354 or len(by_id) != 354 or len(ids) != 354 or len(set(ids)) != 354 or set(ids) != set(by_id):
        raise ValueError('Snapshot/curation ID or count mismatch')
    if len({(x['source'], x['source_id']) for x in records}) != 354:
        raise ValueError('Duplicate source identity')
    base_ids = {x['asset_id'] for x in baseline}
    if len(base_ids) != 200 or not base_ids <= set(by_id) or any(by_id[x['asset_id']] != x for x in baseline):
        raise ValueError('Baseline 200 not preserved')
    if any(not x.get('reviewed_category_vi') for x in assets):
        raise ValueError('Missing reviewed_category_vi: requires review')
    counts = Counter(x['reviewed_category_vi'] for x in assets)
    base_counts = Counter(x['reviewed_category_vi'] for x in assets if x['asset_id'] in base_ids)
    ordered = sorted(counts, key=lambda key: (-counts[key], key))
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / 'category-coverage.csv',
              ['reviewed_category_vi', 'count', 'percentage', 'baseline_200', 'additions_154'],
              [(k, counts[k], f'{counts[k]*100/354:.2f}', base_counts[k], counts[k]-base_counts[k]) for k in ordered])
    write_csv(out / 'candidate-assets.csv',
              ['asset_id', 'reviewed_category_vi', 'legacy_category', 'source_category_json', 'decision', 'human_reviewed', 'preview_sha256', 'preview_local_path', 'cohort', 'source_url', 'author', 'license'],
              [(x['asset_id'], x['reviewed_category_vi'], x.get('category'), json.dumps(x.get('source_category'), ensure_ascii=False), x.get('decision'), x.get('human_reviewed'), x.get('preview_sha256'), x.get('preview_local_path'), 'baseline_200' if x['asset_id'] in base_ids else 'additions_154', by_id[x['asset_id']].get('source_url'), by_id[x['asset_id']].get('author'), by_id[x['asset_id']].get('license')) for x in assets])
    source_counts = Counter(json.dumps(x.get('source_category'), ensure_ascii=False, sort_keys=True) for x in assets)
    write_csv(out / 'source-category-coverage.csv', ['source_category_json', 'count'], sorted(source_counts.items(), key=lambda x: (-x[1], x[0])))
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.glob('*.json'))}
    summary = dict(snapshot=curation.get('snapshot'), asset_count=354, baseline_200=len(base_ids), additions_154=len(set(by_id)-base_ids), unique_source_pairs=354,
                   grouping_field='reviewed_category_vi', mapping='Exact existing labels; no merging or source-category inference',
                   label_count=len(counts), missing_reviewed_labels=0,
                   missing_legacy_category=sum(not x.get('category') for x in assets),
                   human_reviewed_count=sum(x.get('human_reviewed') is True for x in assets),
                   decisions=dict(Counter(x.get('decision') for x in assets)),
                   labels_at_most_2=[k for k in ordered if counts[k] <= 2],
                   manifest_hashes=hashes)
    (out / 'coverage-summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    (out / 'manifest-sha256.txt').write_text(''.join(f'{digest}  {name}\n' for name, digest in hashes.items()), encoding='utf-8')
    lines = ['# Độ phủ danh mục — Issue #92', '',
             'Snapshot `home-interior-354-v1`: 354 asset = 200 mốc + 154 bổ sung.',
             f'Có **{len(counts)} nhãn kiểm duyệt hiện có**, không có nhãn reviewed_category_vi bị thiếu.', '',
             '## Phương pháp', '',
             'Dùng reviewed_category_vi cho cả 354 bản ghi và giữ nguyên chính xác từng nhãn. Không gom đồng nghĩa, không đổi metadata nguồn, không dùng category nguồn để suy đoán nhãn. Mỗi asset đóng góp một lần; tỷ lệ có mẫu số 354 và làm tròn hai chữ số.',
             '154 bản ghi bổ sung thiếu trường category cũ nhưng có reviewed_category_vi; không coi chúng là chưa phân loại. Nhãn này mô tả curation bằng AI hiện có, chưa phải xác nhận của người review độc lập.', '',
             '## Phân bố', '', '| Nhãn kiểm duyệt | Tổng | Tỷ lệ (%) | Mốc 200 | Bổ sung 154 |', '|---|---:|---:|---:|---:|']
    lines += [f'| {k} | {counts[k]} | {counts[k]*100/354:.2f} | {base_counts[k]} | {counts[k]-base_counts[k]} |' for k in ordered]
    lines += ['', '## Nhận xét và đề xuất', '',
              f'- Nhãn lớn nhất: {ordered[0]} ({counts[ordered[0]]}, {counts[ordered[0]]*100/354:.2f}%). Nhãn thứ hai: {ordered[1]} ({counts[ordered[1]]}, {counts[ordered[1]]*100/354:.2f}%).',
              f'- {sum(v <= 2 for v in counts.values())} nhãn chỉ có 1–2 asset. Đây là ngưỡng mô tả do báo cáo chọn, không phải tiêu chí loại hay mục tiêu cân bằng đã được nhóm chốt.',
              '- Hệ nhãn khác độ chi tiết: Ghế / Ghế văn phòng / Ghế bành; Bàn / Bàn trà / Bàn ăn; TV / TV và màn hình. Vì chưa có taxonomy thống nhất, số nhãn không đồng nghĩa số lớp độc lập; không diễn giải tỷ lệ từng nhãn như tỷ lệ toàn họ vật thể.',
              '- Nếu mục tiêu gồm truy vấn thiết bị nhỏ, ưu tiên xem xét bổ sung lò nướng để bàn, bình moka, robot hút bụi và máy hút bụi. Chốt ngân sách và số mẫu với Khuê dựa trên danh sách truy vấn; báo cáo không tự tải thêm hoặc thay snapshot.',
              '- Các nhãn rất cụ thể như Bàn viết hoặc Ghế ăn có thể ít vì phân mảnh nhãn, chưa đủ căn cứ kết luận cả họ bàn/ghế thiếu dữ liệu. Thống nhất mapping trong một phiên bản phân tích riêng trước khi so sánh các họ.',
              '- Tất cả decision hiện là keep; không có decision uncertain trong curation. Rà trùng riêng vẫn còn một cặp uncertain trong duplicate-review.csv; không dùng decision keep để phủ nhận phát hiện đó.',
              f'- Có {summary["human_reviewed_count"]}/354 bản ghi human_reviewed=true. Không tự nâng trạng thái này sau thống kê hoặc rà bằng AI.', '',
              '## Tái lập', '', 'Từ gốc repo:', '', '```bash', 'python docs/reports/issue92/build_coverage.py --repo . --output work/issue92-reproduced', '```', '',
              'Script dùng thư viện chuẩn Python, không cần mạng, ảnh hoặc database. candidate-assets.csv giữ category nguồn riêng; source-category-coverage.csv là thống kê category nguồn trong curation, không dùng thay nhãn kiểm duyệt.', '',
              'Chưa xác nhận coverage đủ cho benchmark, chưa đối chiếu PostgreSQL/index và chưa thay đổi tập text 200.']
    (out / 'category-coverage.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=True, indent=2))


if __name__ == '__main__':
    main()
