"""Hard constraints precede quality; human semantic review is explicit, never inferred."""
from pathlib import Path
import re
from sayelf_agent_ops.runtime import digest
from desktop.runtime.media_workflow import _hash

DIMENSIONS = ('Originality','Evidence','Insight','Conversation','Clarity','Hook','Brand Fit')
SECRET = re.compile(r'(?i)(?:bearer\s+[a-z0-9._-]{10,}|sk-[a-z0-9_-]{12,}|'
                    r'(?:api[_-]?key|password|access[_-]?token)\s*[:=]\s*\S+)')
EPISTEMICS = {'Fact','Observation','Inference','Opinion','Hypothesis'}


def content_payload(draft):
    return {k:draft[k] for k in ('id','account','day','kind','text','claims',
                                 'evidence_ids','classification','trend','revision')} | {
                                     'variant': draft.get('variant','NARRATIVE'),
                                     'matched_trends': draft.get('matched_trends',[])}


def inspect(draft, evidence, require_human=False):
    reasons = []
    if draft['classification'] != 'Public':
        reasons.append('CONTENT_NOT_PUBLIC')
    if SECRET.search(draft['text']):
        reasons.append('POSSIBLE_SECRET')
    # Conservative local envelope; live connector also needs official payload validation.
    weighted = sum(2 if ord(ch)>0x10ff else 1 for ch in draft['text'])
    if not draft['text'].strip() or weighted>280:
        reasons.append('TEXT_ENVELOPE_INVALID')
    if draft['kind'] not in {'BUILD','DEMO','FAILURE','INSIGHT','HUMAN','QUOTE','THREAD'}:
        reasons.append('KIND_FORBIDDEN')
    if not draft['claims']:
        reasons.append('CLAIM_LABELS_REQUIRED')
    validated = {}
    for id in draft['evidence_ids']:
        e = evidence.get(id)
        if not e or e['classification']!='Public' or not e['verified_by']:
            reasons.append('EVIDENCE_NOT_VERIFIED_PUBLIC')
            continue
        try:
            path = Path(e['path'])
            raw = path.read_bytes() if path.is_file() and not path.is_symlink() else b''
            text = raw.decode('utf-8')
            if _hash(raw)!=e['sha256'] or not e['excerpt'] or e['excerpt'] not in text:
                raise ValueError()
            validated[id] = e
        except (OSError,ValueError,UnicodeError):
            reasons.append('EVIDENCE_CHANGED_OR_UNREADABLE')
    for claim in draft['claims']:
        if claim.get('label') not in EPISTEMICS or not claim.get('text'):
            reasons.append('INVALID_EPISTEMIC_LABEL')
            continue
        if claim['text'] not in draft['text']:
            reasons.append('CLAIM_NOT_IN_DRAFT')
        if claim['label'] in {'Fact','Observation'}:
            e = validated.get(claim.get('evidence_id'))
            if not e or claim['text'] not in e['excerpt']:
                reasons.append('FACT_EVIDENCE_MISSING')
        elif claim['label'] in {'Inference','Hypothesis'}:
            if not any(id in validated for id in claim.get('basis',[])):
                reasons.append('INFERENCE_BASIS_MISSING')
    review = draft['review']
    if review.get('content_digest') != digest(content_payload(draft)) or not review.get('actor'):
        reasons.append('CURRENT_HUMAN_REVIEW_REQUIRED')
    if require_human and review.get('actor')=='local-structural-gate':
        reasons.append('HUMAN_SEMANTIC_REVIEW_REQUIRED')
    for flag in ('claims_complete','evidence_checked','compliance_checked','original_work'):
        if review.get(flag) is not True:
            reasons.append(flag.upper()+'_REQUIRED')
    scores = draft['scores']
    valid = set(scores)==set(DIMENSIONS) and all(type(v) is int and 0<=v<=100 for v in scores.values())
    score = round(sum(scores.values())/len(DIMENSIONS),2) if valid else 0
    if not valid:
        reasons.append('QUALITY_RUBRIC_REQUIRED')
    state = 'BLOCKED' if reasons else ('PASS' if score>=80 else 'HOLD')
    return {'state':state,'score':score,'reasons':sorted(set(reasons)),
            'quality_source':review.get('quality_source','human rubric on current content'),
            'evidence_ids':list(validated)}


def score_local(draft, duplicate=False):
    """Transparent structural heuristic; not an originality or semantic truth oracle."""
    text=draft['text']
    body=' '.join(claim.get('text','') for claim in draft['claims'])
    concrete=bool(re.search(r'\d|passed|failed|fix|result|限制|要求|结果|修复|失败',body,re.I))
    return {'Originality':0 if duplicate else (85 if draft['review'].get('original_work') else 30),
            'Evidence':95 if draft['evidence_ids'] else (80 if all(c.get('label')=='Opinion' for c in draft['claims']) else 0),
            'Insight':85 if concrete else 60,
            'Conversation':85 if '?' in text or '？' in text else 30,
            'Clarity':90 if 20<=len(text)<=240 else 55,
            'Hook':80 if '\n\n' in text else 45,
            'Brand Fit':90 if draft['kind'] in {'BUILD','DEMO','FAILURE','INSIGHT','HUMAN'} else 75}
