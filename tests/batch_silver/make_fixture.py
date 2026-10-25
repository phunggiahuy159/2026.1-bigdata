"""Sinh tests/fixtures/bronze_ct_certs.jsonl theo schema bronze.ct_certs (cố định, seed=7).

Chạy lại: python tests/batch_silver/make_fixture.py
Toàn bộ tên miền là giả (tiền tố `fixture-`), không lấy từ luồng chứng chỉ thật.
"""

import json
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "fixtures" / "bronze_ct_certs.jsonl"
BASE = datetime(2026, 10, 20, tzinfo=UTC)  # ngày 0
ISSUER_CN = "Fixture CA R1"
CAS = ["Fixture Encrypt", "Fixture Trust Inc", "Fixture Sign Ltd"]
SLDS = ["fixture-acme-bank", "fixture-acmepay", "fixture-shop", "fixture-news", "fixture-pay"]
SUFFIXES = ["com", "net", "vn", "com.vn", "xyz"]


def ts(day: int, sec: int) -> str:
    t = BASE + timedelta(days=day, seconds=sec)
    return t.strftime("%Y-%m-%dT%H:%M:%S.") + f"{t.microsecond // 1000:03d}Z"


def row(i, update_type, names, day, sec, serial, collector="c1", sha=None):
    return {
        "sha256": sha or f"{i:064x}",
        "update_type": update_type,
        "all_domains": names,
        "subject_cn": names[0] if names else None,
        "issuer_cn": ISSUER_CN,
        "issuer_o": CAS[i % len(CAS)],
        "serial_number": serial,
        "fingerprint": None,
        "signature_algorithm": "sha256WithRSAEncryption",
        "is_ca": False,
        "not_before": ts(day, sec),
        "not_after": ts(day + 90, sec),
        "cert_index": 1000 + i,
        "cert_link": None,
        "source_name": "Fixture Log",
        "log_url": "ct.fixture.invalid/log1",
        "ct_seen": None,
        "submission_ts": None,
        "seen_ts": ts(day, sec),
        "collector_id": collector,
        "kafka_partition": i % 6,
        "kafka_offset": i,
    }


def main():
    rnd = random.Random(7)
    rows, i = [], 0
    for n in range(240):  # chứng chỉ thường, ngày 0..2, nhiều chứng chỉ cùng domain
        day, sec = n % 3, rnd.randrange(80000)
        d = f"{rnd.choice(SLDS)}{n % 17}.{rnd.choice(SUFFIXES)}"
        names = [d, f"www.{d}"] + ([f"*.{d}"] if n % 5 == 0 else [])
        serial = f"{0xA000 + n:x}"  # chữ thường: job phải chuẩn hoá
        i += 1
        rows.append(row(i, "PrecertLogEntry" if n % 2 else "X509LogEntry", names, day, sec, serial))
        if n % 2:  # precert đi kèm cert cuối: sha khác, đến sau vài giây
            i += 1
            rows.append(row(i, "X509LogEntry", names, day, sec + 5, serial))
        if n % 10 == 0:  # collector thứ hai thấy lại đúng bản ghi cuối
            rows.append(
                dict(rows[-1], collector_id="c2", kafka_offset=rows[-1]["kafka_offset"] + 10_000)
            )

    def add(*args, **kw):
        nonlocal i
        i += 1
        rows.append(row(i, *args, **kw))

    # precert 23:59:58 ngày 1, cert cuối 00:00:03 ngày 2: khác ngày, phải gộp về ngày 1
    add("PrecertLogEntry", ["boundary.fixture-acme.com"], 1, 86398, "B0")
    add("X509LogEntry", ["boundary.fixture-acme.com"], 2, 3, "b0")
    # tên bẩn: IP, một nhãn, rỗng, hoa/thường lẫn dấu chấm cuối, tên chính là public suffix
    add(
        "X509LogEntry",
        ["1.2.3.4", "localhost", "", "  WWW.Mixed-Case.Fixture-Acme.COM.  ", "com.vn"],
        1,
        10,
        "D1",
    )
    # tên IDN (Unicode) -> punycode
    add("X509LogEntry", ["bánh-fixture.vn", "www.bánh-fixture.vn"], 0, 20, "1D")
    # thiếu serial: không gộp được; cùng sha (hai collector) khử trùng, sha khác thì hai dòng
    add("X509LogEntry", ["noserial.fixture-acme.net"], 1, 30, None, sha="a" * 64)
    rows.append(dict(rows[-1], collector_id="c2", kafka_offset=99_999))
    add("X509LogEntry", ["noserial.fixture-acme.net"], 1, 40, None, sha="b" * 64)
    # tên gốc và wildcard của nó trong cùng một chứng chỉ
    add("X509LogEntry", ["*.both.fixture-acme.com", "both.fixture-acme.com"], 2, 50, "B1")
    # ngoài khoảng ngày của test
    add("X509LogEntry", ["outside-range.fixture-acme.com"], 6, 10, "0F")
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(
        "".join(json.dumps(r, sort_keys=True, ensure_ascii=False) + "\n" for r in rows),
        encoding="utf-8",
    )
    print(len(rows), "dòng ->", OUT)


if __name__ == "__main__":
    main()
