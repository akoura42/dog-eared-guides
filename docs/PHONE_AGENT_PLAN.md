# Phone Verification Agent — Build Plan

Status: PLANNED (nothing built yet). This document is the plan of record;
update it as phases complete or decisions change.

## 1. Goal

An AI voice agent, running entirely on the owner's M3 Ultra (512GB), that
calls venues to verify dog policies and feeds structured outcomes into the
research ledger as tier-1 (`method: phone`) verifications.

**Success =** a queued ledger candidate goes from `unverifiable` to a
publishable verification (or a confirmed `rejected-no-dogs`/`closed`)
via an automated call whose transcript and structured summary a human can
audit before anything ships. The human-review PR gate is unchanged — the
agent produces evidence, never published pages.

## 2. Non-goals

- No cold outreach, sales, or promotion — verification questions only.
- No audio recordings kept (transcripts only; see §8).
- No IVR wrestling in v1: if a phone tree can't be escaped with one
  keypress guess, log `ivr-blocked` and hang up politely.
- No concurrent mass-dialing. This is a low-volume tool (≈5–30 calls per
  city launch), one call at a time in v1.
- Not a replacement for web verification — phone is the tier-3 → tier-1
  escalation path when the web fails.

## 3. Volume assumptions & cost

- Current backlog: 5 numbers queued in the Tahoe City ledger; expect
  10–30 calls per future city launch + occasional re-verification calls.
- Inference: $0 (local). Telephony: ~$1–2/mo for a number + ~1¢/min
  (≈ $2–5 per city launch). Total system cost is effectively the number
  rental.

## 4. Architecture

```
Telnyx number ── media stream (WebSocket) ──┐
                                            │  cloudflared tunnel
                                            ▼
                    ┌─────────────── Pipecat pipeline (macOS) ───────────────┐
                    │  VAD → STT (parakeet-mlx) → LLM (Qwen3-30B-A3B, MLX)   │
                    │        ← TTS (Kokoro-82M) ←        │                   │
                    └────────────────────────────────────┼───────────────────┘
                                                         ▼
                                    structured CallOutcome JSON
                                                         ▼
                        pipeline/ledger/ (checks.jsonl + place status + transcript file)
                                                         ▼
                              human review → venue file update → PR → merge
```

## 5. Component choices (all open source, all local)

| Layer | Choice | License | Notes |
|---|---|---|---|
| Orchestration | Pipecat | BSD-2 | Interruption/barge-in, VAD, turn-taking; Telnyx & Twilio transports built in |
| Telephony | Telnyx (or Twilio) media streams | n/a (carrier) | The only paid layer; `cloudflared` tunnel exposes the local agent |
| STT | parakeet-mlx (Parakeet TDT 0.6B v2) | CC-BY-4.0 weights | Real-time on Apple Silicon; fallback: whisper.cpp large-v3-turbo |
| LLM | Qwen3-30B-A3B via mlx-lm (OpenAI-compatible server) | Apache 2.0 | ~3B active params → fast TTFT; overqualified for a scripted dialog. Fallback: Qwen3-32B dense |
| TTS | Kokoro-82M | Apache 2.0 | Faster than real-time; natural enough for a utility call |

Latency budget per turn (target ≤ 1.5s perceived): VAD endpoint ~200ms +
STT ~150ms + LLM TTFT ~300–500ms + TTS first-audio ~150ms. Measure in
Phase 0; if TTFT exceeds budget, drop to Qwen3-14B/8B.

## 6. Call design

### Script skeleton (state machine, not freeform chat)

1. **Disclosure (mandatory, verbatim):** "Hi — I'm an automated assistant
   calling on behalf of Dog-Eared Guides, a travel guide. I have one quick
   question about your dog policy; this call isn't recorded. Is now okay?"
   - If no / annoyance / confusion → thank + end (`declined`).
2. **The question** (from the ledger row, e.g.): "Do you allow dogs at
   [venue] — for example on a patio or in outdoor areas?"
3. **Clarifiers** (max 2, only if relevant): where exactly; leash rules;
   fees; seasonal limits.
4. **Verbatim read-back (mandatory):** "So to confirm: [restatement]. Is
   that right?" — an outcome is only `confirmed` if the human affirms the
   read-back. This is the anti-hallucination gate.
5. **Close:** thank; if asked who's calling, give the site name and
   purpose; honor "take us off your list" instantly and permanently
   (`do-not-call` flag in the ledger row).

### Operational rules

- Calling window: 10:00–16:00 **venue-local** time, weekdays; skip likely
  meal rushes for restaurants (11:30–13:30) — encoded in the dialer.
- Max 2 attempts per venue per batch, ≥2 days apart. Voicemail: leave at
  most one short message with a callback number, or none (owner decision, §11).
- One concurrent call. Hard call timeout: 5 minutes.
- Any human distress/confusion → immediate polite exit; never argue.

### CallOutcome schema (the LLM's required structured output)

```json
{
  "place_id": "osm-blue-fish-pok",
  "outcome": "confirmed | denied-dogs | no-answer | voicemail | ivr-blocked | wrong-number | declined | unclear | do-not-call",
  "policy": {"allowed": "patio_only|indoors|outdoor_areas|grounds_only|no|null",
              "leash_required": null, "fee": null, "notes": "verbatim-as-possible answer"},
  "respondent_role": "e.g. host, manager, unknown",
  "readback_affirmed": true,
  "call_ts": "ISO-8601",
  "duration_s": 0
}
```

## 7. Ledger & site integration

- Every call appends to `pipeline/ledger/checks.jsonl` (actor: `phone-agent`)
  and saves a transcript to `pipeline/ledger/transcripts/<place_id>-<date>.md`.
- `readback_affirmed: true` outcomes update the place row
  (`published`-track, `rejected-no-dogs`, or `closed`) — but a human reads
  the transcript before any venue file is written; the file lands in a
  normal content PR.
- **Schema change required (small):** `verification.source_url` currently
  requires a URL, which phone verifications don't have. Change: make
  `source_url` nullable **iff** `method: phone`, and add
  `verification.transcript` (repo-relative path) so the venue page's
  "source" link can point at our own published transcript note instead.
- The `DogPolicyBlock` "Verified by phone" display already exists
  (`method: phone` label); no other site changes.

## 8. Compliance & etiquette (non-negotiable)

- **Disclose the bot** at the top of every call (California B.O.T. Act;
  also just honest).
- **No audio recording.** California is all-party-consent; we sidestep
  entirely by keeping live transcripts only, and the disclosure says so.
- B2B, low-volume, manually-triggered verification calls — not telemarketing;
  no autodialer patterns, no calls to any number marked `do-not-call`.
- Caller ID: a real Telnyx number that, if called back, plays a short
  message identifying Dog-Eared Guides (Telnyx greeting or forward).

## 9. Build phases & acceptance criteria

| Phase | Work | Done when |
|---|---|---|
| **0. Bench** | Install mlx-lm + Qwen3-30B-A3B, parakeet-mlx, Kokoro; measure turn latency end-to-end (text→audio) | p50 turn latency ≤1.5s on the M3 Ultra; models pinned in a `phone-agent/requirements` note |
| **1. Dialog sim** | Script state machine + CallOutcome schema, tested text-only. Adversarial sim: a second local model plays the venue employee across ≥8 scenarios (clear yes / clear no / unsure staffer / "let me ask the manager" / voicemail / wrong number / IVR / hostile) | ≥90% of sims produce a correct, schema-valid outcome; zero invented policies (readback gate holds) |
| **2. Local audio loop** | Pipecat pipeline mic↔speaker, no telephony; barge-in works | A human can role-play a call naturally; interruptions handled |
| **3. Telephony** | Telnyx number + media-stream transport + cloudflared tunnel; agent calls **owner's own phone** | 5 clean test calls incl. one voicemail and one mid-call hangup |
| **4. Supervised live** | Call the 5 queued Tahoe City numbers, owner listening live with a kill switch | 5 transcripts + outcomes in the ledger; human agrees with every outcome |
| **5. Operationalize** | `pipeline/call_agent/` CLI (`--place-id`, `--batch city`), schema change from §7, RUNBOOK section | A ledger phone-queue batch runs end-to-end with one command; docs updated |

Estimated effort: Phases 0–2 ≈ one focused day; 3 ≈ half day (tunnel/carrier
fiddliness); 4–5 ≈ half day. Sequential, each gated on the prior.

## 10. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Model invents a policy the human didn't state | Read-back gate: no affirmation → `unclear`, never `confirmed` |
| Misheard numbers (fees) | Repeat all numbers digit-by-digit in the read-back |
| IVR menus | v1 punts (`ivr-blocked`); a human calls those |
| Tunnel/carrier flakiness mid-call | Outcome `no-answer` + retry policy; never re-ring immediately |
| macOS sleep kills the agent | `caffeinate` wrapper in the CLI |
| Venue annoyance / reputation | Low volume, business hours, instant opt-out, human-quality manners in the script |
| Latency degrades under load | Nothing else heavy runs during call batches; bench gate in Phase 0 |

## 11. Decisions needed from the owner before Phase 3

1. Carrier account: Telnyx vs Twilio (plan assumes Telnyx), and who creates it.
2. Caller-ID number area code (530 local vs generic).
3. Voicemail policy: leave a short callback message, or never.
4. Calling window confirmation (default weekdays 10–16 venue-local, skipping 11:30–13:30 for eat/drink).

## 12. Out-of-scope future ideas (parking lot)

- Multi-city batch dialing with per-timezone scheduling
- Inbound line ("call us to update your listing") on the same number
- Using the local models for menu re-parsing / ledger dedup sweeps
- Whisper-based voicemail transcription for callbacks
