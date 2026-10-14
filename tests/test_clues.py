"""Tests for the clue detector — pins the bug fixes so they can't regress."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.clues import ClueDetector

det = ClueDetector()


def test_qr_detected_with_spans():
    c, spans = det.detect("Scan the QR code below to verify.", "", "Support")
    assert c.suspiciousQR == 1
    assert spans.get("suspiciousQR")  # non-empty spans


def test_device_code_not_firing_on_plain_message():
    # The original bug: [A-Z0-9]{4,} on uppercased text fired on everything.
    c, _ = det.detect("Your package is on hold, please update your address.", "", "USPS")
    assert c.deviceCodeRequest == 0


def test_device_code_detects_real_code():
    c, _ = det.detect("Enter the verification code to continue.", "", "MS")
    assert c.deviceCodeRequest == 1


def test_legit_domain_not_suspicious():
    c, _ = det.detect("View your activity.", "https://account.microsoft.com/security", "MS")
    assert c.slink == 0


def test_unknown_domain_is_suspicious():
    c, _ = det.detect("Verify now.", "https://micros0ft-verify.biz/login", "MS")
    assert c.slink == 1


def test_urgency_detected():
    c, _ = det.detect("Act now, your account will be suspended within 24 hours.", "", "")
    assert c.urgency == 1
    assert c.urgentDeadline == 1


def test_too_good_needs_two_weak_or_one_strong():
    c1, _ = det.detect("This is a free newsletter.", "", "")   # one weak only
    assert c1.tgoodtbt == 0
    c2, _ = det.detect("Congratulations! You won a prize.", "", "")  # strong
    assert c2.tgoodtbt == 1


def test_spoofed_sender():
    c, _ = det.detect("Verify your account.", "https://evil.biz/login", "Microsoft Support")
    assert c.spoofedSender == 1


def test_length_trim_enforced():
    from core.generators import _trim_words
    long = "word " * 100
    assert len(_trim_words(long.strip(), 40).split()) <= 40
    short = "Short message here."
    assert _trim_words(short, 40) == short  # unchanged when already short


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    passed = 0
    for fn in fns:
        try:
            fn(); passed += 1; print(f"PASS {fn.__name__}")
        except AssertionError:
            print(f"FAIL {fn.__name__}"); traceback.print_exc()
    print(f"\n{passed}/{len(fns)} passed")
