import csv
from collections import defaultdict

BRANDS = ['Thule', 'Ulanzi', 'Inateck', 'LISEN', 'WiWU', 'HyperWork', 'Anker', 'Sharge']

def get_brand(title):
    title_lower = title.lower()
    for b in BRANDS:
        if b.lower() in title_lower:
            return b
    return "Other"

rows = []
with open('content_plan.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    for row in reader:
        rows.append(row)

posted = [r for r in rows if r['Status'] == 'POSTED']
# Bài đã có nháp WP — giữ nguyên thứ tự, KHÔNG trộn (đã sẵn sàng publish)
wp_drafts = [r for r in rows if r['Status'] == 'WP_DRAFT']
# Hàng chờ tạo nháp: tất cả status còn lại (DRAFT/PENDING/APPROVED/…), không bỏ sót dòng nào
queue = [r for r in rows if r['Status'] not in ('POSTED', 'WP_DRAFT')]

# Group by brand
brand_groups = defaultdict(list)
for r in queue:
    brand = get_brand(r['Title'])
    brand_groups[brand].append(r)

# Interleave
interleaved = []
while any(brand_groups.values()):
    for brand in sorted(brand_groups.keys()):
        if brand_groups[brand]:
            interleaved.append(brand_groups[brand].pop(0))

out = posted + wp_drafts + interleaved
assert len(out) == len(rows), f"Reorder làm mất dòng: {len(rows)} -> {len(out)}"
with open('content_plan.csv', 'w', encoding='utf-8', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(out)

print("Done reordering!")
