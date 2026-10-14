"""
Clue detection — the single source of truth for which red flags a
message contains.

Design rules (these are the fixes over the original):

1. Every detector returns the *matched text spans*, not just 0/1, so the
   review desk can highlight exactly what triggered each clue and a human
   can see whether the detector is right.
2. No detector fires on a substring of an unrelated word. The original
   `r'qr'` matched the "qr" in no English words but also matched a bare
   "QR" anywhere; worse, the device-code detector matched
   `[A-Z0-9]{4,}` against an UPPERCASED copy of the whole message, so it
   fired on essentially every message. Both are fixed with word
   boundaries and real patterns.
3. Generators do NOT get to set clue flags. Whatever the LLM claims, the
   pipeline overwrites it with this detector's output (see generators.py).
   That is what makes the flags trustworthy.

Each detector returns List[str] of matched snippets. A clue is "present"
(1) iff that list is non-empty, except for the few detectors that need a
threshold (e.g. too-good-to-be-true needs >= 2 signals), which say so.
"""

import re
from typing import Dict, List, Tuple

from core.models import Clues, ALL_CLUES

# Domains we treat as legitimate — a link to one of these is not, by
# itself, a suspicious-link signal.
LEGIT_DOMAINS = [
    "microsoft.com", "google.com", "apple.com", "amazon.com",
    "roblox.com", "minecraft.net", "spotify.com", "discord.com",
    "youtube.com", "tiktok.com", "snapchat.com", "facebook.com",
    "tulsaschools.org", "usps.com", "irs.gov", "medicare.gov",
    "ssa.gov", "paypal.com", "chase.com", "bankofamerica.com",
]

URL_SHORTENERS = ["bit.ly", "tinyurl", "shortu.rl", "t.co", "goo.gl", "ow.ly"]


def _find(patterns: List[str], text: str, flags=re.I) -> List[str]:
    """Return the list of distinct matched snippets for the given patterns."""
    hits = []
    for pat in patterns:
        for m in re.finditer(pat, text, flags):
            snippet = m.group(0).strip()
            if snippet and snippet.lower() not in [h.lower() for h in hits]:
                hits.append(snippet)
    return hits


class ClueDetector:
    """Detects clues in a message and reports what matched."""

    # -- base clues ------------------------------------------------

    def _urgency(self, content: str) -> List[str]:
        patterns = [
            r"\burgent(?:ly)?\b", r"\bimmediate(?:ly)?\b", r"\basap\b",
            r"\bas soon as possible\b", r"\bact now\b", r"\bact fast\b",
            r"\bdon'?t wait\b", r"\blimited time\b", r"\bright away\b",
            r"\bexpires?\b", r"\bwithin \d+ (?:hours?|days?|minutes?)\b",
            r"\bwill be (?:suspended|closed|locked|deleted|disabled|returned)\b",
            r"\byour account will be\b", r"\baction required\b",
            r"\brespond (?:immediately|now)\b", r"\bprompt(?:ly)? attention\b",
            # Softer pressure cues the human taggers counted as urgency:
            r"\battention!", r"\bnow\b", r"\bbefore (?:it'?s |time )",
            r"\bhurry\b", r"\bquick(?:ly)?\b", r"\bspots are limited\b",
            r"\bonly \d+ (?:left|remain)", r"\bneeds? verification\b",
            r"\bverify (?:your )?(?:account|identity)? ?now\b",
            r"\bconfirm (?:your )?.{0,20}\bnow\b", r"\btoday only\b",
            r"\bflash sale\b", r"\bto avoid\b", r"\bor (?:your|risk)\b",
            r"\bfailed too many times\b", r"\bsuspend", r"\bdeactivat",
            r"\bruns? out\b",
        ]
        return _find(patterns, content)

    def _suspicious_link(self, link: str, content: str) -> List[str]:
        if not link:
            return []
        link_l = link.lower().strip()
        hits = []
        # Host = text between scheme and the first slash.
        host = re.sub(r"^[a-z]+://", "", link_l).split("/")[0]
        # Shorteners are always suspicious — match on the host, not a substring
        # (so 't.co' does not match inside 'microsof{t.co}m').
        for s in URL_SHORTENERS:
            if host == s or host.endswith("." + s) or host == s.split(".")[0]:
                hits.append(link.strip())
        # If the HOST ends with a known-legit domain, not suspicious.
        if any(host == d or host.endswith("." + d) for d in LEGIT_DOMAINS):
            return hits
        # Look-alike / deceptive tokens in the host.
        decept = [
            r"verify", r"secure", r"-update", r"confirm", r"login",
            r"signin", r"authenticate", r"-support", r"account-",
            r"\.(?:biz|info|xyz|live|pro|to|co)\b", r"\d",  # digits in host
        ]
        if _find(decept, link_l) or link_l.startswith("http://"):
            if link.strip() not in hits:
                hits.append(link.strip())
            return hits
        # A link to an unknown domain is mildly suspicious on its own.
        if link.strip() not in hits:
            hits.append(link.strip())
        return hits

    def _bad_grammar(self, content: str) -> List[str]:
        misspellings = [
            r"\brecieved?\b", r"\bverifiy\b", r"\bverificaton\b",
            r"\baccout\b", r"\bacount\b", r"\bpassowrd\b", r"\bpassord\b",
            r"\bclickk\b", r"\bimmediatly\b", r"\bemergancy\b",
            r"\bcongradulations?\b", r"\batention\b", r"\bsuppport\b",
            r"\bseding\b", r"\brandume\b", r"\bineligable\b",
            r"\beverythiing\b", r"\bmillennnium\b", r"\bfarmin'\b",
            r"\bclam\b(?! )", r"\bbellow\b", r"\bdi-activate\b",
        ]
        hits = _find(misspellings, content)
        # 3+ ALL-CAPS words (5+ letters) is a grammar/shouting signal.
        caps = re.findall(r"\b[A-Z]{5,}\b", content)
        if len(caps) >= 3:
            hits.extend(caps[:3])
        return hits

    def _too_good(self, content: str) -> Tuple[List[str], int]:
        strong = [
            r"\byou'?ve (?:been )?(?:won|selected)\b", r"\bwinner\b",
            r"\bprize\b", r"\bgiveaway\b", r"\bcongratulations?\b",
            r"\bgift card\b", r"\bgrand prize\b", r"\bclaim (?:your|now)\b",
            r"\bpre-?approved\b", r"\bguaranteed\b", r"\bexclusive\b",
            r"\b\d+% off\b", r"\bfree (?:robux|minecoins|v-?bucks|gift|reward|prize|codes?)\b",
            r"\bfree for the next\b", r"\beverything is free\b",
        ]
        weak = [r"\bfree\b", r"\bwon\b", r"\breward\b", r"\bbonus\b",
                r"\bselected\b", r"\bclaim\b", r"\b\$[\d,]+\b", r"\b\d+,\d{3}\b"]
        strong_hits = _find(strong, content)
        weak_hits = _find(weak, content)
        hits = strong_hits + [h for h in weak_hits if h.lower() not in
                              [s.lower() for s in strong_hits]]
        # One strong signal, or two weak ones, counts.
        present = 1 if (strong_hits or len(weak_hits) >= 2) else 0
        return hits, present

    def _personal_info(self, content: str) -> List[str]:
        patterns = [
            r"\bverify your (?:account|identity|information)\b",
            r"\bconfirm your (?:identity|account|details|information)\b",
            r"\bupdate your (?:information|details|account|shipping|contact)\b",
            r"\benter your\b", r"\bprovide your\b", r"\bsubmit your\b",
            r"\breply with your\b", r"\bconfirm your (?:details|contact)\b",
            r"\busername and (?:password|email)\b",
            r"\bpassword\b", r"\bcredit card\b", r"\bbank (?:account|details)\b",
            r"\bcard details\b", r"\bsocial security\b", r"\bdate of birth\b",
            r"\bzip code\b", r"\bhome address\b", r"\binsurance details\b",
            r"\bconfirm (?:your )?(?:student id|details|information|address|identity)\b",
            r"\bphone number\b", r"\byour (?:username|email address)\b",
            r"\bverify (?:your )?(?:account|identity|information|details|ownership|choice)\b",
            r"\bconfirm your (?:attendance|account info)\b",
            r"\bprovide (?:up-to-date )?.{0,20}(?:details|information)\b",
            r"\byour (?:full name|login info|account (?:details|info))\b",
            r"\bconfirm your (?:password|6-digit code)\b",
        ]
        return _find(patterns, content)

    # -- extended (technique) clues -------------------------------

    def _qr(self, content: str) -> List[str]:
        # Fixed: real phrases only, with word boundary on the bare acronym.
        patterns = [
            r"\bqr code\b", r"\bscan (?:the|this|below) (?:qr )?code\b",
            r"\bscan (?:to|and)\b", r"\bqr\b",
        ]
        return _find(patterns, content)

    def _callback(self, content: str) -> List[str]:
        patterns = [
            r"\bcall (?:us|our|the|now|immediately|back)\b",
            r"\bcall \+?\d[\d\-\.\s()]{6,}\d",  # call + a phone number
            r"\bcall this number\b", r"\bfraud department\b",
            r"\bsupport line\b", r"\bcall \d{3}[-.]?\d{3}[-.]?\d{4}\b",
            r"\b1[-.\s]?8\d{2}[-.\s]?\d{3}[-.\s]?\d{4}\b",  # toll-free number
        ]
        return _find(patterns, content)

    def _device_code(self, content: str) -> List[str]:
        # Fixed: match real code shapes, NOT every 4+ char uppercase run.
        patterns = [
            r"\bverification code\b", r"\benter (?:the )?code\b",
            r"\bsecurity code\b", r"\bone-?time (?:code|passcode|password)\b",
            r"\b6-digit code\b", r"\bauthenticator (?:app|code)\b",
            r"\bcode\s+[A-Z0-9]{2,4}-[A-Z0-9]{2,4}\b",  # X7K2-9M4P style
        ]
        return _find(patterns, content)

    def _invoice(self, content: str) -> List[str]:
        patterns = [
            r"\binvoice\b", r"\bpayment due\b", r"\bpast due\b",
            r"\boverdue\b", r"\bunpaid\b", r"\boutstanding (?:balance|bill)\b",
            r"\bimport dut(?:y|ies)\b", r"\btoll(?:s)?\b", r"\bpay (?:the )?bill\b",
        ]
        return _find(patterns, content)

    def _calendar(self, content: str) -> List[str]:
        patterns = [
            r"\bmeeting\b", r"\bcalendar\b", r"\binvitation\b",
            r"\brsvp\b", r"\bconfirm your attendance\b",
            r"\bplanning session\b",
        ]
        hits = _find(patterns, content)
        return hits if len(hits) >= 2 else []

    def _urgent_deadline(self, content: str) -> List[str]:
        patterns = [
            r"\bwithin \d+ (?:hours?|minutes?|days?)\b",
            r"\bin \d+ (?:hours?|minutes?)\b", r"\bby (?:tomorrow|2pm|friday)\b",
            r"\bby end of day\b", r"\bexpires? in \d+\b", r"\bdeadline\b",
            r"\b\d+ minutes?\b", r"\bnext \d+ hours?\b", r"\b24 hours?\b",
        ]
        return _find(patterns, content)

    def _spoofed_sender(self, username: str, link: str) -> List[str]:
        """A brand name in the sender while the link points elsewhere."""
        if not username:
            return []
        brands = ["microsoft", "google", "apple", "amazon", "paypal",
                  "bank", "usps", "dhl", "irs", "medicare", "netflix"]
        u = username.lower()
        matched_brand = next((b for b in brands if b in u), None)
        if not matched_brand:
            return []
        link_l = (link or "").lower()
        # If there's a link and it does NOT contain the brand's real domain,
        # the sender name is likely spoofed.
        if link_l and matched_brand not in link_l:
            return [f"sender '{username}' vs link '{link}'"]
        return []

    # -- orchestration --------------------------------------------

    def detect(self, content: str, link: str = "", username: str = ""
               ) -> Tuple[Clues, Dict[str, List[str]]]:
        """Return (Clues, spans). spans maps clue name -> matched snippets."""
        content = content or ""
        spans: Dict[str, List[str]] = {}

        def mark(name: str, hits: List[str]):
            if hits:
                spans[name] = hits

        urg = self._urgency(content); mark("urgency", urg)
        sl = self._suspicious_link(link, content); mark("slink", sl)
        bg = self._bad_grammar(content); mark("bgrammer", bg)
        tg_hits, tg = self._too_good(content)
        if tg:
            mark("tgoodtbt", tg_hits)
        pi = self._personal_info(content); mark("pinfo", pi)

        qr = self._qr(content); mark("suspiciousQR", qr)
        cb = self._callback(content); mark("callbackRequest", cb)
        dc = self._device_code(content); mark("deviceCodeRequest", dc)
        inv = self._invoice(content); mark("fakeInvoice", inv)
        cal = self._calendar(content); mark("fakeCalendarEvent", cal)
        ud = self._urgent_deadline(content); mark("urgentDeadline", ud)
        sp = self._spoofed_sender(username, link); mark("spoofedSender", sp)

        clues = Clues(
            urgency=1 if urg else 0,
            slink=1 if sl else 0,
            bgrammer=1 if bg else 0,
            tgoodtbt=tg,
            pinfo=1 if pi else 0,
            suspiciousQR=1 if qr else 0,
            callbackRequest=1 if cb else 0,
            deviceCodeRequest=1 if dc else 0,
            fakeInvoice=1 if inv else 0,
            fakeCalendarEvent=1 if cal else 0,
            urgentDeadline=1 if ud else 0,
            spoofedSender=1 if sp else 0,
        )
        return clues, spans

    # Backwards-compatible shim for any old call site.
    def detect_all_clues(self, content: str, link: str, username: str = "") -> Clues:
        clues, _ = self.detect(content, link, username)
        return clues


def compare_clues(claimed: Dict, detected: Clues) -> Dict:
    """
    Compare what a message *claims* vs. what the detector *finds*.
    Used by the clue-accuracy scorer and the review desk.
    """
    det = detected.to_dict()
    missing, extra = [], []
    for name in ALL_CLUES:
        c = int(claimed.get(name, 0) or 0)
        d = det.get(name, 0)
        if c == 1 and d == 0:
            missing.append(name)   # claimed but not actually present
        if c == 0 and d == 1:
            extra.append(name)     # present but not claimed
    agree = sum(1 for n in ALL_CLUES if int(claimed.get(n, 0) or 0) == det.get(n, 0))
    return {
        "missing_clues": missing,
        "extra_clues": extra,
        "agreement": agree / len(ALL_CLUES),
        "valid": not missing,
    }
